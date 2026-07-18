"""Real-Postgres proof for the 0001 control-plan migration and repository.

Env-gated: set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback Postgres.
Non-loopback hosts raise (guard shared with test_scheduler_postgres)."""

import asyncio
from functools import partial
from uuid import UUID

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import migrations.migrate as migrate
from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from repositories.control_plan_repository import (
    PostgresControlPlanRepository,
)
from schemas.control_plan import DraftControlPlanRequest
from services.control_plan_service import ControlPlanDraftService
from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)
from tests.integration.test_scheduler_postgres import _test_url_loopback

MIGRATION_ID = "0001_control_plan_drafts"
LEDGER_MIGRATION_ID = "0002_predicted_delivery_ledger"
LIFECYCLE_MIGRATION_ID = "0003_control_plan_review_lifecycle"
LIST_INDEX_MIGRATION_ID = "0004_control_plan_list_indexes"
LIST_INDEXES = (
    "scheduler.control_plan_runs_created_at_plan_id_idx",
    "scheduler.control_plan_runs_model_snapshot_id_idx",
    "scheduler.control_plan_runs_prediction_run_id_idx",
    "scheduler.control_plan_runs_requirement_run_id_idx",
    "scheduler.control_plan_runs_horizon_idx",
)
LEDGER_TABLE = "scheduler.section_delivery_ledger"
PLAN_TABLES = (
    "scheduler.control_plan_runs",
    "scheduler.control_plan_requirements",
    "scheduler.gate_plan_events",
    "scheduler.control_state_transitions",
)
TABLES = PLAN_TABLES + (LEDGER_TABLE,)

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None,
    reason="SCHEDULER_TEST_POSTGRES_URL not set",
)


async def _connect():
    url = _test_url_loopback()
    kwargs = migrate.postgres_connection_kwargs(url)
    return await asyncpg.connect(**kwargs)


async def _regclass(conn, table):
    return await conn.fetchval("SELECT to_regclass($1)", table)


async def _require_disposable(conn):
    for table in TABLES:
        if await _regclass(conn, table) is not None:
            raise RuntimeError(
                f"{table} already exists; refuse to run against a "
                "non-disposable database"
            )


def _sqlalchemy_url():
    url = _test_url_loopback()
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


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


def _request():
    return DraftControlPlanRequest.model_validate(draft_payload())


def _service_vol(repository, volume):
    return ControlPlanDraftService(
        ros_client=FakeRosGisClient([requirement_item(volume=volume)]),
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


@pytest.mark.asyncio
async def test_control_plan_migration_and_repository_on_real_postgres():
    conn = await _connect()
    try:
        await _require_disposable(conn)

        # Apply -> all objects exist; reapply is a no-op.
        assert await migrate.apply_migration(conn, MIGRATION_ID) == "applied"
        for table in PLAN_TABLES:
            assert await _regclass(conn, table) is not None
        assert (
            await migrate.apply_migration(conn, MIGRATION_ID)
            == "already-applied"
        )

        # Rollback -> gone; reapply cleanly.
        assert (
            await migrate.rollback_migration(conn, MIGRATION_ID)
            == "rolled-back"
        )
        for table in PLAN_TABLES:
            assert await _regclass(conn, table) is None
        assert await migrate.apply_migration(conn, MIGRATION_ID) == "applied"
        # The ledger migration (0002) sits on top of the plan tables.
        assert (
            await migrate.apply_migration(conn, LEDGER_MIGRATION_ID)
            == "applied"
        )
        assert await _regclass(conn, LEDGER_TABLE) is not None

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        try:
            # Store one draft end-to-end through the real repository.
            async with sessions() as session:
                record, replayed = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
            assert not replayed
            assert record.created_at is not None
            assert record.transitions[0].occurred_at is not None

            # Exact reload round-trips.
            async with sessions() as session:
                loaded = await repository.load_draft_plan(
                    session, record.plan_id, record.plan_version
                )
            assert loaded is not None
            assert loaded.input_content_hash == record.input_content_hash
            assert loaded.draft_content_hash == record.draft_content_hash
            assert loaded.requirements == record.requirements
            assert loaded.events == record.events
            # PR 5.1: the feasible draft persisted ledger rows atomically and
            # they reload byte-identically (row hashes re-verified on load).
            assert record.ledger_entries
            assert loaded.ledger_entries == record.ledger_entries
            ledger_count = await conn.fetchval(
                "SELECT count(*) FROM scheduler.section_delivery_ledger"
            )
            assert ledger_count == len(record.ledger_entries)

            # Replay: the same request returns the stored draft untouched.
            async with sessions() as session:
                replay_record, replay_flag = await _service(
                    repository
                ).create_draft(session, _request(), "operator-2")
            assert replay_flag
            assert replay_record.plan_id == record.plan_id

            # Immutability triggers reject UPDATE and DELETE on every table.
            for statement in (
                "UPDATE scheduler.control_plan_runs SET lifecycle_state = "
                "'draft'",
                "DELETE FROM scheduler.control_plan_runs",
                "UPDATE scheduler.control_plan_requirements SET zone = 2",
                "DELETE FROM scheduler.control_plan_requirements",
                "UPDATE scheduler.gate_plan_events SET gate_id = 'X'",
                "DELETE FROM scheduler.gate_plan_events",
                "UPDATE scheduler.control_state_transitions SET reason = 'x'",
                "DELETE FROM scheduler.control_state_transitions",
                "UPDATE scheduler.section_delivery_ledger SET status = "
                "'invalidated'",
                "DELETE FROM scheduler.section_delivery_ledger",
            ):
                with pytest.raises(
                    asyncpg.exceptions.RaiseError, match="immutable"
                ):
                    await conn.execute(statement)

            # Concurrent identical stores resolve to one committed version.
            async def _concurrent_create(subject):
                async with sessions() as session:
                    return await _service(repository).create_draft(
                        session, _request(), subject
                    )

            results = await asyncio.gather(
                _concurrent_create("operator-3"),
                _concurrent_create("operator-4"),
            )
            plan_ids = {result[0].plan_id for result in results}
            assert plan_ids == {record.plan_id}
            count = await conn.fetchval(
                "SELECT count(*) FROM scheduler.control_plan_runs"
            )
            assert count == 1

            # Solver nondeterminism: a second self-consistent record with the
            # SAME input but a different optimizer output/draft hash must replay
            # the winner, not 409. This mirrors two time-bounded CBC solves.
            import json as _json
            from dataclasses import replace as dc_replace

            from core.control_plan import (
                canonical_json_text,
                control_plan_draft_hash,
            )
            from repositories.control_plan_repository import (
                build_draft_hash_document,
                text_sha256,
            )

            divergent_optimizer = _json.loads(
                record.optimizer_result_document_text
            )
            divergent_optimizer["infeasible_reasons"] = ["divergent-solve"]
            divergent_optimizer_text = canonical_json_text(divergent_optimizer)
            divergent_draft_hash = control_plan_draft_hash(
                build_draft_hash_document(
                    record.canonical_input_document_text,
                    divergent_optimizer_text,
                    record.prediction_request_document_text,
                    record.prediction_response_sha256,
                )
            )
            divergent = dc_replace(
                record,
                plan_id=UUID("00000000-0000-4000-8000-0000000000ff"),
                optimizer_result_document_text=divergent_optimizer_text,
                optimizer_result_sha256=text_sha256(divergent_optimizer_text),
                draft_content_hash=divergent_draft_hash,
            )
            async with sessions() as session:
                replayed_record, replay_flag = await repository.store_draft_plan(
                    session, divergent
                )
            assert replay_flag
            assert replayed_record.plan_id == record.plan_id
            assert replayed_record.draft_content_hash == record.draft_content_hash

            # Atomicity: a child violating its constraints aborts everything.
            from dataclasses import replace as dc_replace

            async with sessions() as session:
                good, _ = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
            bad = dc_replace(
                good,
                input_content_hash="f" * 64,
                draft_content_hash="e" * 64,
                events=(
                    dc_replace(good.events[0], event_sequence=-1),
                ),
            )
            async with sessions() as session:
                with pytest.raises(Exception):
                    await repository.store_draft_plan(session, bad)
            count = await conn.fetchval(
                "SELECT count(*) FROM scheduler.control_plan_runs"
            )
            assert count == 1
        finally:
            await engine.dispose()
    finally:
        # Leave the disposable database empty for the next run (child first).
        try:
            await migrate.rollback_migration(conn, LEDGER_MIGRATION_ID)
            await migrate.rollback_migration(conn, MIGRATION_ID)
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_ledger_migration_apply_rollback_reapply_is_clean():
    conn = await _connect()
    try:
        for table in TABLES:
            if await _regclass(conn, table) is not None:
                raise RuntimeError(f"{table} exists; not a disposable database")
        assert await migrate.apply_migration(conn, MIGRATION_ID) == "applied"
        assert (
            await migrate.apply_migration(conn, LEDGER_MIGRATION_ID)
            == "applied"
        )
        assert await _regclass(conn, LEDGER_TABLE) is not None
        # An illegal ledger status is rejected by the CHECK constraint.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await conn.execute(
                "INSERT INTO scheduler.section_delivery_ledger ("
                "plan_id, plan_version, requirement_id, checkpoint_index, "
                "section_id, checkpoint_at, status, required_volume_m3, "
                "approved_excess_m3, checkpoint_reasons_document_text, "
                "projection_document_text, projection_sha256, "
                "prediction_run_id, prediction_response_sha256) VALUES ("
                "'00000000-0000-4000-8000-000000000001', 1, "
                "'00000000-0000-4000-8000-000000000002', 1, 'SEC', now(), "
                "'confirmed', 1.0, 0.0, '[]', '{}', "
                "'" + "a" * 64 + "', '" + "b" * 64 + "', '" + "c" * 64 + "')"
            )
        # Rollback drops only the ledger; the 0001 tables remain.
        assert (
            await migrate.rollback_migration(conn, LEDGER_MIGRATION_ID)
            == "rolled-back"
        )
        assert await _regclass(conn, LEDGER_TABLE) is None
        assert await _regclass(conn, "scheduler.control_plan_runs") is not None
        assert (
            await migrate.apply_migration(conn, LEDGER_MIGRATION_ID)
            == "applied"
        )
    finally:
        try:
            await migrate.rollback_migration(conn, LEDGER_MIGRATION_ID)
            await migrate.rollback_migration(conn, MIGRATION_ID)
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_0004_list_indexes_apply_rollback_reapply_and_apply_all():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        # apply-all discovers 0001..0004 in lexical order and applies each once.
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes[LIST_INDEX_MIGRATION_ID] == "applied"
        for index in LIST_INDEXES:
            assert await _regclass(conn, index) is not None

        # Rollback 0004 drops ONLY the indexes; the runs table (and its rows'
        # home) stays intact.
        assert (
            await migrate.rollback_migration(conn, LIST_INDEX_MIGRATION_ID)
            == "rolled-back"
        )
        for index in LIST_INDEXES:
            assert await _regclass(conn, index) is None
        assert await _regclass(conn, "scheduler.control_plan_runs") is not None

        # Reapply cleanly; a second apply is a no-op.
        assert (
            await migrate.apply_migration(conn, LIST_INDEX_MIGRATION_ID)
            == "applied"
        )
        assert (
            await migrate.apply_migration(conn, LIST_INDEX_MIGRATION_ID)
            == "already-applied"
        )
        for index in LIST_INDEXES:
            assert await _regclass(conn, index) is not None
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_list_projection_keyset_over_real_rows_no_dup_or_gap():
    from repositories.control_plan_projection_repository import (
        PostgresControlPlanProjectionRepository,
    )
    from schemas.control_plan import ControlPlanListFilters

    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        projection = PostgresControlPlanProjectionRepository()
        try:
            # Five distinct drafts (distinct volumes → distinct input hashes →
            # distinct plan_ids), each committed in its own transaction so the
            # created_at timestamps advance.
            created = []
            for volume in (6000.0, 6100.0, 6200.0, 6300.0, 6400.0):
                async with sessions() as session:
                    record, _ = await _service_vol(
                        repository, volume
                    ).create_draft(session, _request(), "operator-1")
                created.append(record.plan_id)
            assert len(set(created)) == 5

            # Walk the whole list with limit=2 following next_cursor.
            walked = []
            cursor = None
            filters = ControlPlanListFilters()
            for _ in range(10):
                async with sessions() as session:
                    page = await projection.list_plan_summaries(
                        session, filters=filters, cursor=cursor, limit=2
                    )
                walked.extend(
                    (item.created_at, item.plan_id) for item in page.items
                )
                if page.next_cursor is None:
                    break
                cursor = page.next_cursor

            # Every plan, exactly once, in created_at DESC, plan_id DESC order.
            assert {plan_id for _, plan_id in walked} == set(created)
            assert len(walked) == len(set(walked)) == 5
            assert walked == sorted(walked, reverse=True)

            # A lineage filter narrows the page to matching rows only.
            async with sessions() as session:
                one = await projection.list_plan_summaries(
                    session,
                    filters=ControlPlanListFilters(requirement_version=3),
                    cursor=None,
                    limit=50,
                )
            assert len(one.items) == 5  # all five share requirement_version 3
            assert all(item.optimizer_status == "feasible" for item in one.items)
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_list_keyset_breaks_ties_on_plan_version_real_postgres():
    from repositories.control_plan_projection_repository import (
        PostgresControlPlanProjectionRepository,
    )
    from schemas.control_plan import ControlPlanListFilters

    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        projection = PostgresControlPlanProjectionRepository()
        try:
            async with sessions() as session:
                record, _ = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
            plan_id = record.plan_id

            # Hand-insert a SECOND version of the same plan sharing the SAME
            # created_at (only plan_version + the two unique hashes differ), plus
            # its draft_created transition — the exact pair a (created_at, plan_id)
            # keyset would collapse into a single indistinguishable key.
            run = dict(
                await conn.fetchrow(
                    "SELECT * FROM scheduler.control_plan_runs "
                    "WHERE plan_id = $1 AND plan_version = 1",
                    plan_id,
                )
            )
            run["plan_version"] = 2
            run["input_content_hash"] = "f" * 64
            run["draft_content_hash"] = "e" * 64
            columns = list(run)
            placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
            await conn.execute(
                "INSERT INTO scheduler.control_plan_runs "
                f"({', '.join(columns)}) VALUES ({placeholders})",
                *[run[c] for c in columns],
            )
            await conn.execute(
                "INSERT INTO scheduler.control_state_transitions ("
                "plan_id, plan_version, transition_sequence, transition_type, "
                "from_state, to_state, actor_subject) VALUES ("
                "$1, 2, 1, 'draft_created', NULL, 'draft', 'operator-1')",
                plan_id,
            )

            # Walk with limit=1 so every hop relies solely on the cursor tie-break.
            walked = []
            cursor = None
            filters = ControlPlanListFilters()
            for _ in range(10):
                async with sessions() as session:
                    page = await projection.list_plan_summaries(
                        session, filters=filters, cursor=cursor, limit=1
                    )
                walked.extend(
                    (item.plan_id, item.plan_version) for item in page.items
                )
                if page.next_cursor is None:
                    break
                cursor = page.next_cursor

            # BOTH versions of the shared (created_at, plan_id) are served, once
            # each, in plan_version DESC order — no gap, no duplicate.
            assert walked == [(plan_id, 2), (plan_id, 1)]
            assert len(walked) == len(set(walked)) == 2
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_list_filter_and_returned_state_are_one_snapshot_real_postgres():
    from repositories.control_plan_projection_repository import (
        PostgresControlPlanProjectionRepository,
    )
    from schemas.control_plan import ControlPlanListFilters
    from services.control_plan_lifecycle_service import (
        ControlPlanLifecycleService,
    )

    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        lifecycle = ControlPlanLifecycleService(repository=repository)
        projection = PostgresControlPlanProjectionRepository()
        try:
            async with sessions() as session:
                draft, _ = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
            plan_id = draft.plan_id

            # Filtering on the CURRENT state returns the row labelled with it.
            async with sessions() as session:
                page = await projection.list_plan_summaries(
                    session,
                    filters=ControlPlanListFilters(lifecycle_state="draft"),
                    cursor=None,
                    limit=25,
                )
            assert [i.plan_id for i in page.items] == [plan_id]
            assert page.items[0].lifecycle_state == "draft"

            # Commit a transition (draft -> under_review): the derived state moves.
            async with sessions() as session:
                await lifecycle.review_control_plan(
                    session, plan_id, 1, "reviewer"
                )

            # The filter and the returned lifecycle_state now come from ONE
            # statement/snapshot, so they can never disagree: filter=draft no
            # longer matches, and filter=under_review returns it as under_review.
            async with sessions() as session:
                stale = await projection.list_plan_summaries(
                    session,
                    filters=ControlPlanListFilters(lifecycle_state="draft"),
                    cursor=None,
                    limit=25,
                )
            assert stale.items == []
            async with sessions() as session:
                fresh = await projection.list_plan_summaries(
                    session,
                    filters=ControlPlanListFilters(
                        lifecycle_state="under_review"
                    ),
                    cursor=None,
                    limit=25,
                )
            assert [i.plan_id for i in fresh.items] == [plan_id]
            assert fresh.items[0].lifecycle_state == "under_review"
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_review_lifecycle_and_edge_graph_on_real_postgres():
    from services.control_plan_lifecycle_service import (
        ControlPlanLifecycleService,
        current_lifecycle_state,
    )

    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        assert await migrate.apply_migration(conn, MIGRATION_ID) == "applied"
        assert (
            await migrate.apply_migration(conn, LEDGER_MIGRATION_ID)
            == "applied"
        )
        assert (
            await migrate.apply_migration(conn, LIFECYCLE_MIGRATION_ID)
            == "applied"
        )

        # 0003 round-trip on an EMPTY transitions table (down restores the
        # narrow 0001 checks; only possible before any seq>1 row exists).
        assert (
            await migrate.rollback_migration(conn, LIFECYCLE_MIGRATION_ID)
            == "rolled-back"
        )
        assert (
            await migrate.apply_migration(conn, LIFECYCLE_MIGRATION_ID)
            == "applied"
        )

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        lifecycle = ControlPlanLifecycleService(repository=repository)
        try:
            async with sessions() as session:
                draft, _ = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
            async with sessions() as session:
                await lifecycle.review_control_plan(
                    session, draft.plan_id, 1, "reviewer"
                )
            async with sessions() as session:
                approved = await lifecycle.approve_shadow_plan(
                    session, draft.plan_id, 1, "approver"
                )
            assert current_lifecycle_state(approved) == "approved_for_shadow"
            async with sessions() as session:
                reloaded = await repository.load_draft_plan(
                    session, draft.plan_id, 1
                )
            assert current_lifecycle_state(reloaded) == "approved_for_shadow"

            # The DB edge-graph CHECK rejects an illegal transition directly.
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await conn.execute(
                    "INSERT INTO scheduler.control_state_transitions ("
                    "plan_id, plan_version, transition_sequence, "
                    "transition_type, from_state, to_state, actor_subject) "
                    "VALUES ($1, 1, 99, 'shadow_approved', 'draft', "
                    "'approved_for_shadow', 'x')",
                    draft.plan_id,
                )
            # COALESCE guard: NULL from_state on a non-creation type is rejected
            # (a naive tuple CHECK would pass on the resulting UNKNOWN).
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await conn.execute(
                    "INSERT INTO scheduler.control_state_transitions ("
                    "plan_id, plan_version, transition_sequence, "
                    "transition_type, from_state, to_state, actor_subject) "
                    "VALUES ($1, 1, 98, 'review_requested', NULL, "
                    "'under_review', 'x')",
                    draft.plan_id,
                )

            # Real-Postgres concurrency backstop: two actions that both compute
            # sequence 2 from the same fresh draft state — the (plan, version,
            # sequence) PK commits exactly one and rejects the other as a
            # TransitionConflictError (the real IntegrityError → typed mapping).
            from datetime import datetime, timezone

            from repositories.control_plan_repository import (
                TransitionConflictError,
                TransitionRecord,
            )

            async with sessions() as session:
                racer, _ = await _service_vol(repository, 6100.0).create_draft(
                    session, _request(), "operator-2"
                )
            now = datetime(2026, 7, 20, 2, tzinfo=timezone.utc)
            review = TransitionRecord(
                2, "review_requested", "draft", "under_review", "r", None,
                None, occurred_at=now,
            )
            cancel = TransitionRecord(
                2, "cancelled", "draft", "cancelled", "op", "abort", None,
                occurred_at=now,
            )
            async with sessions() as session:
                await repository.append_state_transition(
                    session, racer.plan_id, 1, review
                )
            async with sessions() as session:
                with pytest.raises(TransitionConflictError):
                    await repository.append_state_transition(
                        session, racer.plan_id, 1, cancel
                    )
            seq2_rows = await conn.fetchval(
                "SELECT count(*) FROM scheduler.control_state_transitions "
                "WHERE plan_id = $1 AND transition_sequence = 2",
                racer.plan_id,
            )
            assert seq2_rows == 1
        finally:
            await engine.dispose()
    finally:
        # Hard reset for the shared disposable container (lifecycle rows make
        # the 0003 down impossible, so drop the whole schema instead).
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()
