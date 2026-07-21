"""Pure execution-authority grant logic (PR 7.1a).

An authority grant binds ONE immutable plan version to the approved release
identity triple, the commandability evidence, the exact capability release/hash,
the plan's physical gate/path scope, and the approved operating envelope. The
grant's CURRENT status is never stored — it is folded fail-closed from the
append-only event ledger (granted -> renewed* -> revoked) by
``derive_authority_grant_status``, exactly like the plan-lifecycle and
intent-execution folds.

``verify_execution_authority`` is the 7.2-consumable predicate: it preflights
the ENTIRE ordered intent batch (an early gate must never open before a later
out-of-scope intent fails) and raises with a bounded reason vocabulary. In
7.1a its only production callers are the grant-time preflight and the dry-run
review endpoint — it is deliberately NOT imported by the open-loop worker, the
shadow dispatcher, or any machine route, so nothing here can actuate.

Terminology: ``control_active_gate_authority`` (0007) is the SHADOW scope
mutex; this module is EXECUTION authority.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from pydantic import ValidationError

from core.canonical_json import canonicalize, sha256_hex
from schemas.machine_boundary import CommandIntent

AUTHORITY_GRANT_SCHEMA_VERSION = 1

EVENT_GRANTED = "granted"
EVENT_RENEWED = "renewed"
EVENT_REVOKED = "revoked"
EVENT_TYPES = (EVENT_GRANTED, EVENT_RENEWED, EVENT_REVOKED)

STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"
GRANT_STATUSES = (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_REVOKED)

# Bounded grant-time rejection vocabulary (AuthorityEvidenceError.reason).
EVIDENCE_REASONS = (
    "plan_identity_mismatch",
    "plan_not_v2",
    "release_mismatch",
    "noncommandable_release",
    "plan_not_shadow_active",
    "capability_mismatch",
    "scope_unapproved_gate",
    "scope_mismatch",
    "envelope_violation",
    "evidence_incomplete",
    "receipt_coverage_incomplete",
    "expiry_invalid",
)

# Bounded execution-time rejection vocabulary (ExecutionAuthorityError.reason_code).
EXECUTION_REASONS = (
    "grant_not_active",
    "plan_not_executable",
    "release_mismatch",
    "capability_mismatch",
    "scope_exceeded",
    "intent_set_mismatch",
    "intent_batch_mismatch",
    "intent_evidence_corrupt",
    "envelope_violation",
    "evidence_corrupt",
)

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")

# The only initialization contract 7.1a accepts. Wet-state bounds have no
# agreed variables/units yet and require a versioned future contract — an
# invented numeric range here would be false precision over safety data.
DRY_INITIALIZATION = {"kind": "dry"}


class AuthorityHistoryCorruptError(Exception):
    """The append-only grant ledger is contradictory — callers must fail closed."""


class AuthorityEvidenceError(Exception):
    """A grant request failed fail-closed evidence validation."""

    def __init__(self, reason: str, detail: str):
        assert reason in EVIDENCE_REASONS
        super().__init__(f"{reason}: {detail}")
        self.reason = reason


class AuthorityEvidenceCorruptError(Exception):
    """Stored authority evidence is internally inconsistent — fail closed."""


class ExecutionAuthorityError(Exception):
    """Execution authority is absent for a batch — the caller must not execute."""

    def __init__(self, reason_code: str, detail: str):
        assert reason_code in EXECUTION_REASONS
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class DerivedGrantStatus:
    status: str
    effective_expires_at: datetime


@dataclass(frozen=True)
class AuthorityGrantCandidate:
    """A grant request after strict schema parsing, before evidence validation."""

    plan_id: Any
    plan_version: int
    model_release_id: str
    model_release_content_hash: str
    engine_descriptor_content_hash: str
    commandability_evidence: Mapping[str, Any]
    capability_release_id: str
    capability_hash: str
    scope: Mapping[str, Any]
    flow_lower_exclusive_m3s: float
    flow_upper_inclusive_m3s: float
    initialization: Mapping[str, Any]
    maximum_continuous_open_seconds: int
    maximum_intermediate_trims: int
    shadow_evidence_sha256: str
    hold_drill_evidence_sha256: str
    rollback_drill_evidence_sha256: str
    evidence_manifest: Mapping[str, Any]
    expires_at: datetime


def _aware_or_corrupt(value: Optional[datetime], what: str) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise AuthorityHistoryCorruptError(f"{what} is a naive datetime")
    return value


def derive_authority_grant_status(
    events: Sequence, now: datetime
) -> DerivedGrantStatus:
    """Fold the append-only ledger into the ONLY authoritative current status.

    Any contradiction — no sequence-1 granted birth, duplicate/gapped sequences,
    an event after the terminal revocation, a non-extending renewal, a naive
    stored timestamp — raises ``AuthorityHistoryCorruptError`` so every caller
    fails closed rather than guessing."""
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("now must be timezone-aware")
    ordered = sorted(events, key=lambda event: event.event_sequence)
    if not ordered:
        raise AuthorityHistoryCorruptError("grant has no event history")
    effective_expiry: Optional[datetime] = None
    revoked = False
    previous_occurred: Optional[datetime] = None
    for index, event in enumerate(ordered):
        if event.event_sequence != index + 1:
            raise AuthorityHistoryCorruptError(
                f"event sequences are not contiguous at position {index + 1}"
            )
        if revoked:
            raise AuthorityHistoryCorruptError(
                "an event follows the terminal revocation"
            )
        occurred = _aware_or_corrupt(event.occurred_at, "occurred_at")
        if occurred is None:
            raise AuthorityHistoryCorruptError("event has no occurred_at")
        if previous_occurred is not None and occurred < previous_occurred:
            raise AuthorityHistoryCorruptError("event times are not nondecreasing")
        previous_occurred = occurred
        expires = _aware_or_corrupt(event.effective_expires_at, "effective_expires_at")
        is_birth = event.event_sequence == 1
        if is_birth != (event.event_type == EVENT_GRANTED):
            raise AuthorityHistoryCorruptError(
                "the granted birth must be exactly sequence 1"
            )
        if event.event_type in (EVENT_GRANTED, EVENT_RENEWED):
            if expires is None:
                raise AuthorityHistoryCorruptError(
                    f"{event.event_type} event carries no expiry"
                )
            if expires <= occurred:
                raise AuthorityHistoryCorruptError(
                    f"{event.event_type} expiry is not after its occurrence"
                )
            if effective_expiry is not None:
                if occurred >= effective_expiry:
                    raise AuthorityHistoryCorruptError(
                        "a renewal occurred after the prior authority expired"
                    )
                if expires <= effective_expiry:
                    raise AuthorityHistoryCorruptError(
                        "a renewal must strictly extend the effective expiry"
                    )
            effective_expiry = expires
        elif event.event_type == EVENT_REVOKED:
            if expires is not None:
                raise AuthorityHistoryCorruptError("a revocation carries an expiry")
            revoked = True
        else:
            raise AuthorityHistoryCorruptError(
                f"unknown event type {event.event_type!r}"
            )
    assert effective_expiry is not None  # the sequence-1 granted event set it
    if revoked:
        return DerivedGrantStatus(STATUS_REVOKED, effective_expiry)
    if now >= effective_expiry:
        return DerivedGrantStatus(STATUS_EXPIRED, effective_expiry)
    return DerivedGrantStatus(STATUS_ACTIVE, effective_expiry)


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def intent_set_sha256(intent_content_hashes: Sequence[str]) -> str:
    """Order-independent multiset hash over per-intent content hashes.

    Mirrors the activation-freeze intent-set hash: binds a grant to the EXACT
    immutable outbox batch, so an altered/extra/missing intent changes the
    digest and fails the execution predicate structurally."""
    return sha256_hex(canonicalize(sorted(intent_content_hashes)))


def _parse_utc_instant(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("intent instant is not canonical UTC")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise ValueError("intent instant is not timezone-aware")
    return parsed


def verify_command_intent_row(row: Any) -> CommandIntent:
    """Parse one immutable outbox row and bind every typed replica to its document."""
    document_text = getattr(row, "intent_document_text", None)
    content_hash = getattr(row, "intent_content_hash", None)
    if not isinstance(document_text, str) or not _is_sha256(content_hash):
        raise ValueError("intent row has no canonical document/hash")
    try:
        document = json.loads(document_text)
        intent = CommandIntent.model_validate(document)
    except (ValueError, TypeError, ValidationError) as error:
        raise ValueError(
            "intent document violates the CommandIntent contract"
        ) from error
    canonical_text = canonicalize(intent.model_dump())
    if canonical_text != document_text or sha256_hex(canonical_text) != content_hash:
        raise ValueError("intent document is noncanonical or disagrees with its hash")
    replicas = {
        "intent_id": str(row.intent_id),
        "correlation_id": str(row.correlation_id),
        "request_id": row.request_id,
        "idempotency_key": row.idempotency_key,
        "canonical_gate_id": row.canonical_gate_id,
        "event_kind": row.event_kind,
        "event_sequence": row.event_sequence,
        "gate_event_sequence": row.gate_event_sequence,
        "device_id": row.device_id,
        "adapter_gate_id": row.adapter_gate_id,
        "capability_release_id": row.capability_release_id,
        "capability_hash": row.capability_hash,
        "target_position_m": row.target_position_m,
        "target_level": row.target_level,
        "mode": row.mode,
    }
    for field, value in replicas.items():
        if getattr(intent, field) != value:
            raise ValueError(
                f"intent typed replica {field} disagrees with its document"
            )
    for field in ("not_before", "deadline"):
        row_value = getattr(row, field)
        if (
            not isinstance(row_value, datetime)
            or row_value.tzinfo is None
            or row_value.tzinfo.utcoffset(row_value) is None
            or _parse_utc_instant(getattr(intent, field))
            != row_value.astimezone(timezone.utc)
        ):
            raise ValueError(
                f"intent typed replica {field} disagrees with its document"
            )
    return intent


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_HEX.fullmatch(value))


def parse_scope_document(text: str) -> dict:
    """Strict-parse a canonical scope document into {(section, gate): path tuple}.

    Raises ``ValueError`` on ANY malformation — callers map that to their
    fail-closed vocabulary."""
    parsed = json.loads(text)
    if not isinstance(parsed, dict) or parsed.get("schema_version") != 1:
        raise ValueError("scope document must be a schema_version 1 object")
    gate_paths = parsed.get("gate_paths")
    if not isinstance(gate_paths, list) or not gate_paths:
        raise ValueError("scope gate_paths must be a non-empty list")
    scope: dict = {}
    for entry in gate_paths:
        if not isinstance(entry, dict):
            raise ValueError("scope entry must be an object")
        section = entry.get("section_id")
        gate = entry.get("canonical_gate_id")
        path = entry.get("path_reach_ids")
        if not _non_blank(section) or not _non_blank(gate):
            raise ValueError("scope entry has a blank section or gate")
        if not isinstance(path, list) or not all(_non_blank(r) for r in path):
            raise ValueError("scope entry path_reach_ids must be non-blank strings")
        key = (section, gate)
        if key in scope:
            raise ValueError(f"duplicate scope entry for {key}")
        scope[key] = tuple(path)
    return scope


def _plan_scope(record: Any) -> dict:
    """The plan's scheduled physical scope: {(section, gate): path tuple}.

    Mirrors the supersede physical-scope rule ((section_id, gate_id) pairs from
    the immutable requirements); two requirements naming the same pair must
    agree on the hydraulic path."""
    scope: dict = {}
    for requirement in record.requirements:
        gate = getattr(requirement, "gate_id", None)
        if not gate:
            continue
        key = (requirement.section_id, gate)
        raw = getattr(requirement, "path_reach_ids_document_text", None)
        if raw is None:
            path: tuple = ()
        else:
            parsed = json.loads(raw)
            if not isinstance(parsed, list) or not all(_non_blank(r) for r in parsed):
                raise AuthorityEvidenceError(
                    "scope_mismatch",
                    f"requirement path document for {key} is malformed",
                )
            path = tuple(parsed)
        if key in scope and scope[key] != path:
            raise AuthorityEvidenceError(
                "scope_mismatch",
                f"requirements disagree on the hydraulic path for {key}",
            )
        scope[key] = path
    return scope


def plan_scope_document(record: Any) -> dict:
    """Project the immutable plan requirements into the grant scope contract."""
    scope = _plan_scope(record)
    return {
        "schema_version": 1,
        "gate_paths": [
            {
                "section_id": section_id,
                "canonical_gate_id": gate_id,
                "path_reach_ids": list(path_reach_ids),
            }
            for (section_id, gate_id), path_reach_ids in sorted(scope.items())
        ],
    }


def _max_continuous_open_seconds(record: Any) -> float:
    """The longest interval any gate stays open in the plan's schedule.

    A gate that never closes stays open until ``horizon_end`` — a rolling
    campaign cannot hide an unbounded opening from the policy cap."""
    by_gate: dict = {}
    for event in record.events:
        by_gate.setdefault(event.gate_id, []).append(event)
    longest = 0.0
    for events in by_gate.values():
        events.sort(key=lambda event: event.planned_at)
        opened_at: Optional[datetime] = None
        for event in events:
            if event.target_position_m > 0:
                if opened_at is None:
                    opened_at = event.planned_at
            else:
                if opened_at is not None:
                    longest = max(
                        longest, (event.planned_at - opened_at).total_seconds()
                    )
                    opened_at = None
        if opened_at is not None:
            longest = max(longest, (record.horizon_end - opened_at).total_seconds())
    return longest


def required_authority_envelope(record: Any) -> dict:
    """Return the smallest dry envelope that contains the stored plan."""
    positive_flows = [
        float(event.source_flow_m3s)
        for event in record.events
        if event.source_flow_m3s > 0
    ]
    return {
        "flow_lower_exclusive_m3s": 0.0,
        "flow_upper_inclusive_m3s": max(positive_flows, default=0.0),
        "initialization": dict(DRY_INITIALIZATION),
        "maximum_continuous_open_seconds": max(
            1, int(math.ceil(_max_continuous_open_seconds(record)))
        ),
        "maximum_intermediate_trims": record.max_intermediate_trims,
    }


def validate_evidence_set(
    shadow_evidence_sha256: Any,
    hold_drill_evidence_sha256: Any,
    rollback_drill_evidence_sha256: Any,
    evidence_manifest: Any,
) -> None:
    """The shadow/drill evidence completeness a grant AND every renewal must
    re-prove (a renewal never just extends a timestamp). Fail-closed."""
    for name, value in (
        ("shadow_evidence_sha256", shadow_evidence_sha256),
        ("hold_drill_evidence_sha256", hold_drill_evidence_sha256),
        ("rollback_drill_evidence_sha256", rollback_drill_evidence_sha256),
    ):
        if not _is_sha256(value):
            raise AuthorityEvidenceError(
                "evidence_incomplete", f"{name} is not a sha256 hex digest"
            )
    refs = (
        evidence_manifest.get("refs")
        if isinstance(evidence_manifest, Mapping)
        else None
    )
    if (
        not isinstance(refs, list)
        or not refs
        or not all(_non_blank(ref) for ref in refs)
    ):
        raise AuthorityEvidenceError(
            "evidence_incomplete",
            "the evidence manifest carries no non-blank references",
        )


def validate_commandability_evidence(
    evidence: Any,
    *,
    model_release_id: str,
    model_release_content_hash: str,
    engine_descriptor_content_hash: str,
) -> None:
    """Require positive commandability evidence bound to one release triple."""
    if not isinstance(evidence, Mapping):
        raise AuthorityEvidenceError(
            "noncommandable_release", "commandability evidence is not an object"
        )
    if evidence.get("commandable") is not True:
        raise AuthorityEvidenceError(
            "noncommandable_release",
            "the evidence does not declare a commandable release",
        )
    bound = (
        evidence.get("model_release_id"),
        evidence.get("model_release_content_hash"),
        evidence.get("engine_descriptor_content_hash"),
    )
    requested = (
        model_release_id,
        model_release_content_hash,
        engine_descriptor_content_hash,
    )
    if bound != requested:
        raise AuthorityEvidenceError(
            "noncommandable_release",
            "the commandability evidence does not bind the requested release",
        )
    refs = evidence.get("approval_refs")
    if (
        not isinstance(refs, list)
        or not refs
        or not all(_non_blank(ref) for ref in refs)
    ):
        raise AuthorityEvidenceError(
            "noncommandable_release",
            "the commandability evidence carries no approval references",
        )


def _check_commandability_evidence(candidate: AuthorityGrantCandidate) -> None:
    validate_commandability_evidence(
        candidate.commandability_evidence,
        model_release_id=candidate.model_release_id,
        model_release_content_hash=candidate.model_release_content_hash,
        engine_descriptor_content_hash=candidate.engine_descriptor_content_hash,
    )


def _flow_model_snapshot_content_hash(payload: Mapping[str, Any]) -> str:
    """Reproduce Flow's versioned snapshot identity serializer.

    Flow's ``demand_contract.content_hash`` uses sorted compact JSON, not JCS;
    notably it preserves an integer-valued float as ``2.0``. Authority must
    verify the producer's identity rather than silently substitute JCS.
    """
    return sha256_hex(
        json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        )
    )


def _validate_stored_commandable_release(record: Any) -> None:
    """Bind commandability to the content-addressed stored model snapshot.

    A malformed snapshot or one whose identity/release/engine replicas disagree
    is stored-evidence corruption. A structurally valid snapshot whose explicit
    commandability gates are not all true is an ordinary, bounded refusal.
    """
    try:
        stored_snapshot = json.loads(record.model_snapshot_document_text)
    except (ValueError, TypeError, AttributeError) as error:
        raise AuthorityEvidenceCorruptError(
            "the stored model snapshot document is unreadable"
        ) from error
    if not isinstance(stored_snapshot, Mapping):
        raise AuthorityEvidenceCorruptError(
            "the stored model snapshot document is not an object"
        )
    snapshot_id = stored_snapshot.get("snapshot_id")
    payload = dict(stored_snapshot)
    payload.pop("snapshot_id", None)
    if snapshot_id != getattr(
        record, "model_snapshot_id", None
    ) or snapshot_id != _flow_model_snapshot_content_hash(payload):
        raise AuthorityEvidenceCorruptError(
            "the stored model snapshot does not reproduce its pinned identity"
        )
    response_model = stored_snapshot.get("response_model")
    prediction_engine = stored_snapshot.get("prediction_engine")
    action_model = stored_snapshot.get("action_model")
    if (
        not isinstance(response_model, Mapping)
        or not isinstance(prediction_engine, Mapping)
        or not isinstance(action_model, Mapping)
        or response_model.get("release_id") != record.model_release_id
        or response_model.get("content_hash") != record.model_release_content_hash
        or prediction_engine.get("content_hash")
        != record.engine_descriptor_content_hash
    ):
        raise AuthorityEvidenceCorruptError(
            "the stored model snapshot release or engine pins disagree with the plan"
        )
    if not all(
        value is True
        for value in (
            stored_snapshot.get("commandable"),
            response_model.get("commandable"),
            action_model.get("commandable"),
            action_model.get("actuation_approved"),
        )
    ):
        raise AuthorityEvidenceError(
            "noncommandable_release",
            "the stored model snapshot does not authorize command execution",
        )


def stored_release_is_commandable(record: Any) -> bool:
    """Return false for an honest dark release; propagate stored corruption."""
    try:
        _validate_stored_commandable_release(record)
    except AuthorityEvidenceError as error:
        if error.reason == "noncommandable_release":
            return False
        raise
    return True


def validate_authority_evidence(
    candidate: AuthorityGrantCandidate,
    context: Any,
    *,
    now: datetime,
    lease_hours: int,
) -> None:
    """Fail-closed grant-time validation; raises AuthorityEvidenceError.

    ``context`` carries the loaded evidence: the stored plan ``record``
    (verify_stored_draft has already run on load), the DERIVED
    ``derived_lifecycle_state``, the CURRENTLY CONFIGURED capability
    ``snapshot``, and the plan's 0010 receipt-coverage counts. Request evidence
    can never promote anything the stored plan does not already prove."""
    record = context.record
    if (
        candidate.plan_id != record.plan_id
        or candidate.plan_version != record.plan_version
    ):
        raise AuthorityEvidenceError(
            "plan_identity_mismatch", "the candidate names a different plan"
        )
    if (
        getattr(record, "provenance_version", None) != 2
        or not record.engine_descriptor_content_hash
    ):
        raise AuthorityEvidenceError(
            "plan_not_v2",
            "only provenance-v2 plans carry the engine identity a grant must bind",
        )
    stored_triple = (
        record.model_release_id,
        record.model_release_content_hash,
        record.engine_descriptor_content_hash,
    )
    requested_triple = (
        candidate.model_release_id,
        candidate.model_release_content_hash,
        candidate.engine_descriptor_content_hash,
    )
    if stored_triple != requested_triple:
        raise AuthorityEvidenceError(
            "release_mismatch",
            "the candidate release triple does not match the stored plan",
        )
    _validate_stored_commandable_release(record)
    _check_commandability_evidence(candidate)
    if context.derived_lifecycle_state != "shadow_active":
        raise AuthorityEvidenceError(
            "plan_not_shadow_active",
            f"plan is {context.derived_lifecycle_state!r}, not shadow_active",
        )
    snapshot = context.snapshot
    if (
        candidate.capability_release_id != snapshot.capability_release_id
        or candidate.capability_hash != snapshot.capability_hash
    ):
        raise AuthorityEvidenceError(
            "capability_mismatch",
            "the candidate capability pair does not match the configured snapshot",
        )
    if any(
        intent.capability_release_id != candidate.capability_release_id
        or intent.capability_hash != candidate.capability_hash
        for intent in context.outbox_intents
    ):
        raise AuthorityEvidenceError(
            "capability_mismatch",
            "the immutable outbox was compiled under a different capability pair",
        )
    try:
        scope = parse_scope_document(canonicalize(dict(candidate.scope)))
    except ValueError as error:
        raise AuthorityEvidenceError(
            "evidence_incomplete", f"scope document is malformed: {error}"
        ) from error
    for _, gate in scope:
        if gate not in snapshot.capabilities:
            raise AuthorityEvidenceError(
                "scope_unapproved_gate",
                f"gate {gate!r} has no approved device capability",
            )
    if scope != _plan_scope(record):
        raise AuthorityEvidenceError(
            "scope_mismatch",
            "the grant scope does not exactly equal the plan's physical scope",
        )
    if not (
        candidate.flow_lower_exclusive_m3s >= 0
        and candidate.flow_upper_inclusive_m3s > candidate.flow_lower_exclusive_m3s
    ):
        raise AuthorityEvidenceError(
            "envelope_violation", "the flow envelope bounds are not sane"
        )
    for event in record.events:
        flow = event.source_flow_m3s
        if flow > 0 and not (
            candidate.flow_lower_exclusive_m3s
            < flow
            <= candidate.flow_upper_inclusive_m3s
        ):
            raise AuthorityEvidenceError(
                "envelope_violation",
                "a scheduled flow falls outside the approved envelope",
            )
    if candidate.maximum_continuous_open_seconds <= 0:
        raise AuthorityEvidenceError(
            "envelope_violation", "maximum continuous open must be positive"
        )
    if _max_continuous_open_seconds(record) > candidate.maximum_continuous_open_seconds:
        raise AuthorityEvidenceError(
            "envelope_violation",
            "the plan holds a gate open longer than the approved maximum",
        )
    if not (
        0 <= candidate.maximum_intermediate_trims <= 2
        and candidate.maximum_intermediate_trims >= record.max_intermediate_trims
    ):
        raise AuthorityEvidenceError(
            "envelope_violation",
            "the trim policy is outside 0..2 or below the plan's own setting",
        )
    if canonicalize(dict(candidate.initialization)) != canonicalize(DRY_INITIALIZATION):
        raise AuthorityEvidenceError(
            "evidence_incomplete",
            "initialization must be the exact dry contract",
        )
    validate_evidence_set(
        candidate.shadow_evidence_sha256,
        candidate.hold_drill_evidence_sha256,
        candidate.rollback_drill_evidence_sha256,
        candidate.evidence_manifest,
    )
    if context.outbox_intent_count <= 0 or (
        context.accepted_receipt_intent_count != context.outbox_intent_count
        or context.matching_receipt_intent_count != context.outbox_intent_count
    ):
        raise AuthorityEvidenceError(
            "receipt_coverage_incomplete",
            "every outbox intent must hold a matching accepted validation receipt",
        )
    expires_at = candidate.expires_at
    if expires_at.tzinfo is None or expires_at.tzinfo.utcoffset(expires_at) is None:
        raise AuthorityEvidenceError(
            "expiry_invalid", "expires_at must be timezone-aware"
        )
    if not (now < expires_at <= now + timedelta(hours=lease_hours)):
        raise AuthorityEvidenceError(
            "expiry_invalid",
            f"expires_at must be strictly future and within the {lease_hours}h lease",
        )


def build_grant_document(
    candidate: AuthorityGrantCandidate, *, intent_content_hashes: Sequence[str]
) -> dict:
    """The canonical grant document; its hash is the replay-idempotency key.

    ``intent_content_hashes`` is SERVER-derived in immutable outbox order. The
    ordered list prevents open/close reordering; the set digest independently
    binds membership for activation-freeze compatibility."""
    hashes = tuple(intent_content_hashes)
    if not hashes or not all(_is_sha256(value) for value in hashes):
        raise ValueError("intent_content_hashes must be non-empty sha256 values")
    return {
        "schema_version": AUTHORITY_GRANT_SCHEMA_VERSION,
        "plan": {
            "plan_id": str(candidate.plan_id),
            "plan_version": candidate.plan_version,
        },
        "intents": {
            "count": len(hashes),
            "intent_content_hashes": list(hashes),
            "intent_set_sha256": intent_set_sha256(hashes),
        },
        "release": {
            "model_release_id": candidate.model_release_id,
            "model_release_content_hash": candidate.model_release_content_hash,
            "engine_descriptor_content_hash": (
                candidate.engine_descriptor_content_hash
            ),
        },
        "commandability_evidence": dict(candidate.commandability_evidence),
        "capability": {
            "capability_release_id": candidate.capability_release_id,
            "capability_hash": candidate.capability_hash,
        },
        "scope": dict(candidate.scope),
        "envelope": {
            "flow_lower_exclusive_m3s": candidate.flow_lower_exclusive_m3s,
            "flow_upper_inclusive_m3s": candidate.flow_upper_inclusive_m3s,
            "initialization": dict(candidate.initialization),
            "maximum_continuous_open_seconds": (
                candidate.maximum_continuous_open_seconds
            ),
            "maximum_intermediate_trims": candidate.maximum_intermediate_trims,
        },
        "evidence": {
            "shadow_evidence_sha256": candidate.shadow_evidence_sha256,
            "hold_drill_evidence_sha256": candidate.hold_drill_evidence_sha256,
            "rollback_drill_evidence_sha256": (
                candidate.rollback_drill_evidence_sha256
            ),
            "evidence_manifest": dict(candidate.evidence_manifest),
        },
        "expires_at": candidate.expires_at.isoformat(),
    }


def grant_content_sha256(document: Mapping[str, Any]) -> str:
    return sha256_hex(canonicalize(dict(document)))


def _verify_execution_authority_for_status(
    grant: Any,
    events: Sequence,
    execution_context: Any,
    *,
    now: datetime,
    allowed_statuses: frozenset,
):
    try:
        derived = derive_authority_grant_status(events, now)
    except AuthorityHistoryCorruptError as error:
        raise ExecutionAuthorityError("evidence_corrupt", str(error)) from error
    if derived.status not in allowed_statuses:
        raise ExecutionAuthorityError(
            "grant_not_active", f"grant status is {derived.status}"
        )
    if getattr(execution_context, "derived_lifecycle_state", None) != "shadow_active":
        raise ExecutionAuthorityError(
            "plan_not_executable",
            "the plan is not currently shadow_active",
        )
    if (
        grant.plan_id != execution_context.plan_id
        or grant.plan_version != execution_context.plan_version
        or grant.model_release_id != execution_context.model_release_id
        or grant.model_release_content_hash
        != execution_context.model_release_content_hash
        or grant.engine_descriptor_content_hash
        != execution_context.engine_descriptor_content_hash
    ):
        raise ExecutionAuthorityError(
            "release_mismatch",
            "the execution context does not match the granted plan release",
        )
    if (
        grant.capability_release_id != execution_context.capability_release_id
        or grant.capability_hash != execution_context.capability_hash
    ):
        raise ExecutionAuthorityError(
            "capability_mismatch",
            "the execution capability pair does not match the grant",
        )
    try:
        scope = parse_scope_document(grant.scope_document_text)
    except (ValueError, TypeError) as error:
        raise ExecutionAuthorityError(
            "evidence_corrupt", f"stored scope document is corrupt: {error}"
        ) from error
    granted_gates = {gate for _, gate in scope}
    intent_rows = tuple(execution_context.intents)
    if not intent_rows:
        raise ExecutionAuthorityError(
            "scope_exceeded", "an empty batch has nothing the grant authorizes"
        )
    try:
        grant_document = json.loads(grant.grant_document_text)
        intent_evidence = grant_document["intents"]
        granted_hashes = intent_evidence["intent_content_hashes"]
        if (
            not isinstance(granted_hashes, list)
            or intent_evidence.get("count") != len(granted_hashes)
            or not granted_hashes
            or not all(_is_sha256(value) for value in granted_hashes)
            or intent_set_sha256(granted_hashes) != grant.intent_set_sha256
            or intent_evidence.get("intent_set_sha256") != grant.intent_set_sha256
        ):
            raise ValueError("grant intent evidence is inconsistent")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ExecutionAuthorityError(
            "evidence_corrupt", "the grant intent evidence is corrupt"
        ) from error
    try:
        intents = tuple(verify_command_intent_row(row) for row in intent_rows)
    except (AttributeError, TypeError, ValueError) as error:
        raise ExecutionAuthorityError("intent_evidence_corrupt", str(error)) from error
    batch_hashes = [row.intent_content_hash for row in intent_rows]
    if intent_set_sha256(batch_hashes) != grant.intent_set_sha256:
        raise ExecutionAuthorityError(
            "intent_set_mismatch",
            "the batch does not reproduce the granted intent set",
        )
    if batch_hashes != granted_hashes:
        raise ExecutionAuthorityError(
            "intent_batch_mismatch",
            "the batch order does not reproduce the granted intent sequence",
        )
    sequences = [intent.event_sequence for intent in intents]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise ExecutionAuthorityError(
            "intent_batch_mismatch", "intent event sequences are not strictly ordered"
        )
    for intent in intents:
        if intent.canonical_gate_id not in granted_gates:
            raise ExecutionAuthorityError(
                "scope_exceeded",
                f"intent gate {intent.canonical_gate_id!r} is outside the grant",
            )
        if (
            intent.capability_release_id != grant.capability_release_id
            or intent.capability_hash != grant.capability_hash
        ):
            raise ExecutionAuthorityError(
                "capability_mismatch",
                "an intent was compiled under a different capability pair",
            )
        if (
            intent.lineage.plan_id != str(grant.plan_id)
            or intent.lineage.plan_version != grant.plan_version
            or intent.lineage.model_release_id != grant.model_release_id
            or intent.lineage.model_release_content_hash
            != grant.model_release_content_hash
            or intent.lineage.engine_descriptor_content_hash
            != grant.engine_descriptor_content_hash
        ):
            raise ExecutionAuthorityError(
                "release_mismatch", "an intent lineage does not match the grant"
            )
    return intents


def verify_execution_authority(
    grant: Any, events: Sequence, execution_context: Any, *, now: datetime
) -> None:
    """Authorize the whole immutable batch under a currently active grant."""
    _verify_execution_authority_for_status(
        grant,
        events,
        execution_context,
        now=now,
        allowed_statuses=frozenset({STATUS_ACTIVE}),
    )


def verify_fail_safe_close_authority(
    grant: Any,
    events: Sequence,
    execution_context: Any,
    *,
    selected_intent_id: Any,
    is_held: bool,
    now: datetime,
) -> None:
    """Separately authorize only a held plan's close-at-zero after expiry/revoke."""
    if not is_held:
        raise ExecutionAuthorityError(
            "plan_not_executable", "fail-safe close requires an operator-held plan"
        )
    intents = _verify_execution_authority_for_status(
        grant,
        events,
        execution_context,
        now=now,
        allowed_statuses=frozenset({STATUS_EXPIRED, STATUS_REVOKED}),
    )
    selected = next(
        (
            intent
            for intent in intents
            if str(intent.intent_id) == str(selected_intent_id)
        ),
        None,
    )
    if (
        selected is None
        or selected.event_kind != "close"
        or selected.target_position_m != 0
    ):
        raise ExecutionAuthorityError(
            "scope_exceeded",
            "fail-safe authority permits only a granted close-at-zero intent",
        )
