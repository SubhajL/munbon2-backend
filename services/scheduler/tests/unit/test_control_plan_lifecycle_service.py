"""Lifecycle orchestration: transitions, approval freeze, supersede, races."""

from functools import partial

import pytest

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from core.control_plan_lifecycle import (
    ApprovalCoverageError,
    IllegalTransitionError,
)
from repositories.control_plan_repository import TransitionConflictError
from schemas.control_plan import DraftControlPlanRequest
from services.control_plan_lifecycle_service import (
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
    repository, volume=6000.0, flow=None, run_id=None, version=3
):
    items = [requirement_item(volume=volume, run_id=run_id, version=version)]
    payload = draft_payload()
    if run_id is not None:
        payload["requirement_run_id"] = str(run_id)
    if version != 3:
        payload["requirement_version"] = version
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
        # and share the SEC-1/G1 physical scope, but differ in volume so they are
        # distinct content-addressed plans.
        a = await _make_draft(repo, volume=6000.0)
        b = await _make_draft(repo, volume=6100.0)
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
        return a, b, svc

    @pytest.mark.asyncio
    async def test_supersede_same_scope_retires_old(self):
        repo = FakeRepository()
        a, b, svc = await self._two_approved(repo)
        superseded = await svc.supersede_control_plan(
            None, a.plan_id, 1, b.plan_id, 1, "op", "roll"
        )
        assert current_lifecycle_state(superseded) == "superseded"
        # The successor stays approved.
        assert current_lifecycle_state(
            await repo.load_draft_plan(None, b.plan_id, 1)
        ) == "approved_for_shadow"

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
