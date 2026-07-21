"""Execution-authority grant orchestration (PR 7.1a).

Assembles the evidence context (stored plan record, DERIVED lifecycle state,
the CONFIGURED capability snapshot, 0010 receipt coverage), runs the pure
fail-closed validation + the 7.2 execution-predicate preflight, and persists
the immutable grant row + append-only lifecycle events through the repository.

AUTHZ SAFETY VALENCE (enforced here in addition to the endpoint gates):
grant and renew REQUIRE a strict-complete actor evidence (impossible in compat
deployments); revoke deliberately does NOT — removal of authority must always
work. NOTHING here executes: success only ever permits persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple
from uuid import UUID, uuid4

from core.auth import is_trusted_authorization_evidence
from core.authority_grant import (
    AUTHORITY_GRANT_SCHEMA_VERSION,
    EVENT_GRANTED,
    EVENT_RENEWED,
    EVENT_REVOKED,
    STATUS_ACTIVE,
    AuthorityEvidenceCorruptError,
    AuthorityEvidenceError,
    AuthorityGrantCandidate,
    AuthorityHistoryCorruptError,
    ExecutionAuthorityError,
    build_grant_document,
    derive_authority_grant_status,
    grant_content_sha256,
    intent_set_sha256,
    plan_scope_document,
    required_authority_envelope,
    stored_release_is_commandable,
    validate_authority_evidence,
    validate_evidence_set,
    verify_command_intent_row,
    verify_execution_authority,
)
from core.canonical_json import canonicalize, sha256_hex
from core.config import settings
from core.control_plan_lifecycle import derive_control_plan_state
from core.logger import get_logger
from repositories.control_plan_repository import (
    AuthorityEvidenceStoreCorruptError,
    AuthorityGrantEventRow,
    AuthorityGrantRow,
    AuthorityRevocationConflictError,
)

logger = get_logger(__name__)


class UnknownPlanForGrantError(Exception):
    """The named plan version does not exist — nothing to authorize."""


class UnknownAuthorityGrantError(Exception):
    """The named grant does not exist."""


class RenewalNotAllowedError(Exception):
    """The grant is not in a renewable state (expired/revoked/plan retired)."""


@dataclass(frozen=True)
class AuthorityEvidenceContext:
    """Everything grant-time validation reads; assembled here, consumed pure."""

    record: Any
    derived_lifecycle_state: str
    snapshot: Any
    outbox_intent_count: int
    accepted_receipt_intent_count: int
    matching_receipt_intent_count: int
    # The plan's immutable outbox rows (canonical_gate_id + intent_content_hash)
    # — the SERVER-derived intent-set binding source; never request-supplied.
    outbox_intents: Tuple[Any, ...] = ()


@dataclass(frozen=True)
class AuthorityGrantView:
    grant: AuthorityGrantRow
    events: Tuple[AuthorityGrantEventRow, ...]
    status: str
    effective_expires_at: datetime


@dataclass(frozen=True)
class _PreflightExecutionContext:
    plan_id: UUID
    plan_version: int
    model_release_id: str
    model_release_content_hash: str
    engine_descriptor_content_hash: str
    capability_release_id: str
    capability_hash: str
    derived_lifecycle_state: str
    intents: Tuple[Any, ...]


class AuthorityGrantService:
    def __init__(
        self,
        repository,
        *,
        snapshot,
        lease_hours: Optional[int] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self._repository = repository
        self._snapshot = snapshot
        self._lease_hours = (
            lease_hours
            if lease_hours is not None
            else settings.control_authority_lease_hours
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def _load_context(
        self, session, plan_id: UUID, plan_version: int
    ) -> AuthorityEvidenceContext:
        record = await self._repository.load_draft_plan(session, plan_id, plan_version)
        if record is None:
            raise UnknownPlanForGrantError(
                f"plan {plan_id} v{plan_version} does not exist"
            )
        counts = await self._repository.load_authority_evidence_counts(
            session, plan_id, plan_version
        )
        outbox_intents = tuple(
            await self._repository.load_command_outbox(session, plan_id, plan_version)
        )
        if len(outbox_intents) != counts.outbox_intent_count:
            raise AuthorityEvidenceStoreCorruptError(
                "the outbox listing and its count disagree — store view is "
                "inconsistent"
            )
        return AuthorityEvidenceContext(
            record=record,
            derived_lifecycle_state=derive_control_plan_state(record.transitions),
            snapshot=self._snapshot,
            outbox_intent_count=counts.outbox_intent_count,
            accepted_receipt_intent_count=counts.accepted_receipt_intent_count,
            matching_receipt_intent_count=counts.matching_receipt_intent_count,
            outbox_intents=outbox_intents,
        )

    @staticmethod
    def _require_actor_identity(
        authorization_evidence: Mapping, actor_subject: str
    ) -> None:
        if (
            not isinstance(authorization_evidence, Mapping)
            or authorization_evidence.get("subject") != actor_subject
        ):
            raise AuthorityEvidenceError(
                "evidence_incomplete",
                "the authorization evidence subject does not match the actor",
            )

    @staticmethod
    def _require_trusted_actor(
        authorization_evidence: Mapping, actor_subject: str
    ) -> None:
        AuthorityGrantService._require_actor_identity(
            authorization_evidence, actor_subject
        )
        if (
            not is_trusted_authorization_evidence(authorization_evidence)
            or authorization_evidence.get("authorization_policy_version")
            != settings.control_plan_authorization_policy_version
        ):
            raise AuthorityEvidenceError(
                "evidence_incomplete",
                "the acting principal's authorization evidence is not "
                "strict-complete",
            )

    @staticmethod
    def _intent_hashes(context: AuthorityEvidenceContext) -> Tuple[str, ...]:
        return tuple(row.intent_content_hash for row in context.outbox_intents)

    def _preflight(
        self, candidate: AuthorityGrantCandidate, context: AuthorityEvidenceContext
    ) -> None:
        """Run the EXACT 7.2 predicate against the would-be stored grant.

        The execution context is built from the STORED record + immutable
        outbox + CONFIGURED snapshot (the truth 7.2 will see), never from
        request fields."""
        now = self._clock()
        intent_hashes = self._intent_hashes(context)
        grant_stub = _GrantPredicateStub(candidate, intent_content_hashes=intent_hashes)
        birth = _EventStub(1, EVENT_GRANTED, candidate.expires_at, now)
        record = context.record
        execution_context = _PreflightExecutionContext(
            plan_id=record.plan_id,
            plan_version=record.plan_version,
            model_release_id=record.model_release_id,
            model_release_content_hash=record.model_release_content_hash,
            engine_descriptor_content_hash=record.engine_descriptor_content_hash,
            capability_release_id=context.snapshot.capability_release_id,
            capability_hash=context.snapshot.capability_hash,
            derived_lifecycle_state=context.derived_lifecycle_state,
            intents=context.outbox_intents,
        )
        verify_execution_authority(grant_stub, [birth], execution_context, now=now)

    async def get_authority_applicability(
        self, session, plan_id: UUID, plan_version: int
    ) -> dict:
        """Project all server-owned evidence that determines grant readiness."""
        context = await self._load_context(session, plan_id, plan_version)
        record = context.record
        snapshot = context.snapshot
        try:
            verified_intents = tuple(
                verify_command_intent_row(row) for row in context.outbox_intents
            )
            sequences = [intent.event_sequence for intent in verified_intents]
            if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
                raise ValueError("intent event sequences are not strictly ordered")
            for intent in verified_intents:
                lineage = intent.lineage
                if (
                    lineage.plan_id != str(record.plan_id)
                    or lineage.plan_version != record.plan_version
                    or lineage.model_release_id != record.model_release_id
                    or lineage.model_release_content_hash
                    != record.model_release_content_hash
                    or lineage.engine_descriptor_content_hash
                    != record.engine_descriptor_content_hash
                ):
                    raise ValueError("intent lineage does not match its plan")
        except (AttributeError, TypeError, ValueError) as error:
            raise AuthorityEvidenceCorruptError(
                "stored command-intent evidence is corrupt"
            ) from error
        commandable = stored_release_is_commandable(record)
        capability_configured = bool(snapshot.capabilities)
        capability_matches_outbox = bool(verified_intents) and all(
            intent.capability_release_id == snapshot.capability_release_id
            and intent.capability_hash == snapshot.capability_hash
            for intent in verified_intents
        )
        scope = plan_scope_document(record)
        scope_gates = {entry["canonical_gate_id"] for entry in scope["gate_paths"]}
        receipt_coverage_complete = context.outbox_intent_count > 0 and (
            context.accepted_receipt_intent_count == context.outbox_intent_count
            and context.matching_receipt_intent_count == context.outbox_intent_count
        )
        existing = await self.get_authority_grant_for_plan(
            session, plan_id, plan_version
        )
        blockers = []
        if context.derived_lifecycle_state != "shadow_active":
            blockers.append("plan_not_shadow_active")
        if not commandable:
            blockers.append("noncommandable_release")
        if not capability_configured:
            blockers.append("capability_unconfigured")
        if not capability_matches_outbox:
            blockers.append("capability_stale")
        if not scope_gates or not scope_gates.issubset(snapshot.capabilities):
            blockers.append("scope_unapproved_gate")
        if not receipt_coverage_complete:
            blockers.append("receipt_coverage_incomplete")
        envelope = required_authority_envelope(record)
        if envelope["flow_upper_inclusive_m3s"] <= 0:
            blockers.append("plan_envelope_empty")
        if existing is not None:
            blockers.append("grant_already_exists")
        return {
            "plan_id": record.plan_id,
            "plan_version": record.plan_version,
            "evaluated_at": self._clock(),
            "lifecycle_state": context.derived_lifecycle_state,
            "model_release_id": record.model_release_id,
            "model_release_content_hash": record.model_release_content_hash,
            "engine_descriptor_content_hash": record.engine_descriptor_content_hash,
            "model_release_commandable": commandable,
            "capability_release_id": snapshot.capability_release_id,
            "capability_hash": snapshot.capability_hash,
            "capability_configured": capability_configured,
            "capability_matches_outbox": capability_matches_outbox,
            "scope": scope,
            **envelope,
            "outbox_intent_count": context.outbox_intent_count,
            "accepted_receipt_intent_count": (context.accepted_receipt_intent_count),
            "matching_receipt_intent_count": context.matching_receipt_intent_count,
            "receipt_coverage_complete": receipt_coverage_complete,
            "existing_grant_status": None if existing is None else existing.status,
            "existing_grant_id": (
                None if existing is None else existing.grant.grant_id
            ),
            "blockers": tuple(blockers),
            "can_grant": not blockers,
        }

    async def review_authority_grant(
        self, session, candidate: AuthorityGrantCandidate
    ) -> str:
        """Dry-run the FULL grant validation; persists nothing. Returns the
        content digest the grant WOULD carry (the replay-idempotency key)."""
        context = await self._load_context(
            session, candidate.plan_id, candidate.plan_version
        )
        validate_authority_evidence(
            candidate, context, now=self._clock(), lease_hours=self._lease_hours
        )
        self._preflight(candidate, context)
        return grant_content_sha256(
            build_grant_document(
                candidate, intent_content_hashes=self._intent_hashes(context)
            )
        )

    async def grant_execution_authority(
        self,
        session,
        candidate: AuthorityGrantCandidate,
        *,
        actor_subject: str,
        reason: str,
        authorization_evidence: Mapping,
    ) -> AuthorityGrantView:
        self._require_trusted_actor(authorization_evidence, actor_subject)
        context = await self._load_context(
            session, candidate.plan_id, candidate.plan_version
        )
        now = self._clock()
        validate_authority_evidence(
            candidate, context, now=now, lease_hours=self._lease_hours
        )
        self._preflight(candidate, context)
        intent_hashes = self._intent_hashes(context)
        intent_set_digest = intent_set_sha256(intent_hashes)
        document = build_grant_document(candidate, intent_content_hashes=intent_hashes)
        grant_id = uuid4()
        grant = AuthorityGrantRow(
            grant_id=grant_id,
            authority_schema_version=AUTHORITY_GRANT_SCHEMA_VERSION,
            plan_id=candidate.plan_id,
            plan_version=candidate.plan_version,
            model_release_id=candidate.model_release_id,
            model_release_content_hash=candidate.model_release_content_hash,
            engine_descriptor_content_hash=(candidate.engine_descriptor_content_hash),
            model_release_commandable=True,  # validated; DB CHECK backstops
            commandability_evidence_document_text=canonicalize(
                dict(candidate.commandability_evidence)
            ),
            commandability_evidence_sha256=sha256_hex(
                canonicalize(dict(candidate.commandability_evidence))
            ),
            capability_release_id=candidate.capability_release_id,
            capability_hash=candidate.capability_hash,
            scope_document_text=canonicalize(dict(candidate.scope)),
            scope_sha256=sha256_hex(canonicalize(dict(candidate.scope))),
            intent_set_sha256=intent_set_digest,
            flow_lower_exclusive_m3s=candidate.flow_lower_exclusive_m3s,
            flow_upper_inclusive_m3s=candidate.flow_upper_inclusive_m3s,
            initialization_document_text=canonicalize(dict(candidate.initialization)),
            initialization_sha256=sha256_hex(
                canonicalize(dict(candidate.initialization))
            ),
            maximum_continuous_open_seconds=(candidate.maximum_continuous_open_seconds),
            maximum_intermediate_trims=candidate.maximum_intermediate_trims,
            grant_document_text=canonicalize(document),
            grant_content_sha256=grant_content_sha256(document),
            created_by_subject=actor_subject,
            request_id=str(authorization_evidence["request_id"]),
        )

        def build_birth() -> AuthorityGrantEventRow:
            locked_now = self._clock()
            validate_authority_evidence(
                candidate,
                context,
                now=locked_now,
                lease_hours=self._lease_hours,
            )
            return self._build_event(
                grant_id,
                1,
                EVENT_GRANTED,
                effective_expires_at=candidate.expires_at,
                shadow_evidence_sha256=candidate.shadow_evidence_sha256,
                hold_drill_evidence_sha256=candidate.hold_drill_evidence_sha256,
                rollback_drill_evidence_sha256=(
                    candidate.rollback_drill_evidence_sha256
                ),
                evidence_manifest=candidate.evidence_manifest,
                actor_subject=actor_subject,
                reason=reason,
                authorization_evidence=authorization_evidence,
                occurred_at=locked_now,
            )

        stored, inserted = await self._repository.insert_authority_grant(
            session, grant, build_birth
        )
        if inserted:
            logger.info(
                "authority grant {} issued for plan {} v{}",
                grant_id,
                candidate.plan_id,
                candidate.plan_version,
            )
        loaded = await self._repository.load_authority_grant(session, stored.grant_id)
        assert loaded is not None  # insert just returned this stored row
        return self._view(*loaded)

    async def renew_authority_grant(
        self,
        session,
        grant_id: UUID,
        *,
        new_expires_at: datetime,
        shadow_evidence_sha256: str,
        hold_drill_evidence_sha256: str,
        rollback_drill_evidence_sha256: str,
        evidence_manifest: Mapping,
        reason: str,
        actor_subject: str,
        authorization_evidence: Mapping,
    ) -> AuthorityGrantView:
        self._require_trusted_actor(authorization_evidence, actor_subject)
        validate_evidence_set(
            shadow_evidence_sha256,
            hold_drill_evidence_sha256,
            rollback_drill_evidence_sha256,
            evidence_manifest,
        )
        loaded = await self._repository.load_authority_grant(session, grant_id)
        if loaded is None:
            raise UnknownAuthorityGrantError(f"grant {grant_id} does not exist")
        grant, grant_events = loaded
        context = await self._load_context(session, grant.plan_id, grant.plan_version)
        if context.derived_lifecycle_state != "shadow_active":
            raise RenewalNotAllowedError(
                f"plan is {context.derived_lifecycle_state!r}, not shadow_active"
            )
        if (
            grant.capability_release_id != context.snapshot.capability_release_id
            or grant.capability_hash != context.snapshot.capability_hash
        ):
            raise AuthorityEvidenceError(
                "capability_mismatch",
                "the configured capability snapshot no longer matches the grant",
            )
        if context.outbox_intent_count <= 0 or (
            context.accepted_receipt_intent_count != context.outbox_intent_count
            or context.matching_receipt_intent_count != context.outbox_intent_count
        ):
            raise AuthorityEvidenceError(
                "receipt_coverage_incomplete",
                "receipt coverage must be re-proven at every renewal",
            )
        execution_context = _PreflightExecutionContext(
            plan_id=context.record.plan_id,
            plan_version=context.record.plan_version,
            model_release_id=context.record.model_release_id,
            model_release_content_hash=context.record.model_release_content_hash,
            engine_descriptor_content_hash=(
                context.record.engine_descriptor_content_hash
            ),
            capability_release_id=context.snapshot.capability_release_id,
            capability_hash=context.snapshot.capability_hash,
            derived_lifecycle_state=context.derived_lifecycle_state,
            intents=context.outbox_intents,
        )
        try:
            verify_execution_authority(
                grant, grant_events, execution_context, now=self._clock()
            )
        except ExecutionAuthorityError as error:
            if error.reason_code == "grant_not_active":
                raise RenewalNotAllowedError(str(error)) from error
            raise

        def build(sequence: int, existing: Sequence) -> AuthorityGrantEventRow:
            # The clock is read INSIDE the locked callback — a stale pre-lock
            # 'now' could resurrect a grant that expired while this request
            # queued on the lock — and CLAMPED to the last event's occurred_at
            # so cross-pod clock skew can never write the non-monotonic ledger
            # the fold reads as corruption. The clamp is conservative for
            # expiry: clamped-now >= raw-now, so a lapsed grant can only look
            # MORE expired, never less.
            if not existing:
                raise AuthorityHistoryCorruptError("grant has no event history")
            now = max(
                self._clock(),
                max(event.occurred_at for event in existing),
            )
            derived = derive_authority_grant_status(existing, now)
            if derived.status != STATUS_ACTIVE:
                raise RenewalNotAllowedError(f"grant is {derived.status}")
            if (
                not (now < new_expires_at <= now + timedelta(hours=self._lease_hours))
                or new_expires_at <= derived.effective_expires_at
            ):
                raise AuthorityEvidenceError(
                    "expiry_invalid",
                    "a renewal must strictly extend within the lease cap",
                )
            return self._build_event(
                grant_id,
                sequence,
                EVENT_RENEWED,
                effective_expires_at=new_expires_at,
                shadow_evidence_sha256=shadow_evidence_sha256,
                hold_drill_evidence_sha256=hold_drill_evidence_sha256,
                rollback_drill_evidence_sha256=rollback_drill_evidence_sha256,
                evidence_manifest=evidence_manifest,
                actor_subject=actor_subject,
                reason=reason,
                authorization_evidence=authorization_evidence,
                occurred_at=now,
            )

        await self._repository.append_authority_grant_event(
            session,
            grant_id,
            build,
            require_shadow_active_plan=(grant.plan_id, grant.plan_version),
        )
        reloaded = await self._repository.load_authority_grant(session, grant_id)
        assert reloaded is not None
        return self._view(*reloaded)

    async def revoke_authority_grant(
        self,
        session,
        grant_id: UUID,
        *,
        reason: str,
        actor_subject: str,
        authorization_evidence: Mapping,
    ) -> AuthorityGrantView:
        """Terminal, idempotent, and deliberately NOT strict-policy gated."""
        self._require_actor_identity(authorization_evidence, actor_subject)
        loaded = await self._repository.load_authority_grant(session, grant_id)
        if loaded is None:
            raise UnknownAuthorityGrantError(f"grant {grant_id} does not exist")

        def build(sequence: int, existing: Sequence) -> AuthorityGrantEventRow:
            if any(event.event_type == EVENT_REVOKED for event in existing):
                raise AuthorityRevocationConflictError(
                    f"grant {grant_id} is already terminally revoked"
                )
            # Locked-clock + monotonic clamp (see the renewal callback). A
            # revoke is NEVER refused for time — the clamp only keeps the
            # ledger's occurred_at nondecreasing under clock skew.
            if not existing:
                raise AuthorityHistoryCorruptError("grant has no event history")
            now = max(
                self._clock(),
                max(event.occurred_at for event in existing),
            )
            return self._build_event(
                grant_id,
                sequence,
                EVENT_REVOKED,
                effective_expires_at=None,
                shadow_evidence_sha256=None,
                hold_drill_evidence_sha256=None,
                rollback_drill_evidence_sha256=None,
                evidence_manifest=None,
                actor_subject=actor_subject,
                reason=reason,
                authorization_evidence=authorization_evidence,
                occurred_at=now,
            )

        try:
            await self._repository.append_authority_grant_event(
                session, grant_id, build
            )
            logger.info("authority grant {} revoked: {}", grant_id, reason)
        except AuthorityRevocationConflictError:
            # An operator mashing the safety button must see the terminal
            # state, never an error.
            pass
        reloaded = await self._repository.load_authority_grant(session, grant_id)
        assert reloaded is not None
        return self._view(*reloaded)

    async def get_authority_grant(
        self, session, grant_id: UUID
    ) -> Optional[AuthorityGrantView]:
        loaded = await self._repository.load_authority_grant(session, grant_id)
        return None if loaded is None else self._view(*loaded)

    async def get_authority_grant_for_plan(
        self, session, plan_id: UUID, plan_version: int
    ) -> Optional[AuthorityGrantView]:
        loaded = await self._repository.load_authority_grant_for_plan(
            session, plan_id, plan_version
        )
        return None if loaded is None else self._view(*loaded)

    def _view(
        self, grant: AuthorityGrantRow, events: Sequence[AuthorityGrantEventRow]
    ) -> AuthorityGrantView:
        derived = derive_authority_grant_status(events, self._clock())
        return AuthorityGrantView(
            grant=grant,
            events=tuple(events),
            status=derived.status,
            effective_expires_at=derived.effective_expires_at,
        )

    @staticmethod
    def _build_event(
        grant_id: UUID,
        sequence: int,
        event_type: str,
        *,
        effective_expires_at: Optional[datetime],
        shadow_evidence_sha256: Optional[str],
        hold_drill_evidence_sha256: Optional[str],
        rollback_drill_evidence_sha256: Optional[str],
        evidence_manifest: Optional[Mapping],
        actor_subject: str,
        reason: str,
        authorization_evidence: Mapping,
        occurred_at: datetime,
    ) -> AuthorityGrantEventRow:
        manifest_text = (
            canonicalize(dict(evidence_manifest))
            if evidence_manifest is not None
            else None
        )
        evidence_text = canonicalize(dict(authorization_evidence))
        document = {
            "schema_version": 1,
            "grant_id": str(grant_id),
            "event_sequence": sequence,
            "event_type": event_type,
            "effective_expires_at": (
                effective_expires_at.isoformat()
                if effective_expires_at is not None
                else None
            ),
            "evidence": (
                {
                    "shadow_evidence_sha256": shadow_evidence_sha256,
                    "hold_drill_evidence_sha256": hold_drill_evidence_sha256,
                    "rollback_drill_evidence_sha256": (rollback_drill_evidence_sha256),
                    "evidence_manifest_sha256": (
                        sha256_hex(manifest_text) if manifest_text is not None else None
                    ),
                }
                if event_type != EVENT_REVOKED
                else None
            ),
            "actor_subject": actor_subject,
            "reason": reason,
            "authorization_evidence_sha256": sha256_hex(evidence_text),
            "occurred_at": occurred_at.isoformat(),
        }
        document_text = canonicalize(document)
        return AuthorityGrantEventRow(
            event_id=uuid4(),
            grant_id=grant_id,
            event_sequence=sequence,
            event_type=event_type,
            effective_expires_at=effective_expires_at,
            shadow_evidence_sha256=shadow_evidence_sha256,
            hold_drill_evidence_sha256=hold_drill_evidence_sha256,
            rollback_drill_evidence_sha256=rollback_drill_evidence_sha256,
            evidence_manifest_document_text=manifest_text,
            evidence_manifest_sha256=(
                sha256_hex(manifest_text) if manifest_text is not None else None
            ),
            actor_subject=actor_subject,
            reason=reason,
            authorization_evidence_document_text=evidence_text,
            authorization_evidence_sha256=sha256_hex(evidence_text),
            event_document_text=document_text,
            event_content_sha256=sha256_hex(document_text),
            occurred_at=occurred_at,
        )


class _GrantPredicateStub:
    """The would-be grant row shape verify_execution_authority reads, built
    from a validated candidate BEFORE persistence."""

    def __init__(
        self,
        candidate: AuthorityGrantCandidate,
        *,
        intent_content_hashes: Sequence[str],
    ):
        document = build_grant_document(
            candidate, intent_content_hashes=intent_content_hashes
        )
        self.intent_set_sha256 = intent_set_sha256(intent_content_hashes)
        self.plan_id = candidate.plan_id
        self.plan_version = candidate.plan_version
        self.model_release_id = candidate.model_release_id
        self.model_release_content_hash = candidate.model_release_content_hash
        self.engine_descriptor_content_hash = candidate.engine_descriptor_content_hash
        self.capability_release_id = candidate.capability_release_id
        self.capability_hash = candidate.capability_hash
        self.scope_document_text = canonicalize(dict(candidate.scope))
        self.grant_document_text = canonicalize(document)
        self.flow_lower_exclusive_m3s = candidate.flow_lower_exclusive_m3s
        self.flow_upper_inclusive_m3s = candidate.flow_upper_inclusive_m3s


class _EventStub:
    def __init__(
        self,
        sequence: int,
        event_type: str,
        expires_at: Optional[datetime],
        occurred_at: datetime,
    ):
        self.event_sequence = sequence
        self.event_type = event_type
        self.effective_expires_at = expires_at
        self.occurred_at = occurred_at
