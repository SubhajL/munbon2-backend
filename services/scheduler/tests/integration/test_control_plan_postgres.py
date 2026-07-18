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
PROVENANCE_MIGRATION_ID = "0005_control_plan_provenance_v2"
PROVENANCE_V2_COLUMNS = (
    "provenance_version",
    "prediction_identity_version",
    "engine_id",
    "engine_semantic_contract_version",
    "engine_build_digest",
    "engine_descriptor_content_hash",
    "artifact_sha256",
    "artifact_uncompressed_size_bytes",
    "artifact_media_type",
    "artifact_encoding",
    "artifact_encoding_version",
    "coverage_summary_document_text",
    "coverage_summary_sha256",
    "predicted_delivery_ledger_sha256",
)
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
        # A fresh feasible draft is stored as v2, so the provenance columns must
        # exist before create_draft runs.
        assert (
            await migrate.apply_migration(conn, PROVENANCE_MIGRATION_ID)
            == "applied"
        )

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
                provenance_reference_document_for_record,
                provenance_reference_sha256,
                text_sha256,
            )

            divergent_optimizer = _json.loads(
                record.optimizer_result_document_text
            )
            divergent_optimizer["infeasible_reasons"] = ["divergent-solve"]
            divergent_optimizer_text = canonical_json_text(divergent_optimizer)
            # A v2 draft binds the provenance REFERENCE (not a response sha) into
            # its draft hash — reconstruct it the same way.
            divergent_draft_hash = control_plan_draft_hash(
                build_draft_hash_document(
                    record.canonical_input_document_text,
                    divergent_optimizer_text,
                    record.prediction_request_document_text,
                    provenance_reference_sha256(
                        provenance_reference_document_for_record(record)
                    ),
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
        # v2 rows now make the 0005 down refuse, so hard-reset the whole schema
        # for the shared disposable container.
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
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
            # created_at timestamps advance. Volumes stay inside the feasible band
            # (>=6200 is infeasible for this fixture) so every draft is feasible.
            created = []
            for volume in (6000.0, 6025.0, 6050.0, 6075.0, 6100.0):
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
        # v2 storage columns for the feasible draft this test approves.
        assert (
            await migrate.apply_migration(conn, PROVENANCE_MIGRATION_ID)
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


async def _column_exists(conn, column: str) -> bool:
    return (
        await conn.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'scheduler' "
            "AND table_name = 'control_plan_runs' AND column_name = $1",
            column,
        )
    ) == 1


def _hex64(seed: int) -> str:
    return (f"{seed:064x}")[:64]


@pytest.mark.asyncio
async def test_0005_apply_rollback_reapply_and_down_refuses_on_v2_rows():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        # apply-all reaches 0005; every provenance column exists.
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes[PROVENANCE_MIGRATION_ID] == "applied"
        for column in PROVENANCE_V2_COLUMNS:
            assert await _column_exists(conn, column)

        # On an empty-of-v2 table the down rolls back cleanly and reapplies.
        assert (
            await migrate.rollback_migration(conn, PROVENANCE_MIGRATION_ID)
            == "rolled-back"
        )
        for column in PROVENANCE_V2_COLUMNS:
            assert not await _column_exists(conn, column)
        assert (
            await migrate.apply_migration(conn, PROVENANCE_MIGRATION_ID)
            == "applied"
        )

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        try:
            # One real v2 draft: stored without the response and reloaded (its row
            # hashes re-verified) without any Flow network call.
            async with sessions() as session:
                record, _ = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
            assert record.provenance_version == 2
            assert record.prediction_response_document_text is None
            stored = await conn.fetchrow(
                "SELECT provenance_version, prediction_response_document_text, "
                "prediction_response_sha256, artifact_sha256, "
                "predicted_delivery_ledger_sha256 "
                "FROM scheduler.control_plan_runs WHERE plan_id = $1",
                record.plan_id,
            )
            assert stored["provenance_version"] == 2
            assert stored["prediction_response_document_text"] is None
            assert stored["prediction_response_sha256"] is None
            assert stored["artifact_sha256"] == record.artifact_sha256
            async with sessions() as session:
                loaded = await repository.load_draft_plan(
                    session, record.plan_id, 1
                )
            assert loaded.provenance_version == 2
            assert loaded.prediction_response_document_text is None
            assert loaded.artifact_sha256 == record.artifact_sha256

            # The 0005 down now REFUSES: a v2 row's provenance can't be restored.
            with pytest.raises(
                asyncpg.exceptions.RaiseError, match="v2 artifact-reference"
            ):
                await migrate.rollback_migration(conn, PROVENANCE_MIGRATION_ID)
            # The row and its columns survive the refused rollback.
            assert await _column_exists(conn, "provenance_version")
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_0005_v2_check_rejects_null_engine_or_artifact_or_ledger():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        try:
            async with sessions() as session:
                record, _ = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
        finally:
            await engine.dispose()

        template = dict(
            await conn.fetchrow(
                "SELECT * FROM scheduler.control_plan_runs WHERE plan_id = $1",
                record.plan_id,
            )
        )

        def _fresh(seed, **changes):
            row = dict(template)
            row["plan_id"] = UUID(int=seed)
            row["input_content_hash"] = _hex64(seed)
            row["draft_content_hash"] = _hex64(seed + 10_000)
            row.update(changes)
            return row

        async def _insert(row):
            columns = list(row)
            placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
            await conn.execute(
                "INSERT INTO scheduler.control_plan_runs "
                f"({', '.join(columns)}) VALUES ({placeholders})",
                *[row[c] for c in columns],
            )

        # A fresh, fully-populated v2 row inserts fine (the CHECK admits it).
        await _insert(_fresh(1))

        # Dropping any REQUIRED v2 column (engine / artifact / ledger) is rejected.
        for column in (
            "engine_build_digest",
            "engine_descriptor_content_hash",
            "artifact_sha256",
            "artifact_uncompressed_size_bytes",
            "coverage_summary_sha256",
            "predicted_delivery_ledger_sha256",
        ):
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await _insert(_fresh(1000 + hash(column) % 1000, **{column: None}))

        # A v2 row that keeps a response copy is rejected (must be NULL for v2).
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _insert(
                _fresh(
                    5,
                    prediction_response_document_text="{}",
                    prediction_response_sha256=_hex64(999),
                )
            )

        # A v2 row that pins prediction_identity_version != 2 is rejected: the
        # dedicated CHECK ties provenance_version = 2 to identity version = 2.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _insert(_fresh(6, prediction_identity_version=1))

        # A legacy v1 feasible row (no provenance, full response kept, sha matching
        # the response) still inserts fine under the v1 branch.
        from repositories.control_plan_repository import text_sha256

        v1_response = (
            '{"members":[{"member":"lower","status":"completed"},'
            '{"member":"nominal","status":"completed"},'
            '{"member":"upper","status":"completed"}]}'
        )
        v1_columns = {column: None for column in PROVENANCE_V2_COLUMNS}
        await _insert(
            _fresh(
                7,
                prediction_response_document_text=v1_response,
                prediction_response_sha256=text_sha256(v1_response),
                **v1_columns,
            )
        )
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_v2_content_sha_lists_and_filters_on_real_postgres():
    """FIX 4: a feasible+completed v2 plan (response sha NULL) lists with a content
    sha equal to its artifact_sha256 and is filterable by ?prediction_content_sha256
    — the COALESCE(prediction_response_sha256, artifact_sha256) projection."""
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
            assert record.provenance_version == 2
            assert record.prediction_response_sha256 is None
            assert record.artifact_sha256

            # Lists with a NON-null content sha == artifact_sha256.
            async with sessions() as session:
                page = await projection.list_plan_summaries(
                    session,
                    filters=ControlPlanListFilters(),
                    cursor=None,
                    limit=25,
                )
            assert [i.plan_id for i in page.items] == [record.plan_id]
            assert page.items[0].prediction_response_sha256 == (
                record.artifact_sha256
            )

            # Returned by a content-hash filter on the artifact sha ...
            async with sessions() as session:
                hit = await projection.list_plan_summaries(
                    session,
                    filters=ControlPlanListFilters(
                        prediction_content_sha256=record.artifact_sha256
                    ),
                    cursor=None,
                    limit=25,
                )
            assert [i.plan_id for i in hit.items] == [record.plan_id]

            # ... and excluded by a non-matching content hash.
            async with sessions() as session:
                miss = await projection.list_plan_summaries(
                    session,
                    filters=ControlPlanListFilters(
                        prediction_content_sha256="0" * 64
                    ),
                    cursor=None,
                    limit=25,
                )
            assert miss.items == []
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_v1_feasible_row_loads_verifies_and_approves_on_real_postgres():
    """FIX 5: a VALID v1 feasible row (real response text + matching sha, all v2
    columns NULL) round-trips through the real repository — stored, reloaded
    byte-identically, re-verified on load, and still certifiable for approval."""
    import json as _json
    from dataclasses import replace as dc_replace

    from core.control_plan import control_plan_draft_hash
    from core.control_plan_lifecycle import validate_shadow_approval_coverage
    from repositories.control_plan_repository import (
        build_draft_hash_document,
        text_sha256,
    )
    from tests.control_plan_test_support import FakeRepository

    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repository = PostgresControlPlanRepository()
        try:
            # Build a real v2 record IN MEMORY (nothing persisted) to reuse its
            # exact input/optimizer/prediction-request/requirements/events/ledger.
            v2, _ = await _service(FakeRepository()).create_draft(
                None, _request(), "operator-1"
            )
            assert v2.provenance_version == 2

            # The exact canonical response the fake served; its sha IS the artifact
            # sha, i.e. precisely what a v1 draft of this plan binds. Independently
            # recomputed here (not read back from the discarded v2 response).
            fake = FakeControlFlowClient(snapshot_mirror())
            served = await fake.create_prediction(
                _json.loads(v2.prediction_request_document_text)
            )
            response_text = served.response_text
            response_sha = text_sha256(response_text)
            assert response_sha == v2.artifact_sha256  # oracle

            v1 = dc_replace(
                v2,
                plan_id=UUID("00000000-0000-4000-8000-0000000000a1"),
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

            async with sessions() as session:
                _, replayed = await repository.store_draft_plan(session, v1)
            assert not replayed

            # Reload: full response byte-identical + every content hash re-verified
            # on load (the v1 path), with NO Flow network call.
            async with sessions() as session:
                loaded = await repository.load_draft_plan(session, v1.plan_id, 1)
            assert loaded is not None
            assert loaded.provenance_version is None
            assert loaded.prediction_response_document_text == response_text
            assert loaded.prediction_response_sha256 == response_sha
            assert loaded.draft_content_hash == v1.draft_content_hash
            assert loaded.ledger_entries == v2.ledger_entries
            assert all(
                column is None
                for column in (
                    loaded.engine_id,
                    loaded.artifact_sha256,
                    loaded.coverage_summary_sha256,
                    loaded.predicted_delivery_ledger_sha256,
                )
            )

            # Approval coverage still certifies the v1 record from its response.
            validate_shadow_approval_coverage(loaded)
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_bounded_multi_statement_reads_are_single_snapshot_real_postgres():
    """FIX 3: the multi-statement history/ledger reads take a REPEATABLE READ
    snapshot before their first statement, so a child row COMMITTED between two of
    their statements can never mix generations. Proven two ways: (1) the production
    read leaves its transaction at REPEATABLE READ (a READ COMMITTED default would
    fail this); (2) a hand-rolled interleave over the same statement sequence hides
    a committed append under REPEATABLE READ while a READ COMMITTED reader mixes it
    in."""
    from sqlalchemy import text as sa_text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from models.control_plan import ControlStateTransition
    from repositories.control_plan_projection_repository import (
        PostgresControlPlanProjectionRepository,
        history_header_query,
        history_transitions_query,
    )

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
                draft, _ = await _service(repository).create_draft(
                    session, _request(), "operator-1"
                )
            plan_id = draft.plan_id

            # (1) The production read runs under REPEATABLE READ (ties the fix to
            # production; a READ COMMITTED default would fail this assertion).
            async with sessions() as sa:
                history = await projection.load_lifecycle_history(sa, plan_id, 1)
                assert history is not None
                level = (
                    await sa.execute(sa_text("SHOW transaction_isolation"))
                ).scalar()
                assert level == "repeatable read"

            # (2) Interleave a COMMITTED append between the two history statements.
            # Under REPEATABLE READ the snapshot is fixed at reader A's first
            # statement, so B's committed seq-2 append is invisible to A's second.
            def _append_seq2(sb):
                return sb.execute(
                    pg_insert(ControlStateTransition).values(
                        plan_id=plan_id,
                        plan_version=1,
                        transition_sequence=2,
                        transition_type="review_requested",
                        from_state="draft",
                        to_state="under_review",
                        actor_subject="reviewer",
                    )
                )

            async with sessions() as sa, sessions() as sc:
                await sa.connection(
                    execution_options={"isolation_level": "REPEATABLE READ"}
                )
                # Both readers take their FIRST statement before B commits.
                (await sa.execute(history_header_query(plan_id, 1))).one()
                (await sc.execute(history_header_query(plan_id, 1))).one()
                async with sessions() as sb:
                    await _append_seq2(sb)
                    await sb.commit()
                # Both readers take their SECOND statement after B commits.
                snap_a = (
                    await sa.execute(history_transitions_query(plan_id, 1))
                ).all()
                snap_c = (
                    await sc.execute(history_transitions_query(plan_id, 1))
                ).all()

            # A (REPEATABLE READ) is one generation: only draft_created.
            assert [t.transition_type for t in snap_a] == ["draft_created"]
            # C (READ COMMITTED) mixes generations: header from before, transitions
            # from after — exactly the drift FIX 3 removes from the production read.
            assert [t.transition_type for t in snap_c] == [
                "draft_created",
                "review_requested",
            ]
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_projections_over_real_postgres_match_detail():
    """PR 4.4b-3: the three BOUNDED per-plan reads, run against a real stored v2
    draft, return EXACTLY the projections built from the full ``_assemble`` detail —
    proving the bounded queries load the same values without loading the aggregate."""
    from api.v1.endpoints.control_plans import _response_from_record
    from repositories.control_plan_projection_repository import (
        PostgresControlPlanProjectionRepository,
        build_ledger_projection,
        build_lifecycle_history,
        build_prediction_coverage,
    )

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

            async with sessions() as session:
                full = await repository.load_draft_plan(
                    session, record.plan_id, 1
                )
            assert full is not None
            assert full.provenance_version == 2
            assert full.ledger_entries  # a real feasible draft has ledger rows

            async with sessions() as session:
                coverage = await projection.load_prediction_coverage(
                    session, record.plan_id, 1
                )
                history = await projection.load_lifecycle_history(
                    session, record.plan_id, 1
                )
                ledger = await projection.load_ledger_projection(
                    session, record.plan_id, 1
                )

            # EQUIVALENCE: each bounded read == projecting from the full aggregate.
            assert coverage == build_prediction_coverage(full)
            assert history == build_lifecycle_history(full, full.transitions)
            assert ledger == build_ledger_projection(
                full, full.ledger_entries, full.events, full.requirements
            )
            # ... and the coverage/history subsets equal the full DETAIL response.
            detail = _response_from_record(full)
            assert (
                coverage.prediction_member_statuses
                == detail.prediction_member_statuses
            )
            assert history.transitions == detail.transitions
            assert history.lifecycle_state == detail.lifecycle_state
            assert ledger.ledger_sha256 and ledger.handover

            # An absent plan is None (the route maps that to a 404).
            async with sessions() as session:
                missing = await projection.load_ledger_projection(
                    session,
                    UUID("00000000-0000-4000-8000-0000000000ff"),
                    1,
                )
            assert missing is None
        finally:
            await engine.dispose()
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()
