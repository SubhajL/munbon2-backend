"""Lifecycle orchestration: transitions, approval freeze, supersede, races."""

import json
from functools import partial

import pytest

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from core.control_plan_lifecycle import (
    ApprovalCoverageError,
    IllegalTransitionError,
)
from repositories.control_plan_repository import (
    ScopeConflictError,
    TransitionConflictError,
)
from schemas.control_plan import DraftControlPlanRequest
from services.control_plan_lifecycle_service import (
    ActivationNotAllowedError,
    ControlPlanLifecycleService,
    PlanNotFoundError,
    SupersedeScopeError,
    current_lifecycle_state,
)
from services.control_plan_service import ControlPlanDraftService
from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)


async def _run_blocking(func, *args, **kwargs):
    return func(*args, **kwargs)


def _draft_service(repository, flow=None, items=None):
    return ControlPlanDraftService(
        ros_client=FakeRosGisClient(items or [requirement_item()]),
        flow_client=flow or FakeControlFlowClient(snapshot_mirror()),
        repository=repository,
        optimizer=partial(
            optimize_limited_adjustment_plan,
            model_step_seconds=3600,
            max_intermediate_trims=1,
            solver_timeout_seconds=60,
        ),
        run_blocking=_run_blocking,
        model_step_seconds=3600,
        max_intermediate_trims=1,
        solver_timeout_seconds=60,
    )


async def _make_draft(
    repository, volume=6000.0, flow=None, run_id=None, version=3, campaign_id=None
):
    items = [requirement_item(volume=volume, run_id=run_id, version=version)]
    payload = draft_payload()
    if run_id is not None:
        payload["requirement_run_id"] = str(run_id)
    if version != 3:
        payload["requirement_version"] = version
    if campaign_id is not None:
        payload["campaign_id"] = str(campaign_id)
    request = DraftControlPlanRequest.model_validate(payload)
    record, _ = await _draft_service(
        repository, flow=flow, items=items
    ).create_draft(None, request, "operator-1")
    return record


def _lifecycle(repository):
    return ControlPlanLifecycleService(repository=repository)


def _strict_evidence(subject="approver"):
    """Strict-policy authorization evidence, as the endpoint would build it, so
    the resulting v2 approval document is a TRUSTED approval."""
    return {
        "authorization_policy_version": "control-plan-rbac-v1",
        "claim_policy_mode": "strict",
        "subject": subject,
        "roles": ["supervisor"],
        "token_identity_sha256": "9" * 64,
        "request_id": "req-1",
        "evidence_refs": ["ticket-1"],
    }


def _lineage_freeze(approval_document_text):
    """Extract the lineage freeze from a v2 approval document."""
    import json

    return json.loads(approval_document_text)["lineage_freeze"]


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_review_then_approve_reaches_approved_and_freezes(self):
        repo = FakeRepository()
        draft = await _make_draft(repo)
        svc = _lifecycle(repo)
        reviewed = await svc.review_control_plan(
            None, draft.plan_id, draft.plan_version, "reviewer"
        )
        assert current_lifecycle_state(reviewed) == "under_review"
        approved = await svc.approve_shadow_plan(
            None,
            draft.plan_id,
            draft.plan_version,
            "approver",
            authorization_evidence=_strict_evidence(),
        )
        assert current_lifecycle_state(approved) == "approved_for_shadow"
        approval = next(
            t
            for t in approved.transitions
            if t.transition_type == "shadow_approved"
        )
        import json

        document = json.loads(approval.transition_document_text)
        assert document["schema_version"] == 2
        # Authorization evidence lives OUTSIDE the recomputed lineage.
        assert document["authorization_evidence"]["claim_policy_mode"] == "strict"
        freeze = document["lineage_freeze"]
        assert "authorization_evidence" not in freeze
        assert freeze["machine_authority_granted"] is False
        assert freeze["plan"]["draft_content_hash"] == draft.draft_content_hash
        assert freeze["prediction"]["prediction_run_id"] == (
            draft.prediction_run_id
        )
        assert len(freeze["ledger"]["ledger_sha256"]) == 64

    @pytest.mark.asyncio
    async def test_loaded_state_derives_from_latest_transition(self):
        repo = FakeRepository()
        draft = await _make_draft(repo)
        svc = _lifecycle(repo)
        await svc.review_control_plan(
            None, draft.plan_id, draft.plan_version, "r"
        )
        loaded = await repo.load_draft_plan(
            None, draft.plan_id, draft.plan_version
        )
        # The run header stays 'draft'; the derived state advanced.
        assert loaded.lifecycle_state == "draft"
        assert current_lifecycle_state(loaded) == "under_review"


class TestIllegalTransitions:
    @pytest.mark.asyncio
    async def test_approve_requires_review(self):
        repo = FakeRepository()
        draft = await _make_draft(repo)
        with pytest.raises(IllegalTransitionError):
            await _lifecycle(repo).approve_shadow_plan(
                None, draft.plan_id, draft.plan_version, "a"
            )

    @pytest.mark.asyncio
    async def test_review_twice_is_illegal(self):
        repo = FakeRepository()
        draft = await _make_draft(repo)
        svc = _lifecycle(repo)
        await svc.review_control_plan(None, draft.plan_id, 1, "r")
        with pytest.raises(IllegalTransitionError):
            await svc.review_control_plan(None, draft.plan_id, 1, "r")

    @pytest.mark.asyncio
    async def test_terminal_state_rejects_further_actions(self):
        repo = FakeRepository()
        draft = await _make_draft(repo)
        svc = _lifecycle(repo)
        await svc.cancel_control_plan(None, draft.plan_id, 1, "op", "done")
        with pytest.raises(IllegalTransitionError):
            await svc.review_control_plan(None, draft.plan_id, 1, "r")

    @pytest.mark.asyncio
    async def test_unknown_plan_is_not_found(self):
        from uuid import uuid4

        with pytest.raises(PlanNotFoundError):
            await _lifecycle(FakeRepository()).review_control_plan(
                None, uuid4(), 1, "r"
            )


class TestCoverageGate:
    @pytest.mark.asyncio
    async def test_member_infeasible_draft_cannot_approve(self):
        repo = FakeRepository()
        flow = FakeControlFlowClient(
            snapshot_mirror(), infeasible_members={"lower"}
        )
        draft = await _make_draft(repo, flow=flow)
        svc = _lifecycle(repo)
        await svc.review_control_plan(None, draft.plan_id, 1, "r")
        with pytest.raises(ApprovalCoverageError):
            await svc.approve_shadow_plan(None, draft.plan_id, 1, "a")


class TestNewRequirementRun:
    @pytest.mark.asyncio
    async def test_new_requirement_run_does_not_replace_approved_plan(self):
        from uuid import uuid4

        repo = FakeRepository()
        a = await _make_draft(repo, volume=6000.0)
        svc = _lifecycle(repo)
        await svc.review_control_plan(None, a.plan_id, 1, "r")
        await svc.approve_shadow_plan(None, a.plan_id, 1, "a")
        # A GENUINELY NEW requirement run (distinct run_id + version) creates a
        # distinct draft and must not touch the approved plan.
        b = await _make_draft(
            repo,
            volume=6000.0,
            run_id=uuid4(),
            version=4,
        )
        assert b.plan_id != a.plan_id
        approved_a = await repo.load_draft_plan(None, a.plan_id, 1)
        assert current_lifecycle_state(approved_a) == "approved_for_shadow"
        assert current_lifecycle_state(b) == "draft"
        # The approved plan's frozen lineage still pins the OLD run.
        approval = next(
            t
            for t in approved_a.transitions
            if t.transition_type == "shadow_approved"
        )
        freeze = _lineage_freeze(approval.transition_document_text)
        assert freeze["requirements"]["requirement_run_id"] == str(
            a.requirement_run_id
        )


class TestSupersede:
    async def _two_approved(self, repo):
        # Both feasible (single-open delivers within [required, required+excess])
        # and share the SEC-1/G1 physical scope. B is the NEXT VERSION of A's
        # campaign (PR 4.4b-4: a supersede rolls forward within one campaign), and
        # differs in volume so it is a distinct content-addressed plan.
        a = await _make_draft(repo, volume=6000.0)
        b = await _make_draft(repo, volume=6100.0, campaign_id=a.campaign_id)
        assert b.campaign_id == a.campaign_id and b.plan_version == 2
        svc = _lifecycle(repo)
        for plan in (a, b):
            await svc.review_control_plan(
                None, plan.plan_id, plan.plan_version, "r"
            )
            await svc.approve_shadow_plan(
                None,
                plan.plan_id,
                plan.plan_version,
                "a",
                authorization_evidence=_strict_evidence(),
            )
        return a, b, svc

    @pytest.mark.asyncio
    async def test_supersede_same_scope_retires_old(self):
        repo = FakeRepository()
        a, b, svc = await self._two_approved(repo)
        superseded = await svc.supersede_control_plan(
            None, a.plan_id, 1, b.plan_id, b.plan_version, "op", "roll"
        )
        assert current_lifecycle_state(superseded) == "superseded"
        # The successor stays approved.
        assert current_lifecycle_state(
            await repo.load_draft_plan(None, b.plan_id, b.plan_version)
        ) == "approved_for_shadow"

    @pytest.mark.asyncio
    async def test_supersede_of_active_plan_with_safe_handover_releases_scope(self):
        repo = FakeRepository()
        a, b, svc = await self._two_approved(repo)
        a = await repo.load_draft_plan(None, a.plan_id, 1)
        act_svc = _activation_service(repo, _snapshot_for(a))
        await act_svc.activate_control_plan(
            None, a.plan_id, 1, "op", authorization_evidence=_strict_evidence()
        )
        assert repo.active_scopes  # incumbent holds the mutex
        superseded = await svc.supersede_control_plan(
            None, a.plan_id, 1, b.plan_id, b.plan_version, "op", "roll"
        )
        assert current_lifecycle_state(superseded) == "superseded"
        assert not repo.active_scopes  # the graceful handover released the scope
        # The core value proposition: the successor can now be activated on the
        # freed scope with no lingering ScopeConflictError.
        b = await repo.load_draft_plan(None, b.plan_id, b.plan_version)
        activated_b = await _activation_service(
            repo, _snapshot_for(b)
        ).activate_control_plan(
            None, b.plan_id, b.plan_version, "op",
            authorization_evidence=_strict_evidence(),
        )
        assert current_lifecycle_state(activated_b) == "shadow_active"
        assert repo.active_scopes

    @pytest.mark.asyncio
    async def test_supersede_of_active_with_unsafe_handover_is_refused_keeps_scope(
        self, monkeypatch
    ):
        # Drive an UNSAFE handover through the REAL supersede service path: it must be
        # refused (HandoverUnsafeError) and leave the incumbent ACTIVE, still holding
        # its authority mutex — never a silent handoff.
        from core.predicted_delivery_ledger import HandoverVerdict
        from services.control_plan_lifecycle_service import HandoverUnsafeError

        repo = FakeRepository()
        a, b, svc = await self._two_approved(repo)
        a = await repo.load_draft_plan(None, a.plan_id, 1)
        await _activation_service(repo, _snapshot_for(a)).activate_control_plan(
            None, a.plan_id, 1, "op", authorization_evidence=_strict_evidence()
        )
        monkeypatch.setattr(
            "services.control_plan_lifecycle_service.gate_handover_verdicts",
            lambda *args, **kwargs: iter(
                [("G1", ["r"], HandoverVerdict(False, ("no_terminal_close_event",)))]
            ),
        )
        with pytest.raises(HandoverUnsafeError):
            await svc.supersede_control_plan(
                None, a.plan_id, 1, b.plan_id, b.plan_version, "op", "roll"
            )
        assert (
            current_lifecycle_state(await repo.load_draft_plan(None, a.plan_id, 1))
            == "shadow_active"
        )
        assert repo.active_scopes  # authority NOT handed off

    @pytest.mark.asyncio
    async def test_supersede_must_roll_forward_within_campaign(self):
        # a is v1, b is v2 of the SAME campaign — both approved, trusted, same
        # physical scope. Retiring the NEWER v2 with the OLDER v1 is rejected: a
        # supersede rolls STRICTLY FORWARD, so an approved earlier version can never
        # retire a newer approved version (which would reinstate stale control).
        repo = FakeRepository()
        a, b, svc = await self._two_approved(repo)
        assert a.plan_version == 1 and b.plan_version == 2
        with pytest.raises(SupersedeScopeError, match="LATER"):
            await svc.supersede_control_plan(
                None,
                b.plan_id,
                b.plan_version,
                a.plan_id,
                a.plan_version,
                "op",
                "roll",
            )
        # The forward direction (v1 retired by v2) is still allowed.
        superseded = await svc.supersede_control_plan(
            None, a.plan_id, a.plan_version, b.plan_id, b.plan_version, "op", "roll"
        )
        assert current_lifecycle_state(superseded) == "superseded"

    @pytest.mark.asyncio
    async def test_supersede_requires_same_campaign(self):
        # A successor that is approved, trusted, and shares the physical scope but
        # belongs to a DIFFERENT campaign (its own fresh campaign, not a version of
        # A's) cannot supersede A — PR 4.4b-4 restricts supersede to one campaign.
        repo = FakeRepository()
        a = await _make_draft(repo, volume=6000.0)
        b = await _make_draft(repo, volume=6100.0)  # a NEW, distinct campaign
        assert b.campaign_id != a.campaign_id
        svc = _lifecycle(repo)
        for plan in (a, b):
            await svc.review_control_plan(None, plan.plan_id, 1, "r")
            await svc.approve_shadow_plan(
                None,
                plan.plan_id,
                1,
                "a",
                authorization_evidence=_strict_evidence(),
            )
        with pytest.raises(SupersedeScopeError, match="campaign"):
            await svc.supersede_control_plan(
                None, a.plan_id, 1, b.plan_id, 1, "op", "roll"
            )
        # A same-campaign successor (version 2 of A) IS accepted.
        c = await _make_draft(repo, volume=6050.0, campaign_id=a.campaign_id)
        await svc.review_control_plan(None, c.plan_id, c.plan_version, "r")
        await svc.approve_shadow_plan(
            None,
            c.plan_id,
            c.plan_version,
            "a",
            authorization_evidence=_strict_evidence(),
        )
        superseded = await svc.supersede_control_plan(
            None, a.plan_id, 1, c.plan_id, c.plan_version, "op", "roll"
        )
        assert current_lifecycle_state(superseded) == "superseded"

    @pytest.mark.asyncio
    async def test_supersede_requires_approved_successor(self):
        repo = FakeRepository()
        a = await _make_draft(repo, volume=6000.0)
        b = await _make_draft(repo, volume=6500.0)
        svc = _lifecycle(repo)
        await svc.review_control_plan(None, a.plan_id, 1, "r")
        await svc.approve_shadow_plan(None, a.plan_id, 1, "a")
        # b is only a draft.
        with pytest.raises(SupersedeScopeError):
            await svc.supersede_control_plan(
                None, a.plan_id, 1, b.plan_id, 1, "op", "roll"
            )

    @pytest.mark.asyncio
    async def test_supersede_self_is_rejected(self):
        repo = FakeRepository()
        a, b, svc = await self._two_approved(repo)
        with pytest.raises(SupersedeScopeError):
            await svc.supersede_control_plan(
                None, a.plan_id, 1, a.plan_id, 1, "op", "roll"
            )

    @pytest.mark.asyncio
    async def test_supersede_rejects_untrusted_compat_successor(self):
        # A successor approved WITHOUT strict-policy evidence (compat/internal)
        # is not trusted evidence and must not be able to back a supersede.
        repo = FakeRepository()
        a = await _make_draft(repo, volume=6000.0)
        b = await _make_draft(repo, volume=6100.0)
        svc = _lifecycle(repo)
        await svc.review_control_plan(None, a.plan_id, 1, "r")
        await svc.approve_shadow_plan(
            None, a.plan_id, 1, "a", authorization_evidence=_strict_evidence()
        )
        await svc.review_control_plan(None, b.plan_id, 1, "r")
        # b is approved but with NO strict evidence -> untrusted v2 document.
        await svc.approve_shadow_plan(None, b.plan_id, 1, "a")
        with pytest.raises(SupersedeScopeError, match="trusted"):
            await svc.supersede_control_plan(
                None, a.plan_id, 1, b.plan_id, 1, "op", "roll"
            )


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_second_append_at_same_sequence_conflicts(self):
        # Two review actions computed against the same draft state both target
        # sequence 2; the second append conflicts (PK backstop).
        repo = FakeRepository()
        draft = await _make_draft(repo)
        from repositories.control_plan_repository import TransitionRecord

        transition = TransitionRecord(
            transition_sequence=2,
            transition_type="review_requested",
            from_state="draft",
            to_state="under_review",
            actor_subject="r",
            reason=None,
            transition_document_text=None,
        )
        await repo.append_state_transition(None, draft.plan_id, 1, transition)
        with pytest.raises(TransitionConflictError):
            await repo.append_state_transition(
                None, draft.plan_id, 1, transition
            )


def _snapshot_for(record):
    """Build a device-capability snapshot pinned to a plan's gate events, so every
    event position is an exact quantizer member (the activation happy-path fixture)."""
    from core.canonical_json import canonicalize, sha256_hex
    from schemas.machine_boundary import DeviceCapabilitySnapshot

    gate_positions = {}
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
    snapshot = {
        "schema_version": 1,
        "capability_release_id": "cap-test",
        "capabilities": capabilities,
    }
    snapshot["capability_hash"] = sha256_hex(
        "munbon:device-capability-snapshot:v1\n" + canonicalize(snapshot)
    )
    return DeviceCapabilitySnapshot(**snapshot)


async def _approved(repo, evidence=None, run_id=None):
    draft = await _make_draft(repo, run_id=run_id)
    svc = _lifecycle(repo)
    await svc.review_control_plan(None, draft.plan_id, draft.plan_version, "reviewer")
    await svc.approve_shadow_plan(
        None,
        draft.plan_id,
        draft.plan_version,
        "approver",
        authorization_evidence=evidence or _strict_evidence(),
    )
    return await repo.load_draft_plan(None, draft.plan_id, draft.plan_version)


def _activation_service(repo, snapshot):
    return ControlPlanLifecycleService(
        repository=repo, device_capability_snapshot=snapshot
    )


class TestActivation:
    @pytest.mark.asyncio
    async def test_activate_writes_intents_takes_mutex_and_grants_authority(self):
        repo = FakeRepository()
        record = await _approved(repo)
        svc = _activation_service(repo, _snapshot_for(record))
        activated = await svc.activate_control_plan(
            None,
            record.plan_id,
            record.plan_version,
            "operator",
            authorization_evidence=_strict_evidence(),
        )
        assert current_lifecycle_state(activated) == "shadow_active"
        outbox = await repo.load_command_outbox(None, record.plan_id, record.plan_version)
        assert len(outbox) == len(record.events)
        assert all(row.mode == "shadow" for row in outbox)
        scopes = await repo.load_active_scopes(None, record.plan_id, record.plan_version)
        assert scopes
        activation = next(
            t for t in activated.transitions if t.transition_type == "shadow_activated"
        )
        document = json.loads(activation.transition_document_text)
        assert document["activation_freeze"]["machine_authority_granted"] is True

    @pytest.mark.asyncio
    async def test_activate_requires_approved_state(self):
        repo = FakeRepository()
        draft = await _make_draft(repo)
        svc = _activation_service(repo, _snapshot_for(draft))
        with pytest.raises(IllegalTransitionError):
            await svc.activate_control_plan(
                None, draft.plan_id, draft.plan_version, "operator"
            )

    @pytest.mark.asyncio
    async def test_activate_rejects_an_untrusted_compat_approval(self):
        repo = FakeRepository()
        compat_evidence = {**_strict_evidence(), "claim_policy_mode": "compat"}
        record = await _approved(repo, evidence=compat_evidence)
        svc = _activation_service(repo, _snapshot_for(record))
        with pytest.raises(ActivationNotAllowedError):
            await svc.activate_control_plan(
                None, record.plan_id, record.plan_version, "operator"
            )

    @pytest.mark.asyncio
    async def test_activate_fails_closed_on_an_empty_snapshot(self):
        from core.device_capabilities import CapabilityMembershipError

        repo = FakeRepository()
        record = await _approved(repo)
        svc = ControlPlanLifecycleService(repository=repo)  # empty dark default
        with pytest.raises(CapabilityMembershipError):
            await svc.activate_control_plan(
                None, record.plan_id, record.plan_version, "operator"
            )

    @pytest.mark.asyncio
    async def test_second_activation_on_the_same_scope_conflicts(self):
        from uuid import uuid4

        repo = FakeRepository()
        record_a = await _approved(repo, run_id=uuid4())
        snapshot = _snapshot_for(record_a)
        await _activation_service(repo, snapshot).activate_control_plan(
            None, record_a.plan_id, record_a.plan_version, "op",
            authorization_evidence=_strict_evidence(),
        )
        record_b = await _approved(repo, run_id=uuid4())
        with pytest.raises(ScopeConflictError):
            await _activation_service(repo, snapshot).activate_control_plan(
                None, record_b.plan_id, record_b.plan_version, "op",
                authorization_evidence=_strict_evidence(),
            )

    @pytest.mark.asyncio
    async def test_invalidating_an_active_plan_releases_the_scope(self):
        repo = FakeRepository()
        record = await _approved(repo)
        svc = _activation_service(repo, _snapshot_for(record))
        await svc.activate_control_plan(
            None, record.plan_id, record.plan_version, "op",
            authorization_evidence=_strict_evidence(),
        )
        assert repo.active_scopes
        invalidated = await svc.invalidate_control_plan(
            None, record.plan_id, record.plan_version, "op", "emergency stop"
        )
        assert current_lifecycle_state(invalidated) == "invalidated"
        assert not repo.active_scopes


def test_build_scope_rows_rejects_a_requirement_missing_its_gate():
    from types import SimpleNamespace

    from services.control_plan_lifecycle_service import _build_scope_rows

    record = SimpleNamespace(
        requirements=[
            SimpleNamespace(
                section_id="sec-1", gate_id=None, planning_disposition="scheduled"
            )
        ]
    )
    with pytest.raises(ActivationNotAllowedError):
        _build_scope_rows(record, 2)


def test_require_safe_handover_isolates_the_missing_terminal_close():
    # The rolling-campaign case the review flagged: a plan that holds a gate OPEN
    # across the horizon (no terminal close) is NOT modeled-safe to hand over. This
    # ISOLATES that reason — the ledger row is SATISFIED + drained in both cases, so
    # the SOLE difference is the terminal close: with it the plan is hand-over-able,
    # without it the supersede is refused. (An empty ledger would mask the close
    # guard behind a 'no_ledger_rows' reason — false assurance.)
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    from core.predicted_delivery_ledger import LedgerEntry
    from services.control_plan_lifecycle_service import (
        HandoverUnsafeError,
        _require_safe_handover,
    )

    when = datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc)
    req_id = "11111111-1111-1111-1111-111111111111"
    requirement = SimpleNamespace(
        planning_disposition="scheduled",
        gate_id="G1",
        section_id="SEC-1",
        requirement_id=req_id,
        required_volume_m3=100.0,
        approved_excess_m3=10.0,
        path_reach_ids_document_text='["r1"]',
        window_start=when,
        window_end=when,
    )
    satisfied_terminal = LedgerEntry(
        requirement_id=req_id,
        section_id="SEC-1",
        checkpoint_index=0,
        checkpoint_at=when,
        status="predicted_fulfilled",
        required_volume_m3=100.0,
        approved_excess_m3=10.0,
        lower_delivered_m3=100.0,
        nominal_delivered_m3=100.0,
        upper_delivered_m3=100.0,
        lower_path_in_transit_m3=0.0,
        nominal_path_in_transit_m3=0.0,
        upper_path_in_transit_m3=0.0,
        checkpoint_reasons=("horizon_end",),
        prediction_run_id="p",
        prediction_response_sha256="s",
        projection_sha256="j",
        projection_document_text="{}",
    )

    def _record(events):
        return SimpleNamespace(
            prediction_status="completed",
            ledger_entries=[satisfied_terminal],
            events=events,
            requirements=[requirement],
        )

    open_event = SimpleNamespace(
        gate_id="G1", event_kind="open", planned_at=when, target_position_m=0.5
    )
    close_event = SimpleNamespace(
        gate_id="G1",
        event_kind="close",
        planned_at=when + timedelta(hours=1),
        target_position_m=0.0,
    )
    # With a terminal close, the satisfied + drained plan IS hand-over-able.
    _require_safe_handover(_record([open_event, close_event]))
    # Holding the gate OPEN across the horizon is the SOLE reason it becomes unsafe.
    with pytest.raises(HandoverUnsafeError):
        _require_safe_handover(_record([open_event]))
