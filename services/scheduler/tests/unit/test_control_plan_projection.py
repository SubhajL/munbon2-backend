"""Bounded control-plan list projection (PR 4.4a-3).

The DB-touching keyset walk over real rows lives in the env-gated integration
suite; here the LOGIC is proven against the in-memory fake (stable ordering, no
duplicates/gaps across a cursor walk, exact filters, derived lifecycle/trust) and
the bounded SELECT is proven by compiling the query and asserting it names NO
large-document column and never calls ``_assemble``.
"""

import inspect
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

import repositories.control_plan_projection_repository as projection_module
from repositories.control_plan_projection_repository import (
    PostgresControlPlanProjectionRepository,
    build_summary_query,
)
from schemas.control_plan import (
    PROJECTION_SCHEMA_VERSION,
    ControlPlanListFilters,
)
from tests.control_plan_test_support import (
    TRUSTED_APPROVAL_DOCUMENT,
    UNTRUSTED_APPROVAL_DOCUMENT,
    FakeControlPlanProjectionRepository,
    projection_record,
)

# Distinct plan ids ordered lexically so the (created_at, plan_id) DESC tie-break
# is observable; created_at ascending with the ids so the two axes disagree.
_IDS = [UUID(f"{n:08x}-0000-4000-8000-000000000000") for n in range(1, 8)]


def _records():
    base = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)
    records = []
    for i, plan_id in enumerate(_IDS):
        records.append(
            projection_record(
                plan_id,
                created_at=base.replace(minute=i),
                lifecycle="draft",
            )
        )
    return records


async def _walk(repo, *, limit, filters=None):
    """Page through the whole list following next_cursor; return the flat list of
    (created_at, plan_id) in served order."""
    filters = filters or ControlPlanListFilters()
    seen = []
    cursor = None
    pages = 0
    while True:
        page = await repo.list_plan_summaries(
            None, filters=filters, cursor=cursor, limit=limit
        )
        seen.extend((item.created_at, item.plan_id) for item in page.items)
        pages += 1
        assert pages < 100, "pagination did not terminate"
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    return seen


async def _walk_full(repo, *, limit, filters=None):
    """Page through the whole list following next_cursor; return the flat list of
    (created_at, plan_id, plan_version) — the row's TOTAL identity — in served
    order (so tie-break rows sharing created_at and/or plan_id stay distinct)."""
    filters = filters or ControlPlanListFilters()
    seen = []
    cursor = None
    pages = 0
    while True:
        page = await repo.list_plan_summaries(
            None, filters=filters, cursor=cursor, limit=limit
        )
        seen.extend(
            (item.created_at, item.plan_id, item.plan_version)
            for item in page.items
        )
        pages += 1
        assert pages < 100, "pagination did not terminate"
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    return seen


@pytest.mark.asyncio
async def test_list_keyset_breaks_ties_on_plan_version_at_limit_one():
    # Two rows share BOTH created_at AND plan_id, differing ONLY in plan_version.
    # Without plan_version in the keyset the predicate (created_at, plan_id) <
    # (same, same) is false for the second row → a silent gap. limit=1 forces the
    # cursor to carry the tie-break.
    created_at = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)
    plan_id = _IDS[0]
    records = [
        projection_record(plan_id, created_at=created_at, plan_version=1),
        projection_record(plan_id, created_at=created_at, plan_version=2),
    ]
    walked = await _walk_full(
        FakeControlPlanProjectionRepository(records), limit=1
    )
    # Both versions served, once each, in plan_version DESC order — no gap/dup.
    assert walked == [
        (created_at, plan_id, 2),
        (created_at, plan_id, 1),
    ]
    assert len(walked) == len(set(walked)) == 2


@pytest.mark.asyncio
async def test_list_keyset_walks_equal_created_at_rows_without_dup_or_gap():
    # >=3 rows sharing an IDENTICAL created_at, distinguished only by (plan_id,
    # plan_version): the equal-created_at tie-break is exercised directly at
    # limit=1 (page size 1 so each hop relies solely on the cursor tie-break).
    created_at = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)
    records = [
        projection_record(_IDS[0], created_at=created_at, plan_version=1),
        projection_record(_IDS[1], created_at=created_at, plan_version=1),
        projection_record(_IDS[2], created_at=created_at, plan_version=3),
    ]
    walked = await _walk_full(
        FakeControlPlanProjectionRepository(records), limit=1
    )
    expected = sorted(
        ((r.created_at, r.plan_id, r.plan_version) for r in records),
        reverse=True,
    )
    assert walked == expected
    assert len(walked) == len(set(walked)) == 3


@pytest.mark.asyncio
async def test_list_orders_stably_without_duplicates_or_gaps():
    repo = FakeControlPlanProjectionRepository(_records())
    walked = await _walk(repo, limit=2)

    expected = sorted(
        ((r.created_at, r.plan_id) for r in _records()), reverse=True
    )
    assert walked == expected  # every row, once, in created_at DESC, plan_id DESC
    assert len(walked) == len(set(walked)) == len(_IDS)


@pytest.mark.asyncio
async def test_list_walk_is_independent_of_page_size():
    records = _records()
    by_one = await _walk(FakeControlPlanProjectionRepository(records), limit=1)
    by_five = await _walk(FakeControlPlanProjectionRepository(records), limit=5)
    assert by_one == by_five


@pytest.mark.asyncio
async def test_list_next_cursor_absent_on_the_final_page():
    repo = FakeControlPlanProjectionRepository(_records())
    page = await repo.list_plan_summaries(
        None, filters=ControlPlanListFilters(), cursor=None, limit=len(_IDS)
    )
    assert len(page.items) == len(_IDS)
    assert page.next_cursor is None
    assert page.projection_schema_version == PROJECTION_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_list_filters_lifecycle_horizon_and_lineage():
    approved = projection_record(
        _IDS[0],
        created_at=datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc),
        lifecycle="approved_for_shadow",
        approval_document=TRUSTED_APPROVAL_DOCUMENT,
        requirement_version=5,
        model_snapshot_id="f" * 64,
    )
    other = projection_record(
        _IDS[1],
        created_at=datetime(2026, 7, 18, 8, 1, tzinfo=timezone.utc),
        lifecycle="draft",
        requirement_version=3,
        model_snapshot_id="e" * 64,
    )
    repo = FakeControlPlanProjectionRepository([approved, other])

    by_state = await repo.list_plan_summaries(
        None,
        filters=ControlPlanListFilters(lifecycle_state="approved_for_shadow"),
        cursor=None,
        limit=25,
    )
    assert [i.plan_id for i in by_state.items] == [_IDS[0]]

    by_version = await repo.list_plan_summaries(
        None,
        filters=ControlPlanListFilters(requirement_version=3),
        cursor=None,
        limit=25,
    )
    assert [i.plan_id for i in by_version.items] == [_IDS[1]]

    by_snapshot = await repo.list_plan_summaries(
        None,
        filters=ControlPlanListFilters(model_snapshot_id="f" * 64),
        cursor=None,
        limit=25,
    )
    assert [i.plan_id for i in by_snapshot.items] == [_IDS[0]]


@pytest.mark.asyncio
async def test_list_page_derives_lifecycle_state_and_approval_trust():
    trusted = projection_record(
        _IDS[0],
        created_at=datetime(2026, 7, 18, 8, 2, tzinfo=timezone.utc),
        lifecycle="approved_for_shadow",
        approval_document=TRUSTED_APPROVAL_DOCUMENT,
    )
    untrusted = projection_record(
        _IDS[1],
        created_at=datetime(2026, 7, 18, 8, 1, tzinfo=timezone.utc),
        lifecycle="approved_for_shadow",
        approval_document=UNTRUSTED_APPROVAL_DOCUMENT,
    )
    plain_draft = projection_record(
        _IDS[2],
        created_at=datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc),
        lifecycle="draft",
    )
    repo = FakeControlPlanProjectionRepository([trusted, untrusted, plain_draft])
    page = await repo.list_plan_summaries(
        None, filters=ControlPlanListFilters(), cursor=None, limit=25
    )
    by_id = {item.plan_id: item for item in page.items}

    assert by_id[_IDS[0]].lifecycle_state == "approved_for_shadow"
    assert by_id[_IDS[0]].approval_trust is True
    # A compat-mode v2 approval is a real approval but NOT trusted.
    assert by_id[_IDS[1]].lifecycle_state == "approved_for_shadow"
    assert by_id[_IDS[1]].approval_trust is False
    # A plain draft carries no approval at all.
    assert by_id[_IDS[2]].lifecycle_state == "draft"
    assert by_id[_IDS[2]].approval_trust is False


@pytest.mark.asyncio
async def test_cursor_from_one_filter_set_is_rejected_on_another():
    from core.control_plan_cursor import CursorError

    repo = FakeControlPlanProjectionRepository(_records())
    page = await repo.list_plan_summaries(
        None,
        filters=ControlPlanListFilters(lifecycle_state="draft"),
        cursor=None,
        limit=2,
    )
    assert page.next_cursor is not None
    # Replaying that cursor against a DIFFERENT filter set fails closed.
    with pytest.raises(CursorError):
        await repo.list_plan_summaries(
            None,
            filters=ControlPlanListFilters(lifecycle_state="under_review"),
            cursor=page.next_cursor,
            limit=2,
        )


_LARGE_DOCUMENT_COLUMNS = (
    "optimizer_result_document_text",
    "prediction_response_document_text",
    "prediction_request_document_text",
    "canonical_input_document_text",
    "model_snapshot_document_text",
    "prediction_member_summaries",
)


def test_list_summary_omits_all_large_documents():
    stmt = build_summary_query(ControlPlanListFilters(), None, 25)
    compiled = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    # No large document column may be selected ...
    for column in _LARGE_DOCUMENT_COLUMNS:
        assert column not in compiled, f"{column} must not appear in the list query"
    # ... and the projection never joins the heavy child tables.
    for table in (
        "control_plan_requirements",
        "gate_plan_events",
        "section_delivery_ledger",
    ):
        assert table not in compiled, f"{table} must not appear in the list query"

    # It IS ordered created_at DESC, plan_id DESC, plan_version DESC (the row's
    # TOTAL identity) and fetches limit+1.
    assert (
        "order by scheduler.control_plan_runs.created_at desc, "
        "scheduler.control_plan_runs.plan_id desc, "
        "scheduler.control_plan_runs.plan_version desc" in compiled
    )
    assert "limit 26" in compiled


def test_list_summary_loads_only_the_shadow_approval_document():
    # The bounded projection derives state from a to_state subquery and loads at
    # most ONE small approval document per row — never every transition document.
    compiled = str(
        build_summary_query(ControlPlanListFilters(), None, 25).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    # transition_document_text is selected exactly once, and only under the
    # transition_type = 'shadow_approved' predicate — so no non-approval document
    # is ever loaded.
    assert compiled.count("transition_document_text") == 1
    assert "transition_type = 'shadow_approved'" in compiled
    # The state-derivation subquery selects to_state (never the document).
    assert "control_state_transitions.to_state" in compiled


def test_projection_repository_never_calls_assemble():
    source = inspect.getsource(projection_module)
    # The full-aggregate detail path must never be reached from the projection:
    # no call to `_assemble(...)` and no import of the detail repository.
    assert "_assemble(" not in source
    assert "from repositories.control_plan_repository import" not in source


def test_fake_pins_the_real_projection_repository_interface():
    real = inspect.signature(
        PostgresControlPlanProjectionRepository.list_plan_summaries
    )
    fake = inspect.signature(
        FakeControlPlanProjectionRepository.list_plan_summaries
    )
    assert list(real.parameters) == list(fake.parameters)
    assert set(fake.parameters) == {"self", "session", "filters", "cursor", "limit"}
