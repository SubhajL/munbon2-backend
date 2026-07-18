"""Bounded read-model for the control-plan list projection (PR 4.4a-3).

This repository is DELIBERATELY separate from ``PostgresControlPlanRepository``:
the detail path (`_assemble`) loads the full aggregate (requirements, events,
ALL transitions, ledger, the prediction response and optimizer documents) and
re-verifies every content hash — far too much for a page of headers. The list
projection selects ONLY ``control_plan_runs`` header columns, plus a bounded
read of the small transition rows (sequence/type/from/to + the small lifecycle
document) to derive each plan's current lifecycle state and approval-trust flag.

It NEVER selects the large documents (optimizer_result, prediction response,
model snapshot, canonical input) and never touches the requirements / events /
ledger tables — so a list page can never leak a plan's heavy payload. The
per-row lifecycle state and approval-trust flag are derived in the SAME snapshot
as the header/filter query (two correlated scalar subqueries), so the state a row
is filtered on and the state it is returned with can never disagree under a
concurrent transition, and only the single ``shadow_approved`` transition document
is loaded (never the whole transition history's documents).

Keyset pagination is ordered ``created_at DESC, plan_id DESC, plan_version DESC``
with a row-value ``(created_at, plan_id, plan_version) < (cursor)`` predicate over
the row's TOTAL identity ``(plan_id, plan_version)`` and a ``limit + 1`` fetch to
decide ``next_cursor`` without a second COUNT query.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import is_trusted_shadow_approval
from core.control_plan_cursor import (
    decode_plan_cursor,
    encode_plan_cursor,
)
from core.control_plan_lifecycle import (
    LifecycleHistoryCorruptError,
    derive_control_plan_state,
)
from core.predicted_delivery_ledger import (
    GateEvent,
    LedgerEntry,
    LedgerProjectionError,
    ScheduledRequirement,
    evaluate_safe_handover,
    predicted_delivery_ledger_sha256,
    verify_ledger_entry_columns,
)
from models.control_plan import (
    ControlPlanRequirement,
    ControlPlanRun,
    ControlStateTransition,
    GatePlanEventRow,
    SectionDeliveryLedgerEntry,
)
from schemas.control_plan import (
    PROJECTION_SCHEMA_VERSION,
    ControlPlanLedgerResponse,
    ControlPlanLifecycleHistoryResponse,
    ControlPlanListFilters,
    ControlPlanListPage,
    ControlPlanPredictionCoverageResponse,
    ControlPlanSummaryOut,
    HandoverVerdictOut,
    LedgerEntryOut,
    MemberBoundsOut,
    PlanTransitionOut,
    PredictionMemberStatusOut,
)

# Provenance version of an artifact-reference (v2) row — kept as a local literal
# so this bounded read model never imports the write-model repository (asserted by
# test_projection_repository_never_calls_assemble).
_PROVENANCE_VERSION_V2 = 2


class ProjectionCorruptError(Exception):
    """A stored document a bounded read DID load fails its own integrity check
    (bad JSON / a ledger row that drifted from its hash) — fail closed with a 503
    rather than serving a partial projection."""

# The queryable per-plan prediction CONTENT hash: the v1 full-response sha for a
# v1 row, the artifact sha for a v2 (artifact-reference) row whose response sha is
# NULL. Exposing it as one COALESCE keeps the BFF 4.4 content-hash filter and the
# served ``prediction_response_sha256`` non-null and consistent across BOTH storage
# versions. Both operands are small CHAR(64) scalars, so the projection stays
# bounded.
_PREDICTION_CONTENT_SHA256 = func.coalesce(
    ControlPlanRun.prediction_response_sha256,
    ControlPlanRun.artifact_sha256,
)

# The exact header columns a summary row is built from — small scalars only.
# Adding the large *_document_text / model_snapshot_document_text columns here
# would defeat the whole point of a bounded projection, so they are absent by
# construction (the omission is asserted by a unit test over the compiled SQL).
_SUMMARY_COLUMNS = (
    ControlPlanRun.plan_id,
    ControlPlanRun.plan_version,
    ControlPlanRun.horizon_start,
    ControlPlanRun.horizon_end,
    ControlPlanRun.requirement_run_id,
    ControlPlanRun.requirement_version,
    ControlPlanRun.input_content_hash,
    ControlPlanRun.model_snapshot_id,
    ControlPlanRun.model_release_content_hash,
    ControlPlanRun.optimizer_status,
    ControlPlanRun.prediction_status,
    ControlPlanRun.prediction_run_id,
    _PREDICTION_CONTENT_SHA256.label("prediction_response_sha256"),
    ControlPlanRun.created_by_subject,
    ControlPlanRun.created_at,
)


def _latest_state_subquery():
    """The DERIVED current lifecycle state as a correlated scalar subquery.

    A validated linear history's current state IS the terminal transition's
    ``to_state`` (exactly what ``derive_control_plan_state`` returns), so both the
    ``lifecycle_state`` filter AND the returned ``lifecycle_state`` select on the
    max-sequence ``to_state`` — from ONE statement/snapshot, so a concurrent
    transition can never leave a row filtered on one state but returned with
    another. It selects ONLY ``to_state`` (never the transition document), so the
    projection stays bounded."""
    return (
        select(ControlStateTransition.to_state)
        .where(
            ControlStateTransition.plan_id == ControlPlanRun.plan_id,
            ControlStateTransition.plan_version == ControlPlanRun.plan_version,
        )
        .order_by(ControlStateTransition.transition_sequence.desc())
        .limit(1)
        .scalar_subquery()
    )


def _shadow_approval_document_subquery():
    """The single ``shadow_approved`` transition document as a correlated scalar
    subquery.

    Restricted to ``transition_type = 'shadow_approved'`` (there is at most one
    per plan version), so a page of N plans loads at most N small approval
    documents — NEVER every transition's document. Any non-approval transition
    document stays unread."""
    return (
        select(ControlStateTransition.transition_document_text)
        .where(
            ControlStateTransition.plan_id == ControlPlanRun.plan_id,
            ControlStateTransition.plan_version == ControlPlanRun.plan_version,
            ControlStateTransition.transition_type == "shadow_approved",
        )
        .order_by(ControlStateTransition.transition_sequence.desc())
        .limit(1)
        .scalar_subquery()
    )


def _apply_filters(stmt, filters: ControlPlanListFilters):
    if filters.lifecycle_state is not None:
        stmt = stmt.where(_latest_state_subquery() == filters.lifecycle_state)
    if filters.horizon_start_gte is not None:
        stmt = stmt.where(ControlPlanRun.horizon_start >= filters.horizon_start_gte)
    if filters.horizon_end_lte is not None:
        stmt = stmt.where(ControlPlanRun.horizon_end <= filters.horizon_end_lte)
    if filters.requirement_run_id is not None:
        stmt = stmt.where(
            ControlPlanRun.requirement_run_id == filters.requirement_run_id
        )
    if filters.requirement_version is not None:
        stmt = stmt.where(
            ControlPlanRun.requirement_version == filters.requirement_version
        )
    if filters.input_content_hash is not None:
        stmt = stmt.where(
            ControlPlanRun.input_content_hash == filters.input_content_hash
        )
    if filters.model_snapshot_id is not None:
        stmt = stmt.where(
            ControlPlanRun.model_snapshot_id == filters.model_snapshot_id
        )
    if filters.model_release_content_hash is not None:
        stmt = stmt.where(
            ControlPlanRun.model_release_content_hash
            == filters.model_release_content_hash
        )
    if filters.prediction_run_id is not None:
        stmt = stmt.where(
            ControlPlanRun.prediction_run_id == filters.prediction_run_id
        )
    if filters.prediction_content_sha256 is not None:
        stmt = stmt.where(
            _PREDICTION_CONTENT_SHA256 == filters.prediction_content_sha256
        )
    return stmt


def build_summary_query(
    filters: ControlPlanListFilters,
    keyset: Optional[tuple],
    limit: int,
):
    """The bounded keyset SELECT: header columns + the derived lifecycle state and
    the single shadow-approval document (both correlated scalar subqueries from the
    SAME snapshot), filtered, keyset-bounded, ordered ``created_at DESC, plan_id
    DESC, plan_version DESC``, fetching ``limit + 1``."""
    stmt = select(
        *_SUMMARY_COLUMNS,
        _latest_state_subquery().label("derived_state"),
        _shadow_approval_document_subquery().label(
            "shadow_approval_document_text"
        ),
    )
    stmt = _apply_filters(stmt, filters)
    if keyset is not None:
        cursor_created_at, cursor_plan_id, cursor_plan_version = keyset
        stmt = stmt.where(
            tuple_(
                ControlPlanRun.created_at,
                ControlPlanRun.plan_id,
                ControlPlanRun.plan_version,
            )
            < tuple_(cursor_created_at, cursor_plan_id, cursor_plan_version)
        )
    return stmt.order_by(
        ControlPlanRun.created_at.desc(),
        ControlPlanRun.plan_id.desc(),
        ControlPlanRun.plan_version.desc(),
    ).limit(limit + 1)


def _approval_trust_from_document(document_text: Optional[str]) -> bool:
    """True iff the single loaded ``shadow_approved`` document is a TRUSTED
    (strict-policy v2) approval.

    No shadow_approved transition (``document_text`` is None/empty), a legacy v1
    freeze, a compat-mode v2 document, or an unparseable document all read as
    untrusted — the projection never upgrades an unverifiable approval to
    trusted."""
    if not document_text:
        return False
    try:
        document = json.loads(document_text)
    except ValueError:
        return False
    return is_trusted_shadow_approval(document)


# --- Bounded per-plan read projections (PR 4.4b-3) --------------------------
# Each of the three reads below is a SINGLE-plan snapshot keyed by (plan_id,
# plan_version), selecting only the columns the projection needs and NEVER a
# run-level large document (optimizer_result / model snapshot / canonical input /
# prediction request / prediction RESPONSE) — proven by compiling the SELECTs. The
# pure ``build_*`` functions are shared by the Postgres methods and (via the test
# support twin) the in-memory fake, and are what the equivalence test pins against
# the full ``_assemble`` detail projection.


def _parse_projection_json(text: str):
    try:
        return json.loads(text)
    except ValueError as error:
        raise ProjectionCorruptError(
            f"a stored control-plan document is corrupt: {error}"
        ) from error


def _text_sha256(text: str) -> str:
    """SHA-256 of stored canonical text. Duplicated (not imported) so this bounded
    read model never imports the write-model repository (asserted by
    test_projection_repository_never_calls_assemble)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _model_or_corrupt(build):
    """Build a Pydantic response model from stored JSON, mapping a WELL-FORMED but
    SCHEMA-INVALID stored shape (an unknown enum status, an array where an object
    is required, a missing key) to ProjectionCorruptError (→ 503) rather than
    letting a Pydantic ValidationError / TypeError / KeyError escape as an opaque
    500. Only these malformed-container errors are wrapped; any other exception
    propagates unchanged."""
    try:
        return build()
    except (ValidationError, TypeError, KeyError) as error:
        raise ProjectionCorruptError(
            f"a stored control-plan document has an invalid shape: {error}"
        ) from error


# COVERAGE -------------------------------------------------------------------
_COVERAGE_COLUMNS = (
    ControlPlanRun.plan_id,
    ControlPlanRun.plan_version,
    ControlPlanRun.requirement_run_id,
    ControlPlanRun.requirement_version,
    ControlPlanRun.model_snapshot_id,
    ControlPlanRun.model_release_id,
    ControlPlanRun.model_release_content_hash,
    ControlPlanRun.input_content_hash,
    ControlPlanRun.draft_content_hash,
    ControlPlanRun.optimizer_status,
    ControlPlanRun.prediction_status,
    ControlPlanRun.prediction_run_id,
    # Small (3-member) status list — the ONE bounded document coverage needs; it
    # never selects the optimizer result, model snapshot, or prediction response.
    ControlPlanRun.prediction_member_summaries,
    # v2 authentication columns (all bounded scalars / the small coverage summary):
    # the coverage summary and its hash independently pin the same member statuses,
    # so a mutated prediction_member_summaries column is caught in a bounded read.
    ControlPlanRun.provenance_version,
    ControlPlanRun.coverage_summary_document_text,
    ControlPlanRun.coverage_summary_sha256,
)


def coverage_query(plan_id: UUID, plan_version: int):
    return select(*_COVERAGE_COLUMNS).where(
        ControlPlanRun.plan_id == plan_id,
        ControlPlanRun.plan_version == plan_version,
    )


def _member_statuses(summaries_text: Optional[str]) -> list[PredictionMemberStatusOut]:
    if summaries_text is None:
        return []
    entries = _parse_projection_json(summaries_text)
    return _model_or_corrupt(
        lambda: [PredictionMemberStatusOut(**entry) for entry in entries]
    )


def _authenticate_v2_member_statuses(header, statuses) -> None:
    """Fail closed unless a v2 row's served ``prediction_member_summaries`` agree
    with the INDEPENDENTLY hash-pinned bounded coverage summary.

    The v2 coverage summary carries the same three member labels/statuses under its
    OWN ``coverage_summary_sha256`` (a component of the provenance reference that
    binds into ``draft_content_hash``). Re-verifying that sha here (the bounded
    check ``_verify_stored_draft_v2`` performs, WITHOUT the large input/optimizer/
    snapshot documents) and cross-checking the two surfaces catches any single-
    surface mutation of the served summaries column — the attack ``_assemble``
    catches via the full draft hash — in a genuinely bounded read."""
    doc_text = getattr(header, "coverage_summary_document_text", None)
    stored_sha = getattr(header, "coverage_summary_sha256", None)
    if doc_text is None or stored_sha is None:
        raise ProjectionCorruptError(
            "a v2 control plan is missing its bounded coverage summary"
        )
    if _text_sha256(doc_text) != stored_sha:
        raise ProjectionCorruptError(
            "stored coverage summary does not match its hash"
        )
    document = _parse_projection_json(doc_text)
    members = document.get("members") if isinstance(document, dict) else None
    if not isinstance(members, list):
        raise ProjectionCorruptError(
            "stored coverage summary carries no member list"
        )
    authenticated = [
        (member.get("member"), member.get("status"))
        for member in members
        if isinstance(member, dict)
    ]
    served = [(status.member, status.status) for status in statuses]
    if authenticated != served:
        raise ProjectionCorruptError(
            "served prediction member summaries disagree with the hash-"
            "authenticated coverage summary"
        )


def build_prediction_coverage(header) -> ControlPlanPredictionCoverageResponse:
    """Coverage response from a bounded header (a SQL row OR a full DraftPlanRecord
    — both expose the same attribute names, which is why the equivalence test can
    feed this the full aggregate and get the identical answer).

    Provenance dispatch mirrors ``verify_stored_draft``: None → v1, 2 → v2, any
    other value → corruption (503). For a **v2** row the served member statuses are
    re-authenticated against the bounded, hash-pinned coverage summary. For a **v1**
    row the member summaries are bound only by the FULL draft hash (recomputing it
    needs the whole aggregate, which would defeat boundedness), so a bounded read
    cannot re-authenticate them: v1 coverage relies on the append-only immutability
    triggers as its primary defense, and this narrowing is deliberate (v1 is legacy
    and being phased out). See ``_authenticate_v2_member_statuses``."""
    statuses = _member_statuses(header.prediction_member_summaries)
    version = getattr(header, "provenance_version", None)
    if version == _PROVENANCE_VERSION_V2:
        _authenticate_v2_member_statuses(header, statuses)
    elif version is not None:
        raise ProjectionCorruptError(
            f"stored control plan carries unknown provenance_version {version!r}"
        )
    return _model_or_corrupt(
        lambda: ControlPlanPredictionCoverageResponse(
            plan_id=header.plan_id,
            plan_version=header.plan_version,
            requirement_run_id=header.requirement_run_id,
            requirement_version=header.requirement_version,
            model_snapshot_id=header.model_snapshot_id,
            model_release_id=header.model_release_id,
            model_release_content_hash=header.model_release_content_hash,
            input_content_hash=header.input_content_hash,
            draft_content_hash=header.draft_content_hash,
            optimizer_status=header.optimizer_status,
            prediction_status=header.prediction_status,
            prediction_run_id=header.prediction_run_id,
            prediction_member_statuses=statuses,
        )
    )


# LIFECYCLE HISTORY ----------------------------------------------------------
_HISTORY_HEADER_COLUMNS = (
    ControlPlanRun.plan_id,
    ControlPlanRun.plan_version,
    ControlPlanRun.created_by_subject,
    ControlPlanRun.created_at,
)
_TRANSITION_COLUMNS = (
    ControlStateTransition.transition_sequence,
    ControlStateTransition.transition_type,
    ControlStateTransition.from_state,
    ControlStateTransition.to_state,
    ControlStateTransition.actor_subject,
    ControlStateTransition.reason,
    # History NEEDS each transition document verbatim (unlike the list projection,
    # which loads only the single shadow_approved document).
    ControlStateTransition.transition_document_text,
    ControlStateTransition.occurred_at,
)


def history_header_query(plan_id: UUID, plan_version: int):
    return select(*_HISTORY_HEADER_COLUMNS).where(
        ControlPlanRun.plan_id == plan_id,
        ControlPlanRun.plan_version == plan_version,
    )


def history_transitions_query(plan_id: UUID, plan_version: int):
    return (
        select(*_TRANSITION_COLUMNS)
        .where(
            ControlStateTransition.plan_id == plan_id,
            ControlStateTransition.plan_version == plan_version,
        )
        .order_by(ControlStateTransition.transition_sequence)
    )


def _transition_out(transition) -> PlanTransitionOut:
    document_text = transition.transition_document_text
    document = (
        None if document_text is None else _parse_projection_json(document_text)
    )
    # A well-formed-JSON transition document that is not an object (e.g. an array
    # or a bare scalar) is schema-invalid stored state → fail closed with a 503,
    # never an opaque 500 from Pydantic.
    return _model_or_corrupt(
        lambda: PlanTransitionOut(
            transition_sequence=transition.transition_sequence,
            transition_type=transition.transition_type,
            from_state=transition.from_state,
            to_state=transition.to_state,
            actor_subject=transition.actor_subject,
            reason=transition.reason,
            transition_document=document,
            occurred_at=transition.occurred_at,
        )
    )


def build_lifecycle_history(header, transitions) -> ControlPlanLifecycleHistoryResponse:
    """History response: identity + the DERIVED lifecycle state (validates the whole
    chain — a corrupt history raises LifecycleHistoryCorruptError, a 503) + every
    transition preserved verbatim in sequence order."""
    lifecycle_state = derive_control_plan_state(transitions)
    return ControlPlanLifecycleHistoryResponse(
        plan_id=header.plan_id,
        plan_version=header.plan_version,
        lifecycle_state=lifecycle_state,
        created_by_subject=header.created_by_subject,
        created_at=header.created_at,
        transitions=[_transition_out(t) for t in transitions],
    )


# LEDGER ---------------------------------------------------------------------
_LEDGER_RUN_COLUMNS = (
    ControlPlanRun.plan_id,
    ControlPlanRun.plan_version,
    ControlPlanRun.prediction_run_id,
    ControlPlanRun.prediction_status,
    ControlPlanRun.provenance_version,
    ControlPlanRun.predicted_delivery_ledger_sha256,
    # The header's per-plan prediction CONTENT sha — artifact_sha256 for a v2 row
    # (whose prediction_response_sha256 is NULL) and prediction_response_sha256 for
    # a v1 row — is what every ledger row's own lineage must equal, so a valid row
    # from ANOTHER plan can never be swapped in. Both are small CHAR(64) scalars.
    ControlPlanRun.artifact_sha256,
    ControlPlanRun.prediction_response_sha256,
)
_LEDGER_ENTRY_COLUMNS = (
    SectionDeliveryLedgerEntry.requirement_id,
    SectionDeliveryLedgerEntry.section_id,
    SectionDeliveryLedgerEntry.checkpoint_index,
    SectionDeliveryLedgerEntry.checkpoint_at,
    SectionDeliveryLedgerEntry.status,
    SectionDeliveryLedgerEntry.required_volume_m3,
    SectionDeliveryLedgerEntry.approved_excess_m3,
    SectionDeliveryLedgerEntry.lower_delivered_m3,
    SectionDeliveryLedgerEntry.nominal_delivered_m3,
    SectionDeliveryLedgerEntry.upper_delivered_m3,
    SectionDeliveryLedgerEntry.lower_path_in_transit_m3,
    SectionDeliveryLedgerEntry.nominal_path_in_transit_m3,
    SectionDeliveryLedgerEntry.upper_path_in_transit_m3,
    SectionDeliveryLedgerEntry.checkpoint_reasons_document_text,
    SectionDeliveryLedgerEntry.prediction_run_id,
    SectionDeliveryLedgerEntry.prediction_response_sha256,
    SectionDeliveryLedgerEntry.projection_sha256,
    SectionDeliveryLedgerEntry.projection_document_text,
)
# Only the requirement columns the handover verdict needs (the small path reach
# list included) — never the heavy per-requirement canonical document.
_LEDGER_REQUIREMENT_COLUMNS = (
    ControlPlanRequirement.requirement_id,
    ControlPlanRequirement.section_id,
    ControlPlanRequirement.gate_id,
    ControlPlanRequirement.required_volume_m3,
    ControlPlanRequirement.approved_excess_m3,
    ControlPlanRequirement.planning_disposition,
    ControlPlanRequirement.path_reach_ids_document_text,
    ControlPlanRequirement.window_start,
    ControlPlanRequirement.window_end,
)
_LEDGER_EVENT_COLUMNS = (
    GatePlanEventRow.event_sequence,
    GatePlanEventRow.gate_id,
    GatePlanEventRow.event_kind,
    GatePlanEventRow.planned_at,
    GatePlanEventRow.target_position_m,
)


def ledger_run_query(plan_id: UUID, plan_version: int):
    return select(*_LEDGER_RUN_COLUMNS).where(
        ControlPlanRun.plan_id == plan_id,
        ControlPlanRun.plan_version == plan_version,
    )


def ledger_entries_query(plan_id: UUID, plan_version: int):
    return (
        select(*_LEDGER_ENTRY_COLUMNS)
        .where(
            SectionDeliveryLedgerEntry.plan_id == plan_id,
            SectionDeliveryLedgerEntry.plan_version == plan_version,
        )
        .order_by(
            SectionDeliveryLedgerEntry.requirement_id,
            SectionDeliveryLedgerEntry.checkpoint_index,
        )
    )


def ledger_requirements_query(plan_id: UUID, plan_version: int):
    # Only SCHEDULED requirements drive the handover verdict, so filter them in SQL
    # rather than fetching every requirement and dropping non-scheduled ones in
    # Python. The output is identical: the builder ignores non-scheduled rows.
    return (
        select(*_LEDGER_REQUIREMENT_COLUMNS)
        .where(
            ControlPlanRequirement.plan_id == plan_id,
            ControlPlanRequirement.plan_version == plan_version,
            ControlPlanRequirement.planning_disposition == "scheduled",
        )
        .order_by(ControlPlanRequirement.requirement_id)
    )


def ledger_events_query(plan_id: UUID, plan_version: int, gate_ids):
    # Restrict to the gates referenced by the scheduled requirements — the only
    # gates the handover verdict ever evaluates. An empty gate set selects no rows.
    return (
        select(*_LEDGER_EVENT_COLUMNS)
        .where(
            GatePlanEventRow.plan_id == plan_id,
            GatePlanEventRow.plan_version == plan_version,
            GatePlanEventRow.gate_id.in_(list(gate_ids)),
        )
        .order_by(GatePlanEventRow.event_sequence)
    )


def _ledger_entry_from_row(row) -> LedgerEntry:
    return LedgerEntry(
        requirement_id=str(row.requirement_id),
        section_id=row.section_id,
        checkpoint_index=row.checkpoint_index,
        checkpoint_at=row.checkpoint_at,
        status=row.status,
        required_volume_m3=row.required_volume_m3,
        approved_excess_m3=row.approved_excess_m3,
        lower_delivered_m3=row.lower_delivered_m3,
        nominal_delivered_m3=row.nominal_delivered_m3,
        upper_delivered_m3=row.upper_delivered_m3,
        lower_path_in_transit_m3=row.lower_path_in_transit_m3,
        nominal_path_in_transit_m3=row.nominal_path_in_transit_m3,
        upper_path_in_transit_m3=row.upper_path_in_transit_m3,
        checkpoint_reasons=tuple(
            _parse_projection_json(row.checkpoint_reasons_document_text)
        ),
        prediction_run_id=row.prediction_run_id,
        prediction_response_sha256=row.prediction_response_sha256,
        projection_sha256=row.projection_sha256,
        projection_document_text=row.projection_document_text,
    )


def _bounds(values: list) -> MemberBoundsOut:
    present = [v for v in values if v is not None]
    lower = min(present) if present else None
    upper = max(present) if present else None
    nominal = values[1] if len(values) == 3 else None
    return MemberBoundsOut(lower_bound=lower, nominal=nominal, upper_bound=upper)


def _handover_verdicts(prediction_status, ledger_entries, events, requirements):
    gate_events = [
        GateEvent(
            gate_id=event.gate_id,
            kind=event.event_kind,
            planned_at=event.planned_at,
            target_position_m=event.target_position_m,
        )
        for event in events
    ]
    all_completed = prediction_status == "completed"
    by_gate: dict = {}
    for requirement in requirements:
        if requirement.planning_disposition != "scheduled":
            continue
        by_gate.setdefault(requirement.gate_id, []).append(
            ScheduledRequirement(
                requirement_id=str(requirement.requirement_id),
                section_id=requirement.section_id,
                gate_id=requirement.gate_id,
                required_volume_m3=requirement.required_volume_m3,
                approved_excess_m3=requirement.approved_excess_m3,
                path_reach_ids=tuple(
                    _parse_projection_json(
                        requirement.path_reach_ids_document_text
                    )
                ),
                window_start=requirement.window_start,
                window_end=requirement.window_end,
            )
        )
    for gate_id in sorted(by_gate):
        gate_requirements = by_gate[gate_id]
        verdict = evaluate_safe_handover(
            gate_requirements,
            ledger_entries,
            gate_events,
            all_members_completed=all_completed,
        )
        yield (gate_id, [r.requirement_id for r in gate_requirements], verdict)


def _ledger_content_sha(header) -> Optional[str]:
    """The header's per-plan prediction CONTENT sha that EVERY ledger row's own
    ``prediction_response_sha256`` must equal: ``artifact_sha256`` for a v2
    (artifact-reference) row, ``prediction_response_sha256`` for a v1 row.

    Strict dispatch mirrors ``verify_stored_draft``: ``None`` → v1, ``2`` → v2, any
    other value → corruption. A row from ANOTHER plan that is individually hash-
    valid must never be dispatched to the v1 path and served."""
    version = getattr(header, "provenance_version", None)
    if version == _PROVENANCE_VERSION_V2:
        return header.artifact_sha256
    if version is None:
        return header.prediction_response_sha256
    raise ProjectionCorruptError(
        f"stored control plan carries unknown provenance_version {version!r}"
    )


def build_ledger_projection(
    header, ledger_entries, events, requirements
) -> ControlPlanLedgerResponse:
    """The predicted-delivery ledger response — byte-for-byte the shape the full
    ``_assemble``-backed ledger read produced, but built from the bounded ledger /
    requirement / event rows (never the run's large documents). Re-verifies the
    hashes it DID load: every ledger row against its own content hash, every row's
    per-plan lineage against the header (the ``_assemble`` guard the bounded read
    previously dropped), and the whole-ledger sha against the stored column — fail
    closed on any drift."""
    expected_content_sha = _ledger_content_sha(header)
    for entry in ledger_entries:
        try:
            verify_ledger_entry_columns(entry)
        except LedgerProjectionError as error:
            raise ProjectionCorruptError(str(error)) from error
        # Per-row lineage: an individually hash-valid row that belongs to a
        # DIFFERENT prediction (run id / content sha) is corruption, not a plan
        # this header describes — reject rather than serve a swapped-in ledger.
        if (
            entry.prediction_run_id != header.prediction_run_id
            or entry.prediction_response_sha256 != expected_content_sha
        ):
            raise ProjectionCorruptError(
                f"ledger row for {entry.requirement_id} references a different "
                "prediction than the plan header"
            )
    ledger_sha = predicted_delivery_ledger_sha256(ledger_entries)
    # The whole-ledger sha is verified whenever the header carries one: always for
    # a v2 row (the column is required), and for a v1 row that recorded it. When a
    # v1 header carries no ledger sha the per-row content + lineage checks above are
    # the ledger's integrity guarantee (the behaviour ``_assemble`` had for v1).
    stored_ledger_sha = getattr(header, "predicted_delivery_ledger_sha256", None)
    if stored_ledger_sha is not None and ledger_sha != stored_ledger_sha:
        raise ProjectionCorruptError(
            "stored predicted-delivery ledger hash does not match its rows"
        )
    entries = []
    for entry in ledger_entries:
        delivered = _bounds(
            [
                entry.lower_delivered_m3,
                entry.nominal_delivered_m3,
                entry.upper_delivered_m3,
            ]
        )

        def _remaining(delivered_value):
            return (
                None
                if delivered_value is None
                else max(0.0, entry.required_volume_m3 - delivered_value)
            )

        remaining = MemberBoundsOut(
            lower_bound=_remaining(delivered.upper_bound),
            nominal=_remaining(delivered.nominal),
            upper_bound=_remaining(delivered.lower_bound),
        )
        entries.append(
            LedgerEntryOut(
                requirement_id=entry.requirement_id,
                section_id=entry.section_id,
                checkpoint_index=entry.checkpoint_index,
                checkpoint_at=entry.checkpoint_at,
                status=entry.status,
                required_volume_m3=entry.required_volume_m3,
                approved_excess_m3=entry.approved_excess_m3,
                delivered_m3=delivered,
                path_in_transit_m3=_bounds(
                    [
                        entry.lower_path_in_transit_m3,
                        entry.nominal_path_in_transit_m3,
                        entry.upper_path_in_transit_m3,
                    ]
                ),
                remaining_m3=remaining,
                checkpoint_reasons=list(entry.checkpoint_reasons),
            )
        )
    handover = [
        HandoverVerdictOut(
            gate_id=gate_id,
            requirement_ids=requirement_ids,
            is_safe=verdict.is_safe,
            reasons=list(verdict.reasons),
        )
        for gate_id, requirement_ids, verdict in _handover_verdicts(
            header.prediction_status, ledger_entries, events, requirements
        )
    ]
    return ControlPlanLedgerResponse(
        plan_id=header.plan_id,
        plan_version=header.plan_version,
        prediction_run_id=header.prediction_run_id,
        prediction_status=header.prediction_status,
        ledger_sha256=ledger_sha,
        entries=entries,
        handover=handover,
    )


async def _begin_snapshot_read(session: AsyncSession) -> None:
    """Pin a REPEATABLE READ snapshot for a multi-statement bounded read.

    Postgres fixes a REPEATABLE READ transaction's snapshot at its FIRST query, so
    every subsequent statement in the read observes exactly that one generation. The
    per-transaction isolation option is only honoured before the transaction has
    begun, so any ambient (read-only) transaction on this session is rolled back
    first — guaranteeing the snapshot even when the caller reuses a session across
    reads, instead of silently dropping back to READ COMMITTED. The option is
    per-transaction, so it is reset when this read's transaction ends and never
    leaks to other operations on the pooled connection."""
    await session.rollback()
    await session.connection(
        execution_options={"isolation_level": "REPEATABLE READ"}
    )


class PostgresControlPlanProjectionRepository:
    """Header-only list read model. Twin-checked against the in-memory fake by
    ``test_control_plan_projection`` (both expose the same ``list_plan_summaries``
    signature and pagination semantics)."""

    async def list_plan_summaries(
        self,
        session: AsyncSession,
        *,
        filters: ControlPlanListFilters,
        cursor: Optional[str],
        limit: int,
    ) -> ControlPlanListPage:
        identity = filters.cursor_identity()
        keyset = (
            decode_plan_cursor(cursor, identity) if cursor is not None else None
        )
        rows = (
            await session.execute(build_summary_query(filters, keyset, limit))
        ).all()
        has_more = len(rows) > limit
        page_rows = rows[:limit]

        items = []
        for row in page_rows:
            if row.derived_state is None:
                # A run with no transition history at all is impossible under the
                # atomic store (draft_created lands with the run) — treat a null
                # derived state as fail-closed corruption (503), never a 500.
                raise LifecycleHistoryCorruptError(
                    f"control plan {row.plan_id} v{row.plan_version} has no "
                    "transition history"
                )
            items.append(
                ControlPlanSummaryOut(
                    plan_id=row.plan_id,
                    plan_version=row.plan_version,
                    lifecycle_state=row.derived_state,
                    approval_trust=_approval_trust_from_document(
                        row.shadow_approval_document_text
                    ),
                    horizon_start=row.horizon_start,
                    horizon_end=row.horizon_end,
                    requirement_run_id=row.requirement_run_id,
                    requirement_version=row.requirement_version,
                    input_content_hash=row.input_content_hash,
                    model_snapshot_id=row.model_snapshot_id,
                    model_release_content_hash=row.model_release_content_hash,
                    optimizer_status=row.optimizer_status,
                    prediction_status=row.prediction_status,
                    prediction_run_id=row.prediction_run_id,
                    prediction_response_sha256=row.prediction_response_sha256,
                    created_by_subject=row.created_by_subject,
                    created_at=row.created_at,
                )
            )

        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = encode_plan_cursor(
                last.created_at, last.plan_id, last.plan_version, identity
            )
        return ControlPlanListPage(
            items=items,
            next_cursor=next_cursor,
            projection_schema_version=PROJECTION_SCHEMA_VERSION,
        )

    # --- Bounded per-plan reads (PR 4.4b-3). Each returns None when the plan is
    # absent (the route maps that to 404) and raises fail-closed corruption (503)
    # via the shared build_* functions. None of them ever calls _assemble or loads
    # a run-level large document. The two MULTI-statement reads (history: 2
    # statements; ledger: up to 4) take a REPEATABLE READ snapshot before their
    # first statement (`_begin_snapshot_read`) so every statement observes ONE
    # consistent generation — a concurrent append committed mid-read can never mix
    # a header from one generation with children from another.
    async def load_prediction_coverage(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> Optional[ControlPlanPredictionCoverageResponse]:
        # A single statement — already atomic, so no snapshot pin is needed.
        row = (
            await session.execute(coverage_query(plan_id, plan_version))
        ).one_or_none()
        if row is None:
            return None
        return build_prediction_coverage(row)

    async def load_lifecycle_history(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> Optional[ControlPlanLifecycleHistoryResponse]:
        await _begin_snapshot_read(session)
        header = (
            await session.execute(history_header_query(plan_id, plan_version))
        ).one_or_none()
        if header is None:
            return None
        transitions = (
            await session.execute(
                history_transitions_query(plan_id, plan_version)
            )
        ).all()
        return build_lifecycle_history(header, transitions)

    async def load_ledger_projection(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> Optional[ControlPlanLedgerResponse]:
        await _begin_snapshot_read(session)
        header = (
            await session.execute(ledger_run_query(plan_id, plan_version))
        ).one_or_none()
        if header is None:
            return None
        entry_rows = (
            await session.execute(ledger_entries_query(plan_id, plan_version))
        ).all()
        ledger_entries = tuple(
            _ledger_entry_from_row(row) for row in entry_rows
        )
        # Fetch the scheduled requirements first, then load ONLY the gate events
        # those requirements reference — the handover verdict never touches any
        # other requirement or gate. (Filtered in SQL; the builder output is
        # identical to feeding it the unfiltered requirement/event sets.)
        requirements = (
            await session.execute(
                ledger_requirements_query(plan_id, plan_version)
            )
        ).all()
        gate_ids = sorted({req.gate_id for req in requirements})
        events = (
            await session.execute(
                ledger_events_query(plan_id, plan_version, gate_ids)
            )
        ).all()
        return build_ledger_projection(
            header, ledger_entries, events, requirements
        )
