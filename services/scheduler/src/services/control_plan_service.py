"""Draft control-plan orchestration (PR 4.3a).

`create_draft_control_plan` verifies caller-pinned exact requirements, obtains
one model snapshot, composes the limited-adjustment problem, optimizes,
predicts feasible results through Flow, and persists one immutable
content-addressed draft. Optimizer infeasibility is a valid persisted draft;
every upstream failure aborts with nothing persisted.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from algorithms.hydraulic_schedule_optimizer import (
    GateEventKind,
    LimitedAdjustmentPlan,
    PlanStatus,
)
from core.control_plan import (
    UpstreamContractError,
    build_control_prediction_request,
    build_limited_adjustment_problem,
    canonical_instant,
    canonical_json_text,
    control_plan_draft_hash,
    control_plan_input_hash,
    serialize_limited_adjustment_plan,
    summarize_prediction_status,
)
from repositories.control_plan_repository import (
    DraftPlanRecord,
    GateEventRecord,
    PlanContentConflictError,
    RequirementRecord,
    TransitionRecord,
    build_draft_hash_document,
    text_sha256,
)
from schemas.control_plan import DraftControlPlanRequest

IDENTITY_VERSION = 1
OPTIMIZER_CONTRACT_VERSION = 1


class PlanNotFoundError(Exception):
    """No stored draft carries the requested plan id and version."""


class ModelIncompleteError(Exception):
    """The model snapshot cannot support drafting (HTTP 503)."""


class ControlPlanDraftService:
    def __init__(
        self,
        *,
        ros_client,
        flow_client,
        repository,
        optimizer: Callable[..., LimitedAdjustmentPlan],
        run_blocking: Callable[..., Awaitable[Any]],
        model_step_seconds: int,
        max_intermediate_trims: int,
        solver_timeout_seconds: int,
        clock: Callable[[], datetime] = None,
    ) -> None:
        self._ros = ros_client
        self._flow = flow_client
        self._repository = repository
        self._optimizer = optimizer
        self._run_blocking = run_blocking
        self._model_step_seconds = model_step_seconds
        self._max_intermediate_trims = max_intermediate_trims
        self._solver_timeout_seconds = solver_timeout_seconds
        # An explicit creation instant lets the repository commit the full
        # record atomically without a post-commit reload (which could fail
        # after a successful commit and wrongly report 503).
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def create_draft(
        self,
        session: AsyncSession,
        request: DraftControlPlanRequest,
        actor_subject: str,
    ) -> tuple[DraftPlanRecord, bool]:
        snapshot_text, snapshot = await self._flow.create_model_snapshot()
        release = snapshot.get("response_model_release")
        envelope = (snapshot.get("action_model") or {}).get(
            "operating_envelope"
        )
        if release is None or envelope is None:
            raise ModelIncompleteError(
                "flow-monitoring serves no committed model release; "
                "drafting is unavailable"
            )
        if snapshot["data_status"] not in ("complete", "partial"):
            raise ModelIncompleteError(
                f"model snapshot data_status is "
                f"{snapshot['data_status']!r}; drafting is unavailable"
            )

        scopes = [
            (scope.service_date, scope.zone)
            for scope in request.requirement_scopes
        ]
        items = await self._ros.get_exact_requirements(
            request.requirement_run_id,
            request.requirement_version,
            scopes,
        )

        problem, derived_document = build_limited_adjustment_problem(
            snapshot_id=snapshot["snapshot_id"],
            routing_elements=snapshot["routing_topology"]["elements"],
            response_members=release["response_members"],
            operating_envelope=envelope,
            unavailable_reach_ids=[
                entry["reach_id"]
                for entry in snapshot["unavailable_transport_reaches"]
            ],
            requirement_items=items,
            section_bindings={
                binding.section_id: binding.model_dump()
                for binding in request.section_bindings
            },
            requirement_policies={
                policy.requirement_id: policy.model_dump()
                for policy in request.requirement_policies
            },
            flow_candidates=[
                candidate.model_dump()
                for candidate in request.flow_candidates
            ],
            pulse_duties=[duty.model_dump() for duty in request.pulse_duties],
            branch_allocations=[
                allocation.model_dump()
                for allocation in request.branch_allocations
            ],
            operator_withdrawals=[
                withdrawal.model_dump()
                for withdrawal in request.operator_withdrawals
            ],
            horizon_start=request.starts_at,
            horizon_end=request.ends_at,
            model_step_seconds=self._model_step_seconds,
        )

        item_documents = sorted(
            (self._requirement_document(item) for item in items),
            key=lambda document: document["requirement_id"],
        )
        input_document = {
            "identity_version": IDENTITY_VERSION,
            "request": request.model_dump(mode="json"),
            "requirements": item_documents,
            "snapshot_pins": {
                "model_snapshot_id": snapshot["snapshot_id"],
                "model_release_id": release["release_id"],
                "model_release_content_hash": release["content_hash"],
            },
            "derived_problem": derived_document,
            "optimizer": {
                "contract_version": OPTIMIZER_CONTRACT_VERSION,
                "model_step_seconds": self._model_step_seconds,
                "max_intermediate_trims": self._max_intermediate_trims,
                "solver_timeout_seconds": self._solver_timeout_seconds,
            },
        }
        input_text = canonical_json_text(input_document)
        input_hash = control_plan_input_hash(input_document)

        existing = await self._repository.find_by_input_hash(
            session, input_hash
        )
        if existing is not None:
            if existing.canonical_input_document_text != input_text:
                raise PlanContentConflictError(
                    "an identical input hash is stored with different content"
                )
            return existing, True

        plan = await self._run_blocking(self._optimizer, problem)
        optimizer_document = serialize_limited_adjustment_plan(plan)
        optimizer_text = canonical_json_text(optimizer_document)

        candidate_flow = {
            (candidate.gate_id, candidate.target_position_m):
                candidate.source_flow_m3s
            for candidate in request.flow_candidates
        }
        events = self._event_records(plan, candidate_flow)

        prediction_run_id: Optional[str] = None
        prediction_status = "not_requested"
        member_summaries_text: Optional[str] = None
        prediction_request_text: Optional[str] = None
        prediction_response_text: Optional[str] = None
        prediction_response_sha: Optional[str] = None
        if plan.status is PlanStatus.FEASIBLE:
            obligation_by_id = {
                entry["requirement_id"]: entry
                for entry in derived_document["obligations"]
            }
            prediction_document = build_control_prediction_request(
                model_snapshot_id=snapshot["snapshot_id"],
                model_release_id=release["release_id"],
                model_release_content_hash=release["content_hash"],
                starts_at=request.starts_at,
                ends_at=request.ends_at,
                timestep_seconds=float(self._model_step_seconds),
                plan_events=plan.events,
                flow_candidates=[
                    candidate.model_dump()
                    for candidate in request.flow_candidates
                ],
                operator_withdrawals=[
                    withdrawal.model_dump()
                    for withdrawal in request.operator_withdrawals
                ],
                branch_allocations=[
                    allocation.model_dump()
                    for allocation in request.branch_allocations
                ],
                section_requirements=[
                    {
                        "requirement_id": item["requirement_id"],
                        "section_id": item["section_id"],
                        "delivery_node_id": obligation_by_id[
                            item["requirement_id"]
                        ]["delivery_node_id"],
                        "window_start": item["window_start"],
                        "window_end": item["window_end"],
                        "required_volume_m3": item["required_volume_m3"],
                        "maximum_delivery_m3s": self._binding_for(
                            request, item["section_id"]
                        ).maximum_delivery_m3s,
                        "approved_excess_m3": self._policy_for(
                            request, item["requirement_id"]
                        ).approved_excess_m3,
                    }
                    for item in items
                    if item["requirement_id"] in obligation_by_id
                ],
            )
            prediction_request_text = canonical_json_text(prediction_document)
            (
                prediction_response_text,
                prediction_parsed,
            ) = await self._flow.create_prediction(prediction_document)
            prediction_run_id = prediction_parsed["prediction_run_id"]
            prediction_status = summarize_prediction_status(prediction_parsed)
            member_summaries_text = canonical_json_text(
                [
                    {
                        "member": member.get("member"),
                        "status": member.get("status"),
                    }
                    for member in prediction_parsed["members"]
                ]
            )
            prediction_response_sha = text_sha256(prediction_response_text)

        draft_hash = control_plan_draft_hash(
            build_draft_hash_document(
                input_text,
                optimizer_text,
                prediction_request_text,
                prediction_response_sha,
            )
        )

        created_at = self._clock()
        record = DraftPlanRecord(
            plan_id=uuid4(),
            plan_version=1,
            identity_version=IDENTITY_VERSION,
            input_content_hash=input_hash,
            draft_content_hash=draft_hash,
            lifecycle_state="draft",
            optimizer_status=plan.status.value,
            prediction_status=prediction_status,
            requirement_run_id=request.requirement_run_id,
            requirement_version=request.requirement_version,
            model_snapshot_id=snapshot["snapshot_id"],
            model_release_id=release["release_id"],
            model_release_content_hash=release["content_hash"],
            prediction_run_id=prediction_run_id,
            prediction_member_summaries=member_summaries_text,
            horizon_start=request.starts_at,
            horizon_end=request.ends_at,
            model_step_seconds=self._model_step_seconds,
            max_intermediate_trims=self._max_intermediate_trims,
            canonical_input_document_text=input_text,
            model_snapshot_document_text=snapshot_text,
            optimizer_result_document_text=optimizer_text,
            optimizer_result_sha256=text_sha256(optimizer_text),
            prediction_request_document_text=prediction_request_text,
            prediction_response_document_text=prediction_response_text,
            prediction_response_sha256=prediction_response_sha,
            created_by_subject=actor_subject,
            requirements=self._requirement_records(
                request, items, derived_document
            ),
            events=events,
            transitions=(
                TransitionRecord(
                    transition_sequence=1,
                    transition_type="draft_created",
                    from_state=None,
                    to_state="draft",
                    actor_subject=actor_subject,
                    reason=None,
                    transition_document_text=None,
                    occurred_at=created_at,
                ),
            ),
            created_at=created_at,
        )
        return await self._repository.store_draft_plan(session, record)

    async def get_draft(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> DraftPlanRecord:
        record = await self._repository.load_draft_plan(
            session, plan_id, plan_version
        )
        if record is None:
            raise PlanNotFoundError(
                f"no control plan {plan_id} version {plan_version}"
            )
        return record

    @staticmethod
    def _binding_for(request: DraftControlPlanRequest, section_id: str):
        for binding in request.section_bindings:
            if binding.section_id == section_id:
                return binding
        raise UpstreamContractError(
            f"section {section_id!r} lost its binding mid-orchestration"
        )

    @staticmethod
    def _policy_for(request: DraftControlPlanRequest, requirement_id: str):
        for policy in request.requirement_policies:
            if policy.requirement_id == requirement_id:
                return policy
        raise UpstreamContractError(
            f"requirement {requirement_id!r} lost its policy mid-orchestration"
        )

    @staticmethod
    def _requirement_document(item: dict[str, Any]) -> dict[str, Any]:
        document = dict(item)
        document["service_date"] = item["service_date"].isoformat()
        document["as_of_date"] = item["as_of_date"].isoformat()
        document["window_start"] = canonical_instant(item["window_start"])
        document["window_end"] = canonical_instant(item["window_end"])
        document["published_at"] = canonical_instant(item["published_at"])
        return document

    def _requirement_records(
        self,
        request: DraftControlPlanRequest,
        items: list[dict[str, Any]],
        derived_document: dict[str, Any],
    ) -> tuple[RequirementRecord, ...]:
        obligation_by_id = {
            entry["requirement_id"]: entry
            for entry in derived_document["obligations"]
        }
        records = []
        for item in sorted(items, key=lambda entry: entry["requirement_id"]):
            requirement_id = item["requirement_id"]
            obligation = obligation_by_id.get(requirement_id)
            if obligation is None:
                planning: dict[str, Any] = {
                    "planning_disposition": "no_delivery_required",
                    "delivery_node_id": None,
                    "gate_id": None,
                    "maximum_delivery_m3s": None,
                    "approved_excess_m3": None,
                    "travel_delay_seconds": None,
                    "minimum_delivery_fraction": None,
                    "maximum_delivery_fraction": None,
                    "path_reach_ids_document_text": None,
                    "rotation_windows_document_text": None,
                }
            else:
                binding = self._binding_for(request, item["section_id"])
                policy = self._policy_for(request, requirement_id)
                planning = {
                    "planning_disposition": "scheduled",
                    "delivery_node_id": obligation["delivery_node_id"],
                    "gate_id": obligation["gate_id"],
                    "maximum_delivery_m3s": binding.maximum_delivery_m3s,
                    "approved_excess_m3": policy.approved_excess_m3,
                    "travel_delay_seconds": obligation[
                        "travel_delay_seconds"
                    ],
                    "minimum_delivery_fraction": obligation[
                        "minimum_delivery_fraction"
                    ],
                    "maximum_delivery_fraction": obligation[
                        "maximum_delivery_fraction"
                    ],
                    "path_reach_ids_document_text": canonical_json_text(
                        obligation["path_reach_ids"]
                    ),
                    "rotation_windows_document_text": canonical_json_text(
                        [
                            {
                                "starts_at": canonical_instant(
                                    window.starts_at
                                ),
                                "ends_at": canonical_instant(window.ends_at),
                            }
                            for window in policy.rotation_windows
                        ]
                    ),
                }
            records.append(
                RequirementRecord(
                    requirement_id=UUID(requirement_id),
                    run_id=UUID(item["run_id"]),
                    source_version=item["version"],
                    service_date=item["service_date"],
                    section_id=item["section_id"],
                    zone=item["zone"],
                    required_volume_m3=item["required_volume_m3"],
                    window_start=item["window_start"],
                    window_end=item["window_end"],
                    quality=item["quality"],
                    published_at=item["published_at"],
                    as_of_date=item["as_of_date"],
                    source_data_status=item["data_status"],
                    requirement_document_text=canonical_json_text(
                        self._requirement_document(item)
                    ),
                    **planning,
                )
            )
        return tuple(records)

    @staticmethod
    def _event_records(
        plan: LimitedAdjustmentPlan,
        candidate_flow: dict[tuple[str, float], float],
    ) -> tuple[GateEventRecord, ...]:
        records = []
        gate_sequence: dict[str, int] = defaultdict(int)
        trim_count: dict[str, int] = defaultdict(int)
        for index, event in enumerate(plan.events, start=1):
            gate_sequence[event.gate_id] += 1
            if event.kind is GateEventKind.CLOSE:
                flow = 0.0
                trim_ordinal = None
            else:
                flow = candidate_flow[
                    (event.gate_id, event.target_position_m)
                ]
                if event.kind is GateEventKind.TRIM:
                    trim_count[event.gate_id] += 1
                    trim_ordinal = trim_count[event.gate_id]
                else:
                    trim_ordinal = None
            records.append(
                GateEventRecord(
                    event_sequence=index,
                    gate_event_sequence=gate_sequence[event.gate_id],
                    gate_id=event.gate_id,
                    event_kind=event.kind.value,
                    planned_at=event.planned_at,
                    target_position_m=event.target_position_m,
                    source_flow_m3s=flow,
                    trim_ordinal=trim_ordinal,
                )
            )
        return tuple(records)


def parse_member_summaries(record: DraftPlanRecord) -> list[dict[str, Any]]:
    if record.prediction_member_summaries is None:
        return []
    return json.loads(record.prediction_member_summaries)
