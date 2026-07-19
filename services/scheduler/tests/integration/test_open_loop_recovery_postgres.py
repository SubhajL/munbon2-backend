"""PR 5.2a restart-safe authority recovery on real Postgres (env-gated).

Set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback Postgres. Proves the
things a unit test cannot: that ``recover_execution_state`` rebuilds the MUTABLE
``control_active_gate_authority`` cache purely from the append-only
``control_state_transitions`` history (the "no volatile authority" invariant),
drops crash-orphaned rows whose holder is terminal, and is an idempotent no-op when
the cache already matches — all through the ACTUAL repository + advisory-lock path.
"""

import hashlib
from uuid import uuid4

import asyncpg
import pytest

import migrations.migrate as migrate
from tests.integration.test_scheduler_postgres import _test_url_loopback

MUTEX = "scheduler.control_active_gate_authority"

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None,
    reason="SCHEDULER_TEST_POSTGRES_URL not set",
)


async def _connect():
    return await asyncpg.connect(
        **migrate.postgres_connection_kwargs(_test_url_loopback())
    )


async def _insert_run(conn, plan_id, version):
    await conn.execute(
        """
        INSERT INTO scheduler.control_plan_runs (
            plan_id, plan_version, input_content_hash, draft_content_hash,
            optimizer_status, prediction_status, requirement_run_id,
            requirement_version, model_snapshot_id, model_release_id,
            model_release_content_hash, horizon_start, horizon_end,
            model_step_seconds, max_intermediate_trims,
            canonical_input_document_text, model_snapshot_document_text,
            optimizer_result_document_text, optimizer_result_sha256,
            created_by_subject
        ) VALUES (
            $1, $2, $3, $4, 'infeasible', 'not_requested', $5, 1, $6, 'release-v1',
            $6, now(), now() + interval '6 days', 3600, 1, '{}', '{}', '{}', $6,
            'op'
        )
        """,
        plan_id, version,
        hashlib.sha256(f"in:{plan_id}".encode()).hexdigest(),
        hashlib.sha256(f"draft:{plan_id}".encode()).hexdigest(),
        uuid4(), "3" * 64,
    )


async def _insert_scheduled_requirement(conn, plan_id, version, section_id, gate_id):
    # A `scheduled` requirement must populate every delivery column (0001 CHECK
    # control_plan_requirements_scheduled_fields) and satisfy the fraction ordering.
    await conn.execute(
        """
        INSERT INTO scheduler.control_plan_requirements (
            plan_id, plan_version, requirement_id, run_id, source_version,
            service_date, section_id, zone, required_volume_m3, window_start,
            window_end, quality, published_at, as_of_date, source_data_status,
            planning_disposition, delivery_node_id, gate_id, maximum_delivery_m3s,
            approved_excess_m3, travel_delay_seconds, minimum_delivery_fraction,
            maximum_delivery_fraction, path_reach_ids_document_text,
            rotation_windows_document_text, requirement_document_text
        ) VALUES (
            $1, $2, $3, $4, 1, current_date, $5, 6, 1000.0, now(),
            now() + interval '1 day', 'estimated', now(), current_date, 'published',
            'scheduled', $6, $7, 1.0, 0.0, 3600, 0.5, 1.0, '["R1"]', '[]', '{}'
        )
        """,
        plan_id, version, uuid4(), uuid4(), section_id, f"node-{gate_id}", gate_id,
    )


# (transition_type, from_state, to_state) for a full happy-path chain to active,
# then the emergency-invalidate exit for the terminal case.
_TO_ACTIVE = [
    ("draft_created", None, "draft"),
    ("review_requested", "draft", "under_review"),
    ("shadow_approved", "under_review", "approved_for_shadow"),
    ("shadow_activated", "approved_for_shadow", "shadow_active"),
]
_INVALIDATE = ("invalidated", "shadow_active", "invalidated")


async def _insert_chain(conn, plan_id, version, edges):
    for sequence, (ttype, frm, to) in enumerate(edges, start=1):
        await conn.execute(
            """
            INSERT INTO scheduler.control_state_transitions (
                plan_id, plan_version, transition_sequence, transition_type,
                from_state, to_state, actor_subject
            ) VALUES ($1, $2, $3, $4, $5, $6, 'op')
            """,
            plan_id, version, sequence, ttype, frm, to,
        )


async def _insert_mutex_row(conn, section_id, gate_id, plan_id, version, seq):
    await conn.execute(
        "INSERT INTO scheduler.control_active_gate_authority (section_id, gate_id, "
        "plan_id, plan_version, activation_transition_sequence) "
        "VALUES ($1, $2, $3, $4, $5)",
        section_id, gate_id, plan_id, version, seq,
    )


async def _mutex_rows(conn):
    rows = await conn.fetch(
        "SELECT section_id, gate_id, plan_id, plan_version, "
        "activation_transition_sequence FROM scheduler.control_active_gate_authority "
        "ORDER BY section_id, gate_id"
    )
    return [dict(r) for r in rows]


async def _recover(sessions):
    from repositories.control_plan_repository import PostgresControlPlanRepository
    from services.open_loop_execution_service import OpenLoopExecutionService

    async with sessions() as session:
        return await OpenLoopExecutionService(
            PostgresControlPlanRepository()
        ).recover_execution_state(session)


def _sessions():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.integration.test_control_plan_postgres import _sqlalchemy_url

    engine = create_async_engine(_sqlalchemy_url())
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_restart_reconstructs_state_from_transitions():
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)
        await _insert_scheduled_requirement(conn, plan_id, version, "sec-1", "G1")
        await _insert_scheduled_requirement(conn, plan_id, version, "sec-2", "G2")
        await _insert_chain(conn, plan_id, version, _TO_ACTIVE)
        # Simulate the volatile cache lost on restart: no mutex rows exist yet.
        assert await _mutex_rows(conn) == []

        engine, sessions = _sessions()
        report = await _recover(sessions)

        assert (report.inserted, report.deleted) == (2, 0)
        rows = await _mutex_rows(conn)
        assert [(r["section_id"], r["gate_id"]) for r in rows] == [
            ("sec-1", "G1"), ("sec-2", "G2")
        ]
        # Every rebuilt row is pinned to the plan and its activation transition (seq 4).
        for row in rows:
            assert row["plan_id"] == plan_id
            assert row["plan_version"] == version
            assert row["activation_transition_sequence"] == 4
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_recovery_removes_orphan_authority_for_terminal_plan():
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)
        await _insert_scheduled_requirement(conn, plan_id, version, "sec-1", "G1")
        # The plan activated then was invalidated (terminal) — but a crash left its
        # mutex row behind (the release normally happens atomically with the exit).
        await _insert_chain(conn, plan_id, version, _TO_ACTIVE + [_INVALIDATE])
        await _insert_mutex_row(conn, "sec-1", "G1", plan_id, version, 4)

        engine, sessions = _sessions()
        report = await _recover(sessions)

        assert (report.inserted, report.deleted) == (0, 1)
        assert await _mutex_rows(conn) == []
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_recovery_is_idempotent_noop_when_consistent():
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)
        await _insert_scheduled_requirement(conn, plan_id, version, "sec-1", "G1")
        await _insert_scheduled_requirement(conn, plan_id, version, "sec-2", "G2")
        await _insert_chain(conn, plan_id, version, _TO_ACTIVE)

        engine, sessions = _sessions()
        first = await _recover(sessions)
        assert (first.inserted, first.deleted) == (2, 0)
        before = await _mutex_rows(conn)

        # A second recovery must change nothing — and must NOT delete the fresh,
        # still-active plan's rows (holder is shadow_active, not terminal).
        second = await _recover(sessions)
        assert (second.inserted, second.deleted) == (0, 0)
        assert await _mutex_rows(conn) == before
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_terminal_orphan_scope_transfers_to_active_plan_in_one_pass():
    # A terminal plan A holds (sec-1,G1) as a crash-orphan while active plan B owns
    # the same scope in the truth. ONE recovery pass must delete A's orphan AND
    # insert B's row — never leave the scope with no authority row (the M2 defect).
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_a, plan_b = uuid4(), uuid4()
        await _insert_run(conn, plan_a, 1)
        await _insert_scheduled_requirement(conn, plan_a, 1, "sec-1", "G1")
        await _insert_chain(conn, plan_a, 1, _TO_ACTIVE + [_INVALIDATE])  # terminal
        await _insert_mutex_row(conn, "sec-1", "G1", plan_a, 1, 4)        # orphan
        await _insert_run(conn, plan_b, 1)
        await _insert_scheduled_requirement(conn, plan_b, 1, "sec-1", "G1")
        await _insert_chain(conn, plan_b, 1, _TO_ACTIVE)                  # active

        engine, sessions = _sessions()
        report = await _recover(sessions)

        assert (report.inserted, report.deleted) == (1, 1)
        rows = await _mutex_rows(conn)
        assert [
            (r["section_id"], r["gate_id"], r["plan_id"]) for r in rows
        ] == [("sec-1", "G1", plan_b)]
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_recovery_does_not_resurrect_scope_for_released_terminal_plan():
    # A plan that activated then was invalidated — its mutex row was already released
    # atomically (normal path), so no row exists. Recovery must NOT re-insert its
    # scope (the H1 resurrection symptom): a terminal plan holds no authority.
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)
        await _insert_scheduled_requirement(conn, plan_id, version, "sec-1", "G1")
        await _insert_chain(conn, plan_id, version, _TO_ACTIVE + [_INVALIDATE])
        assert await _mutex_rows(conn) == []

        engine, sessions = _sessions()
        report = await _recover(sessions)

        assert (report.inserted, report.deleted) == (0, 0)
        assert await _mutex_rows(conn) == []
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()
