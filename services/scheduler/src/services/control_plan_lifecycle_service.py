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

from core.activation_freeze import (
    activation_document_text,
    build_activation_document,
    build_activation_freeze,
)
from core.auth import is_trusted_shadow_approval
from core.canonical_json import canonicalize
from core.command_intent import (
    command_intent_content_hash,
    compile_command_intents,
)
from core.control_plan_lifecycle import (
    STATE_ACTIVATED,
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
from core.device_capabilities import empty_device_capability_snapshot
from core.predicted_delivery_ledger import predicted_delivery_ledger_sha256
from repositories.control_plan_repository import (
    DraftPlanRecord,
    OutboxRow,
    ScopeRow,
    TransitionRecord,
)


class PlanNotFoundError(Exception):
    """No stored plan carries the requested id/version."""


class SupersedeScopeError(Exception):
    """The successor plan is not a valid supersede for the target."""


class ActivationNotAllowedError(Exception):
    """The plan cannot be activated (untrusted approval, no intents, or no freeze)."""


class ControlPlanLifecycleService:
    def __init__(
        self,
        *,
        repository,
        clock: Callable[[], datetime] = None,
        device_capability_snapshot=None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # The exact 6.1a capability snapshot loaded at startup. The empty dark
        # default (zero machine-capable gates) makes every gate a non-member, so an
        # unconfigured deploy fails closed at activation.
        self._snapshot = (
            device_capability_snapshot
            if device_capability_snapshot is not None
            else empty_device_capability_snapshot()
        )

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

    async def activate_control_plan(
        self,
        session,
        plan_id,
        plan_version,
        actor_subject,
        reason=None,
        authorization_evidence: Optional[dict] = None,
    ) -> DraftPlanRecord:
        """Activate a strict-TRUSTED approved v2 plan: compile its command intents,
        write them to the append-only outbox, take the one-per-scope authority mutex,
        and append the shadow_activated transition granting machine authority — all
        atomically. Fails closed unless the plan is approved_for_shadow, its approval
        is trusted (strict policy), its freeze still matches, it is v2, and every gate
        event is an exact capability member."""
        record = await self._load(session, plan_id, plan_version)
        current = derive_control_plan_state(record.transitions)
        # Raises IllegalTransitionError unless current == approved_for_shadow.
        target = next_state(current, "shadow_activated")

        approval = _shadow_approval_transition(record)
        if approval is None:
            raise ActivationNotAllowedError("the plan has no shadow-approval freeze")
        try:
            approval_document = json.loads(approval.transition_document_text)
        except (TypeError, ValueError) as error:
            raise LifecycleHistoryCorruptError(
                f"approval document is not valid JSON: {error}"
            ) from error
        # Trust gate: only a strict-policy shadow approval may be activated (compat
        # approvals are untrusted, so activation stays dark by default).
        if not is_trusted_shadow_approval(approval_document):
            raise ActivationNotAllowedError(
                "shadow approval is not a trusted (strict-policy) approval"
            )
        requirement_set_sha256 = self._requirement_set_hash(record)
        # The approval freeze must still match the immutable rows.
        verify_shadow_approval_freeze(
            approval.transition_document_text,
            record,
            ledger_sha256=predicted_delivery_ledger_sha256(record.ledger_entries),
            requirement_set_sha256=requirement_set_sha256,
        )

        activation_sequence = len(record.transitions) + 1
        # Deterministic, replay-stable request id for the intents (activation happens
        # at most once per plan — the state machine blocks re-activation).
        request_id = (
            f"activation.{record.plan_id}.{record.plan_version}.{activation_sequence}"
        )
        intents = compile_command_intents(
            record,
            self._snapshot,
            activation_sequence=activation_sequence,
            request_id=request_id,
            requirement_set_sha256=requirement_set_sha256,
        )
        if not intents:
            raise ActivationNotAllowedError("the plan has no gate events to activate")

        freeze = build_activation_freeze(
            record,
            snapshot=self._snapshot,
            intents=intents,
            requirement_set_sha256=requirement_set_sha256,
            approval_transition_sequence=approval.transition_sequence,
        )
        document = build_activation_document(freeze, authorization_evidence or {})
        transition = TransitionRecord(
            transition_sequence=activation_sequence,
            transition_type="shadow_activated",
            from_state=current,
            to_state=target,
            actor_subject=actor_subject,
            reason=reason,
            transition_document_text=activation_document_text(document),
            occurred_at=self._clock(),
        )
        await self._repository.insert_activation(
            session,
            plan_id=record.plan_id,
            plan_version=record.plan_version,
            transition=transition,
            outbox_rows=_build_outbox_rows(record, intents, activation_sequence),
            scope_rows=_build_scope_rows(record, activation_sequence),
        )
        return await self._load(session, record.plan_id, record.plan_version)

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
        current = derive_control_plan_state(record.transitions)
        if current == STATE_ACTIVATED:
            # Emergency-invalidate an ACTIVE plan: append the transition AND release
            # its authority mutex atomically, so leaving shadow_active never orphans
            # the scope (which would brick it against future activations).
            transition = TransitionRecord(
                transition_sequence=len(record.transitions) + 1,
                transition_type="invalidated",
                from_state=current,
                to_state=next_state(current, "invalidated"),
                actor_subject=actor_subject,
                reason=reason,
                transition_document_text=None,
                occurred_at=self._clock(),
            )
            await self._repository.append_transition_and_release_scope(
                session,
                plan_id=record.plan_id,
                plan_version=record.plan_version,
                transition=transition,
            )
            return await self._load(session, record.plan_id, record.plan_version)
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


def _build_outbox_rows(record, intents, activation_sequence: int) -> list:
    event_by_sequence = {event.event_sequence: event for event in record.events}
    rows = []
    for intent in intents:
        event = event_by_sequence[intent.event_sequence]
        rows.append(
            OutboxRow(
                intent_id=UUID(intent.intent_id),
                correlation_id=UUID(intent.correlation_id),
                request_id=intent.request_id,
                idempotency_key=intent.idempotency_key,
                canonical_gate_id=intent.canonical_gate_id,
                event_kind=intent.event_kind,
                event_sequence=intent.event_sequence,
                gate_event_sequence=intent.gate_event_sequence,
                device_id=intent.device_id,
                adapter_gate_id=intent.adapter_gate_id,
                capability_release_id=intent.capability_release_id,
                capability_hash=intent.capability_hash,
                target_position_m=intent.target_position_m,
                target_level=intent.target_level,
                not_before=event.planned_at,
                deadline=record.horizon_end,
                mode=intent.mode,
                intent_document_text=canonicalize(intent.model_dump()),
                intent_content_hash=command_intent_content_hash(intent),
                activation_transition_sequence=activation_sequence,
            )
        )
    return rows


def _build_scope_rows(record, activation_sequence: int) -> list:
    scope = _physical_scope(record)
    for section_id, gate_id in scope:
        if section_id is None or gate_id is None:
            # The mutex columns are NOT NULL; a scheduled requirement without a
            # concrete (section, gate) cannot take authority — fail closed (409),
            # never a NULL-violation 500. Not reachable today (composition always
            # assigns a gate_id), but a cheap defense-in-depth guard.
            raise ActivationNotAllowedError(
                "a scheduled requirement is missing its section/gate scope"
            )
    return [
        ScopeRow(
            section_id=section_id,
            gate_id=gate_id,
            activation_transition_sequence=activation_sequence,
        )
        for section_id, gate_id in sorted(scope)
    ]


def _shadow_approval_transition(record: DraftPlanRecord):
    for transition in record.transitions:
        if transition.transition_type == "shadow_approved":
            return transition
    return None


def current_lifecycle_state(record: DraftPlanRecord) -> str:
    return derive_control_plan_state(record.transitions)
