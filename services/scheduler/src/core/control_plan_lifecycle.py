"""Pure control-plan review lifecycle (PR 4.3b).

Event-sourced: the current lifecycle state is derived, fail-closed, from the
append-only ``control_state_transitions`` history. ``control_plan_runs`` stays
immutable, so its ``lifecycle_state`` column is frozen creation metadata and is
never the current-state authority. Shadow approval freezes exact lineage hashes
and grants NO machine authority.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timezone
from typing import Any, Mapping, Optional, Sequence

from core.predicted_delivery_ledger import predicted_delivery_ledger_sha256


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

REQUIREMENT_SET_HASH_PREFIX = "scheduler:control-plan-requirements:v1\n"
APPROVAL_FREEZE_SCHEMA_VERSION = 1
# A v2 (artifact-reference) record freezes engine + artifact identity, so its
# lineage-freeze schema advances to 3 (v1 records keep schema 1).
APPROVAL_FREEZE_SCHEMA_VERSION_V3 = 3
PROVENANCE_VERSION_V2 = 2
_PREDICTION_MEMBERS = frozenset({"lower", "nominal", "upper"})

STATE_DRAFT = "draft"
STATE_UNDER_REVIEW = "under_review"
STATE_APPROVED = "approved_for_shadow"
# PR 4.3c: an approved plan that has been ACTIVATED — its command intents are in the
# outbox and it holds machine authority (shadow mode). Non-terminal.
STATE_ACTIVATED = "shadow_active"
STATE_CANCELLED = "cancelled"
STATE_SUPERSEDED = "superseded"
STATE_INVALIDATED = "invalidated"

LIFECYCLE_STATES = frozenset(
    {
        STATE_DRAFT,
        STATE_UNDER_REVIEW,
        STATE_APPROVED,
        STATE_ACTIVATED,
        STATE_CANCELLED,
        STATE_SUPERSEDED,
        STATE_INVALIDATED,
    }
)
TERMINAL_STATES = frozenset(
    {STATE_CANCELLED, STATE_SUPERSEDED, STATE_INVALIDATED}
)

# (transition_type, from_state, to_state); from_state None only for creation.
_EDGES: frozenset = frozenset(
    {
        ("draft_created", None, STATE_DRAFT),
        ("review_requested", STATE_DRAFT, STATE_UNDER_REVIEW),
        ("shadow_approved", STATE_UNDER_REVIEW, STATE_APPROVED),
        ("cancelled", STATE_DRAFT, STATE_CANCELLED),
        ("cancelled", STATE_UNDER_REVIEW, STATE_CANCELLED),
        ("cancelled", STATE_APPROVED, STATE_CANCELLED),
        ("superseded", STATE_APPROVED, STATE_SUPERSEDED),
        ("invalidated", STATE_DRAFT, STATE_INVALIDATED),
        ("invalidated", STATE_UNDER_REVIEW, STATE_INVALIDATED),
        ("invalidated", STATE_APPROVED, STATE_INVALIDATED),
        # PR 4.3c-1: activate an approved plan; emergency-invalidate an active one
        # (releasing its scope). Supersede-of-active + safe-handover is 4.3c-2.
        ("shadow_activated", STATE_APPROVED, STATE_ACTIVATED),
        ("invalidated", STATE_ACTIVATED, STATE_INVALIDATED),
    }
)
# to_state reachable from a given current state, keyed by transition_type.
TRANSITION_TARGET = {
    ("review_requested", STATE_DRAFT): STATE_UNDER_REVIEW,
    ("shadow_approved", STATE_UNDER_REVIEW): STATE_APPROVED,
    ("cancelled", STATE_DRAFT): STATE_CANCELLED,
    ("cancelled", STATE_UNDER_REVIEW): STATE_CANCELLED,
    ("cancelled", STATE_APPROVED): STATE_CANCELLED,
    ("superseded", STATE_APPROVED): STATE_SUPERSEDED,
    ("invalidated", STATE_DRAFT): STATE_INVALIDATED,
    ("invalidated", STATE_UNDER_REVIEW): STATE_INVALIDATED,
    ("invalidated", STATE_APPROVED): STATE_INVALIDATED,
    ("shadow_activated", STATE_APPROVED): STATE_ACTIVATED,
    ("invalidated", STATE_ACTIVATED): STATE_INVALIDATED,
}


class LifecycleError(ValueError):
    """Base lifecycle failure."""


class LifecycleHistoryCorruptError(LifecycleError):
    """Stored transition history is internally inconsistent (fail closed)."""


class IllegalTransitionError(LifecycleError):
    """The requested action is not a legal edge from the current state."""


class ApprovalCoverageError(LifecycleError):
    """The plan is not in a fully-covered state and cannot be approved."""


class ApprovalFreezeMismatchError(LifecycleError):
    """A frozen approval document no longer matches the immutable plan."""


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def derive_control_plan_state(transitions: Sequence[Any]) -> str:
    """Return the current lifecycle state by validating the whole history.

    The history must begin with exactly one ``draft_created`` at sequence 1,
    have contiguous 1..N sequences, chain each ``from_state`` to the prior
    ``to_state``, and use only declared edges. Any inconsistency is corruption.
    """
    if not transitions:
        raise LifecycleHistoryCorruptError("plan has no transitions")
    ordered = sorted(transitions, key=lambda t: t.transition_sequence)
    previous_to: Optional[str] = None
    for index, transition in enumerate(ordered, start=1):
        if transition.transition_sequence != index:
            raise LifecycleHistoryCorruptError(
                "transition sequence is not contiguous from 1"
            )
        edge = (
            transition.transition_type,
            transition.from_state,
            transition.to_state,
        )
        if edge not in _EDGES:
            raise LifecycleHistoryCorruptError(
                f"transition {edge} is not a declared lifecycle edge"
            )
        if index == 1:
            if transition.from_state is not None:
                raise LifecycleHistoryCorruptError(
                    "the initial transition must have a null from_state"
                )
        elif transition.from_state != previous_to:
            raise LifecycleHistoryCorruptError(
                "transition from_state does not chain to the prior to_state"
            )
        previous_to = transition.to_state
    return previous_to


def next_state(current_state: str, transition_type: str) -> str:
    """The target state for an action, or raise if the edge is illegal."""
    target = TRANSITION_TARGET.get((transition_type, current_state))
    if target is None:
        raise IllegalTransitionError(
            f"{transition_type!r} is not legal from {current_state!r}"
        )
    return target


def control_plan_requirement_set_sha256(
    requirement_pairs: Sequence[tuple[str, str]],
) -> str:
    """Order-independent, domain-separated hash of the requirement set.

    Each pair is (requirement_id, requirement_document_text). Sorting by
    requirement_id makes the set hash independent of row order while still
    pinning every requirement's exact document.
    """
    payload = [
        {
            "requirement_id": requirement_id,
            "requirement_document_sha256": hashlib.sha256(
                document.encode("utf-8")
            ).hexdigest(),
        }
        for requirement_id, document in sorted(requirement_pairs)
    ]
    text = REQUIREMENT_SET_HASH_PREFIX + _canonical(payload)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scheduled_requirements(record: Any) -> list:
    return [
        requirement
        for requirement in record.requirements
        if requirement.planning_disposition == "scheduled"
    ]


_TERMINAL_OK_STATUSES = frozenset(
    {"predicted_fulfilled", "predicted_excess_risk"}
)


def validate_shadow_approval_coverage(record: Any) -> None:
    """Fail closed unless the draft is a fully-covered, feasible, completed
    prediction with a clean ledger whose lineage matches the plan header.
    `predicted_excess_risk` is approvable (shadow grants no authority); a terminal
    `not_started`/`predicted_in_progress` (a projected shortfall) is NOT.

    Dispatches by storage version: a v2 (artifact-reference) record proves
    completion from the bounded member/coverage summaries + ledger WITHOUT the
    full trajectory; a v1 record re-derives it from the persisted response."""
    if getattr(record, "provenance_version", None) == PROVENANCE_VERSION_V2:
        return validate_shadow_approval_coverage_v2(record)
    from core.control_plan import summarize_prediction_status

    if record.optimizer_status != "feasible":
        raise ApprovalCoverageError(
            "only a feasible optimizer result can be approved for shadow"
        )
    if (
        record.prediction_run_id is None
        or record.prediction_response_document_text is None
        or record.prediction_response_sha256 is None
    ):
        raise ApprovalCoverageError("the draft carries no persisted prediction")
    # Re-derive completion from the persisted RESPONSE rather than trusting the
    # stored summary column: this ties approval to the actual prediction bytes.
    try:
        response = json.loads(record.prediction_response_document_text)
    except ValueError as error:
        raise ApprovalCoverageError(
            f"stored prediction response is not valid JSON: {error}"
        ) from error
    try:
        derived_status = summarize_prediction_status(response)
    except Exception as error:  # UpstreamContractError etc.
        raise ApprovalCoverageError(
            f"stored prediction response is malformed: {error}"
        ) from error
    if derived_status != "completed" or record.prediction_status != "completed":
        raise ApprovalCoverageError(
            "shadow approval requires a completed three-member prediction"
        )
    _validate_scheduled_and_ledger(record, record.prediction_response_sha256)


def validate_shadow_approval_coverage_v2(record: Any) -> None:
    """Prove a v2 draft is fully covered WITHOUT the full trajectory.

    Completion is proven from the exact THREE hashed member summaries and the
    bounded coverage summary (whose sha and run id must tie to the header), and
    the ledger's lineage must reference this plan's run + artifact sha256 — never
    a refetch/reparse of the up-to-64 MiB response."""
    if record.optimizer_status != "feasible":
        raise ApprovalCoverageError(
            "only a feasible optimizer result can be approved for shadow"
        )
    if (
        record.prediction_run_id is None
        or record.artifact_sha256 is None
        or record.prediction_member_summaries is None
        or record.coverage_summary_document_text is None
        or record.coverage_summary_sha256 is None
        or record.predicted_delivery_ledger_sha256 is None
    ):
        raise ApprovalCoverageError(
            "the v2 draft carries no complete artifact reference"
        )
    # Prove three-member completion from the hashed member summaries alone.
    try:
        summaries = json.loads(record.prediction_member_summaries)
    except ValueError as error:
        raise ApprovalCoverageError(
            f"stored member summaries are not valid JSON: {error}"
        ) from error
    if not isinstance(summaries, list) or len(summaries) != 3:
        raise ApprovalCoverageError(
            "shadow approval requires exactly three member summaries"
        )
    labels = {
        entry.get("member") for entry in summaries if isinstance(entry, dict)
    }
    if labels != _PREDICTION_MEMBERS or any(
        entry.get("status") != "completed" for entry in summaries
    ):
        raise ApprovalCoverageError(
            "shadow approval requires a completed three-member prediction"
        )
    if record.prediction_status != "completed":
        raise ApprovalCoverageError(
            "shadow approval requires a completed three-member prediction"
        )
    # The bounded coverage summary must be intact and tie to this plan's run.
    if _sha256_text(record.coverage_summary_document_text) != (
        record.coverage_summary_sha256
    ):
        raise ApprovalCoverageError(
            "stored coverage summary does not match its hash"
        )
    try:
        coverage = json.loads(record.coverage_summary_document_text)
    except ValueError as error:
        raise ApprovalCoverageError(
            f"stored coverage summary is not valid JSON: {error}"
        ) from error
    if not isinstance(coverage, dict) or (
        coverage.get("prediction_run_id") != record.prediction_run_id
    ):
        raise ApprovalCoverageError(
            "coverage summary does not tie to the plan's prediction run"
        )
    # The ledger set must be exactly the one the header pins.
    if predicted_delivery_ledger_sha256(record.ledger_entries) != (
        record.predicted_delivery_ledger_sha256
    ):
        raise ApprovalCoverageError(
            "ledger rows do not match the pinned ledger hash"
        )
    _validate_scheduled_and_ledger(record, record.artifact_sha256)


def _validate_scheduled_and_ledger(
    record: Any, expected_response_sha256: str
) -> None:
    """Shared coverage: every scheduled requirement has a valid delivery path, the
    ledger covers exactly that set, every row references this plan's prediction
    (run id + ``expected_response_sha256``), and each requirement's terminal row
    lands at the horizon end predicting satisfaction."""
    scheduled = _scheduled_requirements(record)
    if not scheduled:
        raise ApprovalCoverageError("the draft has no scheduled requirement")
    scheduled_ids = set()
    for requirement in scheduled:
        try:
            path = json.loads(requirement.path_reach_ids_document_text or "null")
        except ValueError as error:
            raise ApprovalCoverageError(
                f"requirement {requirement.requirement_id} has a malformed path"
            ) from error
        if (
            not isinstance(path, list)
            or not path
            or any(not isinstance(r, str) or not r.strip() for r in path)
        ):
            raise ApprovalCoverageError(
                f"requirement {requirement.requirement_id} has no valid delivery "
                "path"
            )
        scheduled_ids.add(str(requirement.requirement_id))

    ledger_ids = {entry.requirement_id for entry in record.ledger_entries}
    if ledger_ids != scheduled_ids:
        raise ApprovalCoverageError(
            "ledger requirement coverage does not match the scheduled set"
        )
    # Every ledger row must belong to THIS plan's prediction — a self-consistent
    # ledger projected over a different prediction must not be certifiable.
    for entry in record.ledger_entries:
        if (
            entry.prediction_run_id != record.prediction_run_id
            or entry.prediction_response_sha256 != expected_response_sha256
        ):
            raise ApprovalCoverageError(
                f"ledger row for {entry.requirement_id} references a different "
                "prediction than the plan header"
            )
        if entry.status in ("manual_review", "invalidated"):
            raise ApprovalCoverageError(
                f"ledger row for {entry.requirement_id} is {entry.status}"
            )
    # Each requirement's terminal row must be its final checkpoint, land exactly
    # at the horizon end, and predict satisfaction (fulfilled/excess), not a
    # projected shortfall.
    horizon_end = _as_utc(record.horizon_end)
    by_requirement: dict[str, list] = {}
    for entry in record.ledger_entries:
        by_requirement.setdefault(entry.requirement_id, []).append(entry)
    for requirement_id, rows in by_requirement.items():
        terminal = max(rows, key=lambda e: e.checkpoint_index)
        if "horizon_end" not in terminal.checkpoint_reasons:
            raise ApprovalCoverageError(
                f"requirement {requirement_id} has no horizon-end terminal row"
            )
        if _as_utc(terminal.checkpoint_at) != horizon_end:
            raise ApprovalCoverageError(
                f"requirement {requirement_id} terminal row is not at the "
                "horizon end"
            )
        if terminal.status not in _TERMINAL_OK_STATUSES:
            raise ApprovalCoverageError(
                f"requirement {requirement_id} is predicted to fall short "
                f"(terminal status {terminal.status})"
            )


def _as_utc(instant):
    return instant.astimezone(timezone.utc)


def build_shadow_approval_freeze(
    record: Any, *, ledger_sha256: str, requirement_set_sha256: str
) -> dict:
    """The recomputable lineage freeze. A v2 record freezes the engine + artifact
    identity (schema 3); a v1 record freezes the response sha (schema 1)."""
    scheduled = _scheduled_requirements(record)
    freeze = {
        "schema_version": APPROVAL_FREEZE_SCHEMA_VERSION,
        "approval_mode": "shadow",
        "machine_authority_granted": False,
        "plan": {
            "plan_id": str(record.plan_id),
            "plan_version": record.plan_version,
            "input_content_hash": record.input_content_hash,
            "draft_content_hash": record.draft_content_hash,
            "optimizer_result_sha256": record.optimizer_result_sha256,
        },
        "requirements": {
            "requirement_run_id": str(record.requirement_run_id),
            "requirement_version": record.requirement_version,
            "requirement_set_sha256": requirement_set_sha256,
        },
        "model": {
            "model_snapshot_id": record.model_snapshot_id,
            "model_release_id": record.model_release_id,
            "model_release_content_hash": record.model_release_content_hash,
        },
        "prediction": {
            "prediction_run_id": record.prediction_run_id,
            "prediction_response_sha256": record.prediction_response_sha256,
        },
        "ledger": {
            "ledger_sha256": ledger_sha256,
            "entry_count": len(record.ledger_entries),
            "scheduled_requirement_count": len(scheduled),
        },
    }
    if getattr(record, "provenance_version", None) == PROVENANCE_VERSION_V2:
        freeze["schema_version"] = APPROVAL_FREEZE_SCHEMA_VERSION_V3
        # v2 freezes the engine + artifact identity in place of the response copy.
        freeze["prediction"] = {
            "prediction_run_id": record.prediction_run_id,
            "prediction_identity_version": record.prediction_identity_version,
            "engine_id": record.engine_id,
            "engine_semantic_contract_version": (
                record.engine_semantic_contract_version
            ),
            "engine_build_digest": record.engine_build_digest,
            "engine_descriptor_content_hash": (
                record.engine_descriptor_content_hash
            ),
            "artifact_sha256": record.artifact_sha256,
            "artifact_uncompressed_size_bytes": (
                record.artifact_uncompressed_size_bytes
            ),
            "artifact_media_type": record.artifact_media_type,
            "artifact_encoding": record.artifact_encoding,
            "artifact_encoding_version": record.artifact_encoding_version,
            "prediction_member_summaries_sha256": _sha256_text(
                record.prediction_member_summaries
            ),
            "coverage_summary_sha256": record.coverage_summary_sha256,
        }
        freeze["ledger"]["predicted_delivery_ledger_sha256"] = (
            record.predicted_delivery_ledger_sha256
        )
    return freeze


def shadow_approval_freeze_text(freeze: Mapping[str, Any]) -> str:
    return _canonical(freeze)


APPROVAL_DOCUMENT_SCHEMA_VERSION = 2


def build_shadow_approval_document(
    lineage_freeze: Mapping[str, Any],
    authorization_evidence: Mapping[str, Any],
) -> dict:
    """Wrap the recomputable lineage and the non-recomputable authorization
    evidence in a v2 document.

    CRITICAL: evidence lives in its OWN key, never inside ``lineage_freeze`` —
    ``verify_shadow_approval_freeze`` recomputes the lineage from immutable rows,
    and evidence is not derivable from those rows.
    """
    return {
        "schema_version": APPROVAL_DOCUMENT_SCHEMA_VERSION,
        "lineage_freeze": dict(lineage_freeze),
        "authorization_evidence": dict(authorization_evidence),
    }


def shadow_approval_document_text(document: Mapping[str, Any]) -> str:
    return _canonical(document)


def verify_shadow_approval_freeze(
    document_text: str,
    record: Any,
    *,
    ledger_sha256: str,
    requirement_set_sha256: str,
) -> None:
    """Recompute the lineage from immutable rows and require exact equality.

    Handles both shapes transparently: a v2 document ``{schema_version,
    lineage_freeze, authorization_evidence}`` compares only its ``lineage_freeze``
    (evidence is intentionally not recomputed); a legacy v1 document that IS the
    bare freeze compares whole.
    """
    try:
        stored = json.loads(document_text)
    except ValueError as error:
        raise ApprovalFreezeMismatchError(
            f"approval document is not valid JSON: {error}"
        ) from error
    stored_lineage = (
        stored["lineage_freeze"]
        if isinstance(stored, Mapping) and "lineage_freeze" in stored
        else stored
    )
    expected = build_shadow_approval_freeze(
        record,
        ledger_sha256=ledger_sha256,
        requirement_set_sha256=requirement_set_sha256,
    )
    if _canonical(stored_lineage) != _canonical(expected):
        raise ApprovalFreezeMismatchError(
            "frozen approval lineage no longer matches the immutable plan"
        )
