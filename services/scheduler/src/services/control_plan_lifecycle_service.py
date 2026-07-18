"""Control-plan review lifecycle orchestration (PR 4.3b).

Each action loads the plan, derives the current state from its append-only
transition history, checks the requested edge, and appends exactly one immutable
transition in a single transaction. Shadow approval freezes exact lineage and
grants no machine authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

import json

from core.auth import is_trusted_shadow_approval
from core.control_plan_lifecycle import (
    LifecycleHistoryCorruptError,
    build_shadow_approval_document,
    build_shadow_approval_freeze,
    control_plan_requirement_set_sha256,
    derive_control_plan_state,
    next_state,
    shadow_approval_document_text,
    shadow_approval_freeze_text,
    validate_shadow_approval_coverage,
    verify_shadow_approval_freeze,
)
from core.predicted_delivery_ledger import predicted_delivery_ledger_sha256
from repositories.control_plan_repository import (
    DraftPlanRecord,
    TransitionRecord,
)


class PlanNotFoundError(Exception):
    """No stored plan carries the requested id/version."""


class SupersedeScopeError(Exception):
    """The successor plan is not a valid supersede for the target."""


class ControlPlanLifecycleService:
    def __init__(
        self,
        *,
        repository,
        clock: Callable[[], datetime] = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def _load(
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

    def _requirement_set_hash(self, record: DraftPlanRecord) -> str:
        return control_plan_requirement_set_sha256(
            [
                (str(r.requirement_id), r.requirement_document_text)
                for r in record.requirements
            ]
        )

    async def _append(
        self,
        session: AsyncSession,
        record: DraftPlanRecord,
        transition_type: str,
        actor_subject: str,
        reason: Optional[str],
        document_text: Optional[str],
    ) -> DraftPlanRecord:
        current = derive_control_plan_state(record.transitions)
        target = next_state(current, transition_type)
        occurred_at = self._clock()
        transition = TransitionRecord(
            transition_sequence=len(record.transitions) + 1,
            transition_type=transition_type,
            from_state=current,
            to_state=target,
            actor_subject=actor_subject,
            reason=reason,
            transition_document_text=document_text,
            occurred_at=occurred_at,
        )
        await self._repository.append_state_transition(
            session, record.plan_id, record.plan_version, transition
        )
        return await self._load(
            session, record.plan_id, record.plan_version
        )

    async def review_control_plan(
        self, session, plan_id, plan_version, actor_subject, reason=None
    ) -> DraftPlanRecord:
        record = await self._load(session, plan_id, plan_version)
        return await self._append(
            session, record, "review_requested", actor_subject, reason, None
        )

    async def approve_shadow_plan(
        self,
        session,
        plan_id,
        plan_version,
        actor_subject,
        reason=None,
        authorization_evidence: Optional[dict] = None,
        evidence_refs: Optional[list] = None,
    ) -> DraftPlanRecord:
        record = await self._load(session, plan_id, plan_version)
        # Coverage gate + lineage freeze BEFORE the edge is appended.
        validate_shadow_approval_coverage(record)
        ledger_sha256 = predicted_delivery_ledger_sha256(record.ledger_entries)
        freeze = build_shadow_approval_freeze(
            record,
            ledger_sha256=ledger_sha256,
            requirement_set_sha256=self._requirement_set_hash(record),
        )
        # The endpoint always supplies real strict-mode evidence; internal/test
        # callers may omit it, in which case the v2 wrapper still carries an
        # empty (untrusted) evidence block so the document shape is consistent.
        document = build_shadow_approval_document(
            freeze, authorization_evidence or {}
        )
        return await self._append(
            session,
            record,
            "shadow_approved",
            actor_subject,
            reason,
            shadow_approval_document_text(document),
        )

    async def cancel_control_plan(
        self, session, plan_id, plan_version, actor_subject, reason
    ) -> DraftPlanRecord:
        record = await self._load(session, plan_id, plan_version)
        return await self._append(
            session, record, "cancelled", actor_subject, reason, None
        )

    async def invalidate_control_plan(
        self, session, plan_id, plan_version, actor_subject, reason
    ) -> DraftPlanRecord:
        record = await self._load(session, plan_id, plan_version)
        return await self._append(
            session, record, "invalidated", actor_subject, reason, None
        )

    async def supersede_control_plan(
        self,
        session,
        plan_id,
        plan_version,
        successor_plan_id: UUID,
        successor_plan_version: int,
        actor_subject,
        reason,
    ) -> DraftPlanRecord:
        record = await self._load(session, plan_id, plan_version)
        successor = await self._load(
            session, successor_plan_id, successor_plan_version
        )
        if (
            successor.plan_id == record.plan_id
            and successor.plan_version == record.plan_version
        ):
            raise SupersedeScopeError("a plan cannot supersede itself")
        if derive_control_plan_state(successor.transitions) != (
            "approved_for_shadow"
        ):
            raise SupersedeScopeError(
                "the successor plan is not approved for shadow"
            )
        # The successor's frozen approval must still match its immutable rows.
        approval = _shadow_approval_transition(successor)
        if approval is None:
            raise SupersedeScopeError(
                "the successor has no shadow-approval freeze"
            )
        # Only a strict-policy (trusted) shadow approval may back a supersede: a
        # legacy v1 freeze or a compat-mode v2 approval is not trusted evidence.
        try:
            approval_document = json.loads(approval.transition_document_text)
        except (TypeError, ValueError) as error:
            # A corrupt stored approval document is fail-closed corruption (503),
            # never an opaque 500.
            raise LifecycleHistoryCorruptError(
                f"successor approval document is not valid JSON: {error}"
            ) from error
        if not is_trusted_shadow_approval(approval_document):
            raise SupersedeScopeError(
                "successor approval is not a trusted (strict-policy) shadow "
                "approval"
            )
        verify_shadow_approval_freeze(
            approval.transition_document_text,
            successor,
            ledger_sha256=predicted_delivery_ledger_sha256(
                successor.ledger_entries
            ),
            requirement_set_sha256=self._requirement_set_hash(successor),
        )
        # A superseding plan must control the SAME physical (section, gate) scope
        # — daily lineage may roll (dates/requirement ids differ) but the target
        # of control may not change.
        old_scope = _physical_scope(record)
        new_scope = _physical_scope(successor)
        if not old_scope or old_scope != new_scope:
            raise SupersedeScopeError(
                "the successor does not control the same physical scope"
            )
        # A supersede stays WITHIN one campaign: a rolling plan's successor must be
        # a later version of the SAME campaign (PR 4.4b-4), never a cross-campaign
        # swap. A legacy singleton campaign's id equals its own plan_id. Both ids
        # come from the immutable mapping (populated on every load / fail-closed).
        if record.campaign_id is None or successor.campaign_id is None:
            raise LifecycleHistoryCorruptError(
                "a control plan version is missing its campaign identity"
            )
        if successor.campaign_id != record.campaign_id:
            raise SupersedeScopeError(
                "the successor belongs to a different campaign"
            )
        # A supersede rolls STRICTLY FORWARD within the campaign: the successor must
        # be a LATER version than the target, so an approved earlier version can
        # never retire a newer approved version (which would put stale control back
        # in charge). (campaign_id, plan_version) is unique, so plan_version totally
        # orders a campaign's append-only chain.
        if successor.plan_version <= record.plan_version:
            raise SupersedeScopeError(
                "a plan can only be superseded by a LATER version of its campaign"
            )
        document = shadow_approval_freeze_text(
            {
                "schema_version": 1,
                "superseded_by": {
                    "plan_id": str(successor.plan_id),
                    "plan_version": successor.plan_version,
                    "draft_content_hash": successor.draft_content_hash,
                    "approval_transition_sequence": approval.transition_sequence,
                },
                "physical_scope": sorted(
                    [section, gate] for section, gate in old_scope
                ),
            }
        )
        return await self._append(
            session, record, "superseded", actor_subject, reason, document
        )


def _physical_scope(record: DraftPlanRecord) -> set:
    return {
        (r.section_id, r.gate_id)
        for r in record.requirements
        if r.planning_disposition == "scheduled"
    }


def _shadow_approval_transition(record: DraftPlanRecord):
    for transition in record.transitions:
        if transition.transition_type == "shadow_approved":
            return transition
    return None


def current_lifecycle_state(record: DraftPlanRecord) -> str:
    return derive_control_plan_state(record.transitions)
