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
TABLES = (
    "scheduler.control_plan_runs",
    "scheduler.control_plan_requirements",
    "scheduler.gate_plan_events",
    "scheduler.control_state_transitions",
)

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


@pytest.mark.asyncio
async def test_control_plan_migration_and_repository_on_real_postgres():
    conn = await _connect()
    try:
        await _require_disposable(conn)

        # Apply -> all objects exist; reapply is a no-op.
        assert await migrate.apply_migration(conn, MIGRATION_ID) == "applied"
        for table in TABLES:
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
        for table in TABLES:
            assert await _regclass(conn, table) is None
        assert await migrate.apply_migration(conn, MIGRATION_ID) == "applied"

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
        # Leave the disposable database empty for the next run.
        try:
            await migrate.rollback_migration(conn, MIGRATION_ID)
        finally:
            await conn.close()
