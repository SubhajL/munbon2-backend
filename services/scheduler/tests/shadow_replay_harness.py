"""PR 6.5a — deterministic end-to-end shadow replay harness (TEST support).

Drives the REAL control-plane chain — canonical requirement → draft → prediction → shadow
approval → activation → validation-receipt dispatch — over a caller-supplied session, with
INJECTED deterministic upstream clients (ROS/flow prediction, SCADA validate) and a FIXED clock.

It lives under tests/ (not src/) because it fabricates trusted authorization evidence and a
self-manufactured device-capability snapshot to bypass the human RBAC/token path and the external
D6 registry — appropriate for a determinism fixture, NOT for the production image.

What it PROVES (PR 6.5's done-gate):
- RETRY / RESTART idempotence: re-running against the SAME persisted database yields a byte-identical
  canonical projection and ZERO new rows (create_draft replays on input_content_hash → stable
  plan_id and every uuid5-derived intent id; the lifecycle transitions are guarded on the plan's
  derived state; dispatch persists receipts exactly-once via ON CONFLICT).
- COMPUTE determinism (checked by the test running the chain on a SECOND, INDEPENDENT fresh schema):
  the content hashes (input/draft) are equal, so the optimizer + prediction are deterministic.

What it does NOT prove (do not oversell): a live SCADA's own idempotent receipt replay (on a retry the
scheduler-side exactly-once dedup means SCADA is not re-called), nor activation's capability-membership
gate (the snapshot is derived from the plan's own events, so every position is a member by construction).

It NEVER actuates: the only SCADA dependency is the validation-only ScadaValidationClient (single URL,
no execute path); there is no GateController/transport in the reachable graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Callable

from sqlalchemy import select

from algorithms.hydraulic_schedule_optimizer import optimize_limited_adjustment_plan
from core.control_plan_lifecycle import derive_control_plan_state
from core.device_capabilities import _content_hash as device_capability_content_hash
from models.control_plan import ControlCommandValidationReceipt
from repositories.control_plan_repository import PostgresControlPlanRepository
from schemas.control_plan import DraftControlPlanRequest
from schemas.machine_boundary import DeviceCapabilitySnapshot
from services.control_plan_lifecycle_service import ControlPlanLifecycleService
from services.control_plan_service import ControlPlanDraftService
from services.open_loop_execution_service import OpenLoopExecutionService
from services.shadow_dispatch_service import ShadowDispatchService
from jobs.shadow_dispatch_once import dispatch_active_plans


@dataclass(frozen=True)
class ReplayResult:
    """The canonical lineage + receipt projection — deliberately EXCLUDES created_at (DB now()),
    receipt_id (SCADA-minted), and observation_id (uuid4) so two runs of the same inputs compare
    equal. Everything here is content/identity-addressed."""

    plan_id: str
    plan_version: int
    input_content_hash: str
    draft_content_hash: str
    lifecycle_state: str
    intents: tuple[tuple[str, str], ...]
    receipts: tuple[tuple[str, str, str], ...]


async def _run_blocking(func, *args, **kwargs):
    return func(*args, **kwargs)


def build_device_snapshot_for_plan(record) -> DeviceCapabilitySnapshot:
    """A device-capability snapshot pinned to a plan's gate events, so every event position is an
    exact quantizer member (activation requires exact membership). Reuses the FROZEN capability-hash
    from core.device_capabilities (never forks it)."""
    gate_positions: dict = {}
    for event in record.events:
        positions = gate_positions.setdefault(event.gate_id, [])
        if event.target_position_m not in positions:
            positions.append(event.target_position_m)
    capabilities = {}
    for index, (gate_id, positions) in enumerate(gate_positions.items()):
        capabilities[gate_id] = {
            "device_id": f"rtu-{index}",
            "adapter_gate_id": f"ch-{index}",
            "targets": [
                {"target_position_m": position, "target_level": level}
                for level, position in enumerate(positions)
            ],
        }
    release_id = "cap-replay"
    snapshot = {
        "schema_version": 1,
        "capability_release_id": release_id,
        "capabilities": capabilities,
        "capability_hash": device_capability_content_hash(1, release_id, capabilities),
    }
    return DeviceCapabilitySnapshot(**snapshot)


def _strict_evidence(subject: str) -> dict:
    """Strict-policy authorization evidence, as the endpoint builds it — yields a TRUSTED approval
    (required for activation to grant machine authority). Synthetic; a determinism fixture only."""
    return {
        "authorization_policy_version": "control-plan-rbac-v1",
        "claim_policy_mode": "strict",
        "subject": subject,
        "roles": ["supervisor"],
        "token_identity_sha256": "9" * 64,
        "request_id": "replay-req",
        "evidence_refs": ["replay-ticket"],
    }


def _canonical_intents(outbox_rows) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((row.idempotency_key, row.intent_content_hash) for row in outbox_rows)
    )


async def _load_canonical_receipts(session, plan_id, plan_version):
    rows = (
        await session.execute(
            select(
                ControlCommandValidationReceipt.idempotency_key,
                ControlCommandValidationReceipt.status,
                ControlCommandValidationReceipt.receipt_content_sha256,
            ).where(
                ControlCommandValidationReceipt.plan_id == plan_id,
                ControlCommandValidationReceipt.plan_version == plan_version,
            )
        )
    ).all()
    return tuple(sorted((r.idempotency_key, r.status, r.receipt_content_sha256) for r in rows))


async def run_shadow_replay(
    session,
    *,
    draft_request: DraftControlPlanRequest,
    actor: str,
    clock: Callable[[], datetime],
    flow_client,
    ros_client,
    scada_client,
    model_step_seconds: int = 3600,
    max_intermediate_trims: int = 1,
    solver_timeout_seconds: int = 60,
    repository: PostgresControlPlanRepository | None = None,
) -> ReplayResult:
    """Drive the real chain once (idempotently) and return the canonical lineage + receipts.

    Raises RuntimeError if the plan does not reach shadow_active (e.g. a replay of a terminal plan
    would otherwise dispatch as a silent no-op) or if any per-plan dispatch failed."""
    repository = repository or PostgresControlPlanRepository()

    draft_service = ControlPlanDraftService(
        ros_client=ros_client,
        flow_client=flow_client,
        repository=repository,
        optimizer=partial(
            optimize_limited_adjustment_plan,
            model_step_seconds=model_step_seconds,
            max_intermediate_trims=max_intermediate_trims,
            solver_timeout_seconds=solver_timeout_seconds,
        ),
        run_blocking=_run_blocking,
        model_step_seconds=model_step_seconds,
        max_intermediate_trims=max_intermediate_trims,
        solver_timeout_seconds=solver_timeout_seconds,
        clock=clock,
    )
    record, _ = await draft_service.create_draft(session, draft_request, actor)

    lifecycle = ControlPlanLifecycleService(repository=repository, clock=clock)
    # Guard every transition on the plan's DERIVED state so a re-run against an already-advanced
    # plan is a no-op. create_draft's return carries the committed transitions in BOTH paths
    # (fresh -> (draft_created,); replay via find_by_input_hash -> the DB-assembled history).
    state = derive_control_plan_state(record.transitions)
    if state == "draft":
        await lifecycle.review_control_plan(session, record.plan_id, record.plan_version, actor)
        state = "under_review"
    if state == "under_review":
        await lifecycle.approve_shadow_plan(
            session,
            record.plan_id,
            record.plan_version,
            actor,
            authorization_evidence=_strict_evidence(actor),
        )
        state = "approved_for_shadow"
    if state == "approved_for_shadow":
        activation = ControlPlanLifecycleService(
            repository=repository,
            clock=clock,
            device_capability_snapshot=build_device_snapshot_for_plan(record),
        )
        await activation.activate_control_plan(
            session,
            record.plan_id,
            record.plan_version,
            actor,
            authorization_evidence=_strict_evidence(actor),
        )
        state = "shadow_active"

    if state != "shadow_active":
        raise RuntimeError(
            f"replay plan {record.plan_id} v{record.plan_version} is {state!r}, not shadow_active; "
            "cannot dispatch (a terminal/unexpected plan must fail loud, not no-op silently)"
        )

    # Dispatch: claim due intents (5.2) and persist a validation receipt each (6.3a), exactly-once
    # (ON CONFLICT) — a re-run adds zero receipt rows. NEVER executes/actuates.
    dispatch = ShadowDispatchService(
        repository,
        scada_client,
        OpenLoopExecutionService(repository, clock=clock, execution_mode="shadow"),
        clock=clock,
    )
    try:
        reports = await dispatch_active_plans(dispatch, session, repository)
    finally:
        await dispatch.aclose()
    failures = sum(len(report.failures) for report in reports)
    if failures:
        raise RuntimeError(
            f"replay dispatch had {failures} per-intent failure(s) — a SCADA/dispatch fault must "
            "surface, not hide behind missing receipts"
        )

    outbox = await repository.load_command_outbox(session, record.plan_id, record.plan_version)
    receipts = await _load_canonical_receipts(session, record.plan_id, record.plan_version)
    return ReplayResult(
        plan_id=str(record.plan_id),
        plan_version=record.plan_version,
        input_content_hash=record.input_content_hash,
        draft_content_hash=record.draft_content_hash,
        lifecycle_state=state,
        intents=_canonical_intents(outbox),
        receipts=receipts,
    )
