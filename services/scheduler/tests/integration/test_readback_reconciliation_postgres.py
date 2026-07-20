"""PR 6.3b readback reconciliation on real Postgres (env-gated).

Verifies migration 0011 applies + is append-only, and that a full enforce-mode reconcile of an
injected drifting readback records an observation (0011) AND holds the plan via a real 5.2
plan-level `held` event (0009).
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest

import migrations.migrate as migrate
from tests.integration.test_open_loop_worker_postgres import (
    _connect,
    _seed_active_plan,
    _sessions,
)
from tests.integration.test_scheduler_postgres import _test_url_loopback

OBS = "scheduler.control_gate_readback_observations"
EVENTS = "scheduler.control_command_execution_events"
NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None,
    reason="SCHEDULER_TEST_POSTGRES_URL not set",
)


@pytest.mark.asyncio
async def test_migration_0011_applies_and_is_append_only():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes["0011_gate_readback_observations"] == "applied"
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW - timedelta(hours=1), deadline=NOW + timedelta(hours=5)
        )
        await conn.execute(
            f"""INSERT INTO {OBS} (observation_id, plan_id, plan_version, canonical_gate_id,
                observed_level, expected_level, quality, verdict, reconciliation_mode, observed_at)
                VALUES ($1,$2,$3,'G1',4,2,'ok','mismatch','enforce',now())""",
            uuid4(), plan_id, version,
        )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(f"UPDATE {OBS} SET verdict='ok' WHERE plan_id=$1", plan_id)
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(f"DELETE FROM {OBS} WHERE plan_id=$1", plan_id)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_enforce_reconcile_records_observation_and_holds_the_plan():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW - timedelta(hours=1), deadline=NOW + timedelta(hours=5)
        )
    finally:
        await conn.close()

    engine, sessions = _sessions()
    try:
        from repositories.control_plan_repository import PostgresControlPlanRepository
        from services.open_loop_execution_service import OpenLoopExecutionService
        from services.readback_reconciliation_service import ReadbackReconciliationService

        repo = PostgresControlPlanRepository()
        open_loop = OpenLoopExecutionService(repo, clock=lambda: NOW, execution_mode="shadow")
        service = ReadbackReconciliationService(
            repo, open_loop, mode="enforce", clock=lambda: NOW
        )
        async with sessions() as session:
            report = await service.reconcile_plan_readback(
                session, plan_id, version,
                readings={"G1": {"observed_level": 4, "quality": "ok"}},
                expected_levels={"G1": 2},
                now=NOW,
            )
        assert report.held is True
        assert "G1" in report.mismatched_gate_ids
    finally:
        await engine.dispose()

    conn = await _connect()
    try:
        obs = await conn.fetchval(
            f"SELECT count(*) FROM {OBS} WHERE plan_id=$1 AND verdict='mismatch'", plan_id
        )
        assert obs == 1
        held = await conn.fetchval(
            f"SELECT count(*) FROM {EVENTS} WHERE plan_id=$1 AND event_type='held'", plan_id
        )
        assert held == 1
    finally:
        await conn.close()
