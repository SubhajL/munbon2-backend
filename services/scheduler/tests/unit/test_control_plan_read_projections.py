"""Bounded control-plan read projections (PR 4.4b-3).

The scheduler serves three dedicated, BOUNDED reads — prediction coverage,
lifecycle history, and the predicted-delivery ledger — each a single-snapshot,
header/required-columns-only query that NEVER touches ``_assemble`` and, for a v2
(artifact-reference) row, NEVER selects the discarded prediction response. The
core requirement is EQUIVALENCE: each bounded projection must return EXACTLY the
same data as projecting from the full ``_assemble`` detail. Here the LOGIC is
proven against a full fixture record (both v1- and v2-shaped) versus the detail
builder, the bounded SELECTs are proven by compiling them and asserting they name
NO large-document column, and corruption is proven to fail closed. The DB-touching
walk over real rows lives in the env-gated integration suite.
"""

import json
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from api.v1.endpoints.control_plans import _response_from_record
from core.control_plan import control_plan_draft_hash
from core.control_plan_lifecycle import LifecycleHistoryCorruptError
from repositories.control_plan_projection_repository import (
    ProjectionCorruptError,
    build_ledger_projection,
    build_lifecycle_history,
    build_prediction_coverage,
    coverage_query,
    history_header_query,
    history_transitions_query,
    ledger_entries_query,
    ledger_events_query,
    ledger_requirements_query,
    ledger_run_query,
)
from repositories.control_plan_repository import (
    build_draft_hash_document,
    text_sha256,
)
from schemas.control_plan import (
    ControlPlanLedgerResponse,
    ControlPlanLifecycleHistoryResponse,
    ControlPlanPredictionCoverageResponse,
    HandoverVerdictOut,
    LedgerEntryOut,
    MemberBoundsOut,
)
from services.control_plan_service import ControlPlanDraftService
from schemas.control_plan import DraftControlPlanRequest
from tests.control_plan_test_support import (
    REQ_ID,
    TRUSTED_APPROVAL_DOCUMENT,
    FakeControlFlowClient,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)
from core.predicted_delivery_ledger import (
    GateEvent,
    ScheduledRequirement,
    evaluate_safe_handover,
    ledger_row_sha256,
    predicted_delivery_ledger_sha256,
)
from repositories.control_plan_repository import TransitionRecord

_V1_PLAN_ID = UUID("00000000-0000-4000-8000-0000000000a1")


async def _run_blocking(func, *args, **kwargs):
    return func(*args, **kwargs)


def _service(repository):
    return ControlPlanDraftService(
        ros_client=FakeRosGisClient([requirement_item()]),
        flow_client=FakeControlFlowClient(snapshot_mirror()),
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


async def _v2_record():
    """A rich, feasible+completed v2 draft (ledger, events, requirements, member
    summaries) assembled entirely in memory — nothing persisted."""
    record, _ = await _service(FakeRepository()).create_draft(
        None, DraftControlPlanRequest.model_validate(draft_payload()), "operator-1"
    )
    assert record.provenance_version == 2
    return record


async def _v1_record(v2):
    fake = FakeControlFlowClient(snapshot_mirror())
    served = await fake.create_prediction(
        json.loads(v2.prediction_request_document_text)
    )
    response_text = served.response_text
    response_sha = text_sha256(response_text)
    assert response_sha == v2.artifact_sha256
    return replace(
        v2,
        plan_id=_V1_PLAN_ID,
        prediction_response_document_text=response_text,
        prediction_response_sha256=response_sha,
        draft_content_hash=control_plan_draft_hash(
            build_draft_hash_document(
                v2.canonical_input_document_text,
                v2.optimizer_result_document_text,
                v2.prediction_request_document_text,
                response_sha,
            )
        ),
        provenance_version=None,
        prediction_identity_version=None,
        engine_id=None,
        engine_semantic_contract_version=None,
        engine_build_digest=None,
        engine_descriptor_content_hash=None,
        artifact_sha256=None,
        artifact_uncompressed_size_bytes=None,
        artifact_media_type=None,
        artifact_encoding=None,
        artifact_encoding_version=None,
        coverage_summary_document_text=None,
        coverage_summary_sha256=None,
        predicted_delivery_ledger_sha256=None,
    )


def _with_approved_history(record):
    """Extend a draft-only record with a full review→approve transition chain so
    the history projection has non-trivial documents to preserve verbatim."""
    created_at = record.created_at or datetime(2026, 7, 20, tzinfo=timezone.utc)
    approval_text = json.dumps(TRUSTED_APPROVAL_DOCUMENT, separators=(",", ":"))
    transitions = (
        record.transitions[0],
        TransitionRecord(
            transition_sequence=2,
            transition_type="review_requested",
            from_state="draft",
            to_state="under_review",
            actor_subject="supervisor-1",
            reason="ready",
            transition_document_text=None,
            occurred_at=created_at,
        ),
        TransitionRecord(
            transition_sequence=3,
            transition_type="shadow_approved",
            from_state="under_review",
            to_state="approved_for_shadow",
            actor_subject="supervisor-1",
            reason="coverage verified",
            transition_document_text=approval_text,
            occurred_at=created_at,
        ),
    )
    return replace(record, transitions=transitions)


def _independent_bounds(values):
    """Min/lower, middle/nominal, max/upper — reimplemented in the test (NOT via
    the projection's own ``_bounds``) so the oracle is independent of the code under
    test."""
    present = [v for v in values if v is not None]
    return MemberBoundsOut(
        lower_bound=min(present) if present else None,
        nominal=values[1] if len(values) == 3 else None,
        upper_bound=max(present) if present else None,
    )


def _expected_ledger_response(record) -> ControlPlanLedgerResponse:
    """An INDEPENDENT oracle for the ledger projection: the former
    ``_ledger_response_from_record`` output, reconstructed field-by-field from the
    fixture's raw ledger/requirement/event rows WITHOUT calling
    ``build_ledger_projection`` (so the equivalence assertion is not the builder
    compared against itself). Delivered/transit bounds are min/max, remaining is
    ``max(0, required - delivered)`` with the member envelope INVERTED (least
    delivered → most remaining), and the per-gate handover verdict comes from the
    domain primitive ``evaluate_safe_handover`` directly."""
    entries = []
    for entry in record.ledger_entries:
        delivered = _independent_bounds(
            [
                entry.lower_delivered_m3,
                entry.nominal_delivered_m3,
                entry.upper_delivered_m3,
            ]
        )

        def remaining(value):
            return (
                None
                if value is None
                else max(0.0, entry.required_volume_m3 - value)
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
                path_in_transit_m3=_independent_bounds(
                    [
                        entry.lower_path_in_transit_m3,
                        entry.nominal_path_in_transit_m3,
                        entry.upper_path_in_transit_m3,
                    ]
                ),
                remaining_m3=MemberBoundsOut(
                    lower_bound=remaining(delivered.upper_bound),
                    nominal=remaining(delivered.nominal),
                    upper_bound=remaining(delivered.lower_bound),
                ),
                checkpoint_reasons=list(entry.checkpoint_reasons),
            )
        )

    scheduled = [
        requirement
        for requirement in record.requirements
        if requirement.planning_disposition == "scheduled"
    ]
    gate_events = [
        GateEvent(
            gate_id=event.gate_id,
            kind=event.event_kind,
            planned_at=event.planned_at,
            target_position_m=event.target_position_m,
        )
        for event in record.events
    ]
    by_gate: dict = {}
    for requirement in scheduled:
        by_gate.setdefault(requirement.gate_id, []).append(
            ScheduledRequirement(
                requirement_id=str(requirement.requirement_id),
                section_id=requirement.section_id,
                gate_id=requirement.gate_id,
                required_volume_m3=requirement.required_volume_m3,
                approved_excess_m3=requirement.approved_excess_m3,
                path_reach_ids=tuple(
                    json.loads(requirement.path_reach_ids_document_text)
                ),
                window_start=requirement.window_start,
                window_end=requirement.window_end,
            )
        )
    handover = []
    for gate_id in sorted(by_gate):
        gate_requirements = by_gate[gate_id]
        verdict = evaluate_safe_handover(
            gate_requirements,
            record.ledger_entries,
            gate_events,
            all_members_completed=record.prediction_status == "completed",
        )
        handover.append(
            HandoverVerdictOut(
                gate_id=gate_id,
                requirement_ids=[r.requirement_id for r in gate_requirements],
                is_safe=verdict.is_safe,
                reasons=list(verdict.reasons),
            )
        )
    return ControlPlanLedgerResponse(
        plan_id=record.plan_id,
        plan_version=record.plan_version,
        prediction_run_id=record.prediction_run_id,
        prediction_status=record.prediction_status,
        ledger_sha256=predicted_delivery_ledger_sha256(record.ledger_entries),
        entries=entries,
        handover=handover,
    )


def _reforge_lineage(entry, prediction_run_id, prediction_response_sha256):
    """Rebuild a ledger entry so it references a DIFFERENT prediction while staying
    INDIVIDUALLY hash-valid: the mutated run id / content sha are written into both
    the columns AND the hashed projection document, and the row hash is recomputed.
    ``verify_ledger_entry_columns`` therefore accepts it — only the per-row lineage
    guard against the plan header can reject it."""
    document = json.loads(entry.projection_document_text)
    document["prediction_run_id"] = prediction_run_id
    document["prediction_response_sha256"] = prediction_response_sha256
    text = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return replace(
        entry,
        prediction_run_id=prediction_run_id,
        prediction_response_sha256=prediction_response_sha256,
        projection_document_text=text,
        projection_sha256=ledger_row_sha256(text),
    )


# The run-level heavy documents a bounded read must NEVER select.
_RUN_LARGE_DOCS = (
    "optimizer_result_document_text",
    "prediction_response_document_text",
    "prediction_request_document_text",
    "canonical_input_document_text",
    "model_snapshot_document_text",
)


def _compiled(stmt):
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()


# --- EQUIVALENCE: bounded projection == projection from the full detail --------
@pytest.mark.asyncio
async def test_coverage_projection_equals_full_aggregate_coverage():
    for record in (await _v2_record(), await _v1_record(await _v2_record())):
        detail = _response_from_record(record)  # the full _assemble detail
        coverage = build_prediction_coverage(record)
        assert isinstance(coverage, ControlPlanPredictionCoverageResponse)
        # Every coverage field equals the detail's — proven independently (two
        # different builders over the same record).
        assert coverage.plan_id == detail.plan_id
        assert coverage.plan_version == detail.plan_version
        assert coverage.requirement_run_id == detail.requirement_run_id
        assert coverage.requirement_version == detail.requirement_version
        assert coverage.model_snapshot_id == detail.model_snapshot_id
        assert coverage.model_release_id == detail.model_release_id
        assert (
            coverage.model_release_content_hash
            == detail.model_release_content_hash
        )
        assert coverage.input_content_hash == detail.input_content_hash
        assert coverage.draft_content_hash == detail.draft_content_hash
        assert coverage.optimizer_status == detail.optimizer_status
        assert coverage.prediction_status == detail.prediction_status
        assert coverage.prediction_run_id == detail.prediction_run_id
        assert (
            coverage.prediction_member_statuses
            == detail.prediction_member_statuses
        )
        # A completed 3-member prediction really is present (not a vacuous pass).
        assert [m.status for m in coverage.prediction_member_statuses] == [
            "completed",
            "completed",
            "completed",
        ]


@pytest.mark.asyncio
async def test_history_projection_equals_full_aggregate_history():
    for base in (await _v2_record(), await _v1_record(await _v2_record())):
        record = _with_approved_history(base)
        detail = _response_from_record(record)
        history = build_lifecycle_history(record, record.transitions)
        assert isinstance(history, ControlPlanLifecycleHistoryResponse)
        assert history.plan_id == detail.plan_id
        assert history.plan_version == detail.plan_version
        assert history.lifecycle_state == detail.lifecycle_state
        assert history.lifecycle_state == "approved_for_shadow"
        assert history.created_by_subject == detail.created_by_subject
        assert history.created_at == detail.created_at
        assert history.transitions == detail.transitions
        # The frozen shadow-approval document survives verbatim (not stripped).
        assert (
            history.transitions[-1].transition_document
            == TRUSTED_APPROVAL_DOCUMENT
        )


@pytest.mark.asyncio
async def test_ledger_projection_equals_full_aggregate_ledger():
    for record in (await _v2_record(), await _v1_record(await _v2_record())):
        ledger = build_ledger_projection(
            record, record.ledger_entries, record.events, record.requirements
        )
        assert isinstance(ledger, ControlPlanLedgerResponse)
        # FIX 5: the oracle is an INDEPENDENT reconstruction (not the builder
        # compared against a stripped copy of itself) — every entry, its bounds,
        # remaining envelope, checkpoint reasons, the handover verdict, and the
        # ledger sha must equal it exactly.
        assert ledger == _expected_ledger_response(record)
        # Projecting from a record whose heavy run-level documents are stripped
        # (exactly what the bounded query never loads) still yields the SAME ledger.
        stripped = replace(
            record,
            optimizer_result_document_text="{}",
            model_snapshot_document_text="{}",
            canonical_input_document_text="{}",
            prediction_request_document_text=None,
            prediction_response_document_text=None,
        )
        assert (
            build_ledger_projection(
                stripped,
                stripped.ledger_entries,
                stripped.events,
                stripped.requirements,
            )
            == ledger
        )
        # Hard-coded ground truth for THIS fixture: 6 checkpoint rows and a single
        # safe handover for gate G1 (open→close events, all members completed).
        assert ledger.ledger_sha256 == predicted_delivery_ledger_sha256(
            record.ledger_entries
        )
        assert len(ledger.entries) == 6
        assert ledger.handover == [
            HandoverVerdictOut(
                gate_id="G1",
                requirement_ids=[REQ_ID],
                is_safe=True,
                reasons=[],
            )
        ]


# --- BOUNDEDNESS: the SELECTs name no large document --------------------------
def test_projection_queries_omit_large_document_columns():
    plan_id = UUID("11111111-0000-4000-8000-000000000000")
    statements = {
        "coverage": coverage_query(plan_id, 1),
        "history_header": history_header_query(plan_id, 1),
        "history_transitions": history_transitions_query(plan_id, 1),
        "ledger_run": ledger_run_query(plan_id, 1),
        "ledger_entries": ledger_entries_query(plan_id, 1),
        "ledger_requirements": ledger_requirements_query(plan_id, 1),
        "ledger_events": ledger_events_query(plan_id, 1, ["G1"]),
    }
    for name, stmt in statements.items():
        compiled = _compiled(stmt)
        for column in _RUN_LARGE_DOCS:
            assert column not in compiled, f"{name} must not select {column}"
        # No v2 read may ever select the discarded prediction response.
        assert "prediction_response_document_text" not in compiled

    # The coverage read is a single header row that DOES carry the small
    # per-member summaries but touches NONE of the heavy child tables.
    coverage_sql = _compiled(statements["coverage"])
    assert "prediction_member_summaries" in coverage_sql
    for table in (
        "control_state_transitions",
        "control_plan_requirements",
        "gate_plan_events",
        "section_delivery_ledger",
    ):
        assert table not in coverage_sql

    # History reads its OWN identity + the transition rows (documents included —
    # history needs them) and nothing else.
    header_sql = _compiled(statements["history_header"])
    assert "control_state_transitions" not in header_sql
    trans_sql = _compiled(statements["history_transitions"])
    assert "control_state_transitions" in trans_sql
    assert "transition_document_text" in trans_sql
    for table in ("control_plan_requirements", "gate_plan_events",
                  "section_delivery_ledger"):
        assert table not in trans_sql

    # The ledger requirement read omits the heavy per-requirement document but
    # keeps the small path_reach_ids the handover verdict needs, and (FIX 6) filters
    # to scheduled requirements in SQL rather than dropping others in Python.
    req_sql = _compiled(statements["ledger_requirements"])
    assert "requirement_document_text" not in req_sql
    assert "path_reach_ids_document_text" in req_sql
    assert "planning_disposition" in req_sql and "scheduled" in req_sql

    # (FIX 6) The gate-event read is restricted to the referenced gates in SQL.
    event_sql = _compiled(statements["ledger_events"])
    assert "gate_id in ('g1')" in event_sql


def test_coverage_and_ledger_queries_are_single_plan_snapshots():
    # Each read is keyed by (plan_id, plan_version): a single row / a single
    # plan's children, never a scan.
    plan_id = UUID("22222222-0000-4000-8000-000000000000")
    for stmt in (
        coverage_query(plan_id, 4),
        ledger_run_query(plan_id, 4),
    ):
        compiled = _compiled(stmt)
        assert "plan_version = 4" in compiled
        assert str(plan_id) in compiled


# --- CORRUPTION: fail closed, never a partial projection ----------------------
@pytest.mark.asyncio
async def test_corrupt_member_summaries_raise_projection_corrupt():
    record = replace(await _v2_record(), prediction_member_summaries="{not json")
    with pytest.raises(ProjectionCorruptError):
        build_prediction_coverage(record)


@pytest.mark.asyncio
async def test_corrupt_transition_document_raises_projection_corrupt():
    record = await _v2_record()
    tampered = replace(
        record,
        transitions=(
            replace(
                record.transitions[0],
                transition_document_text="{broken",
            ),
        ),
    )
    with pytest.raises(ProjectionCorruptError):
        build_lifecycle_history(tampered, tampered.transitions)


@pytest.mark.asyncio
async def test_corrupt_lifecycle_history_raises_history_corrupt():
    # An empty history is corruption (the atomic store always lands draft_created).
    record = replace(await _v2_record(), transitions=())
    with pytest.raises(LifecycleHistoryCorruptError):
        build_lifecycle_history(record, record.transitions)


@pytest.mark.asyncio
async def test_tampered_ledger_row_raises_projection_corrupt():
    record = await _v2_record()
    assert record.ledger_entries  # the fixture really has ledger rows
    tampered_entries = (
        replace(record.ledger_entries[0], required_volume_m3=-1.0),
    ) + record.ledger_entries[1:]
    with pytest.raises(ProjectionCorruptError):
        build_ledger_projection(
            record, tampered_entries, record.events, record.requirements
        )


@pytest.mark.asyncio
async def test_v2_ledger_hash_mismatch_raises_projection_corrupt():
    record = replace(
        await _v2_record(), predicted_delivery_ledger_sha256="0" * 64
    )
    with pytest.raises(ProjectionCorruptError):
        build_ledger_projection(
            record, record.ledger_entries, record.events, record.requirements
        )


# --- FIX 1: per-row ledger lineage against the plan header --------------------
@pytest.mark.asyncio
async def test_ledger_rows_from_another_prediction_raise_projection_corrupt():
    # Every ledger row is swapped for an INDIVIDUALLY hash-valid row of a DIFFERENT
    # prediction, and the whole-ledger sha is realigned to the swapped set — so only
    # the per-row lineage guard (row.prediction_run_id / sha == header's) can catch
    # it. Without that guard this would serve a foreign plan's ledger as 200.
    record = await _v2_record()
    foreign = tuple(
        _reforge_lineage(entry, "e" * 64, "f" * 64)
        for entry in record.ledger_entries
    )
    tampered = replace(
        record,
        predicted_delivery_ledger_sha256=predicted_delivery_ledger_sha256(
            foreign
        ),
    )
    with pytest.raises(ProjectionCorruptError):
        build_ledger_projection(
            tampered, foreign, record.events, record.requirements
        )


@pytest.mark.asyncio
async def test_v1_ledger_row_lineage_mismatch_raises_projection_corrupt():
    # A v1 header (no whole-ledger sha) still binds every row to its own
    # prediction_response_sha256 — a row whose content sha drifts from the header's
    # is corruption on the v1 path too.
    v1 = await _v1_record(await _v2_record())
    foreign = (
        _reforge_lineage(v1.ledger_entries[0], v1.prediction_run_id, "f" * 64),
    ) + v1.ledger_entries[1:]
    with pytest.raises(ProjectionCorruptError):
        build_ledger_projection(v1, foreign, v1.events, v1.requirements)


@pytest.mark.asyncio
async def test_unknown_provenance_version_raises_projection_corrupt():
    # An unrecognised provenance_version must never be dispatched to the v1 path
    # (which would skip the v2 artifact checks) — reject it on BOTH reads.
    record = replace(await _v2_record(), provenance_version=3)
    with pytest.raises(ProjectionCorruptError):
        build_ledger_projection(
            record, record.ledger_entries, record.events, record.requirements
        )
    with pytest.raises(ProjectionCorruptError):
        build_prediction_coverage(record)


# --- FIX 2: v2 coverage member-summary authentication ------------------------
@pytest.mark.asyncio
async def test_v2_mutated_member_status_raises_projection_corrupt():
    # A WELL-FORMED mutation of the served summaries (completed→infeasible) that no
    # longer agrees with the hash-authenticated coverage summary → 503, exactly
    # where _assemble (which re-verifies the draft hash) fails closed.
    record = await _v2_record()
    summaries = json.loads(record.prediction_member_summaries)
    summaries[0]["status"] = "infeasible"
    mutated = replace(
        record,
        prediction_member_summaries=json.dumps(
            summaries, separators=(",", ":")
        ),
    )
    with pytest.raises(ProjectionCorruptError):
        build_prediction_coverage(mutated)


@pytest.mark.asyncio
async def test_v2_nulled_member_summaries_raise_projection_corrupt():
    # Nulling the served summaries where the coverage summary still names three
    # members is a mismatch → 503 (never a silent empty-coverage 200).
    record = replace(await _v2_record(), prediction_member_summaries=None)
    with pytest.raises(ProjectionCorruptError):
        build_prediction_coverage(record)


@pytest.mark.asyncio
async def test_v2_consistent_coverage_returns_exact_statuses():
    # The positive: a consistent v2 record authenticates and serves the exact
    # per-member statuses (proves the authentication is not a blanket reject).
    coverage = build_prediction_coverage(await _v2_record())
    assert [m.status for m in coverage.prediction_member_statuses] == [
        "completed",
        "completed",
        "completed",
    ]


# --- FIX 4: well-formed-but-schema-invalid stored JSON is 503, not 500 --------
@pytest.mark.asyncio
async def test_coverage_unknown_member_status_raises_projection_corrupt():
    # Valid JSON, unknown enum value: a Pydantic ValidationError must be wrapped as
    # corruption (503), not escape as an opaque 500.
    record = await _v2_record()
    summaries = json.loads(record.prediction_member_summaries)
    summaries[0]["status"] = "bogus_status"
    mutated = replace(
        record,
        prediction_member_summaries=json.dumps(
            summaries, separators=(",", ":")
        ),
    )
    with pytest.raises(ProjectionCorruptError):
        build_prediction_coverage(mutated)


@pytest.mark.asyncio
async def test_transition_document_array_raises_projection_corrupt():
    # A transition_document that is a JSON ARRAY (valid JSON, wrong shape) must be
    # wrapped as corruption (503), not raise a bare Pydantic/TypeError 500.
    record = await _v2_record()
    tampered = replace(
        record,
        transitions=(
            replace(
                record.transitions[0],
                transition_document_text="[1, 2, 3]",
            ),
        ),
    )
    with pytest.raises(ProjectionCorruptError):
        build_lifecycle_history(tampered, tampered.transitions)
