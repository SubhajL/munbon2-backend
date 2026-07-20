"""Integration: PR 6.5a bounded machine-boundary read projections over a disposable PG.

Seeds the durable tables directly, then loads each projection through the real repository
and asserts the folded shape. Set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback PG.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

import migrations.migrate as migrate
from repositories.control_plan_projection_repository import (
    PostgresControlPlanProjectionRepository,
)
from tests.integration.test_control_plan_postgres import _sqlalchemy_url
from tests.integration.test_open_loop_worker_postgres import (
    _connect,
    _insert_outbox_intent,
)
from tests.integration.test_scheduler_postgres import _test_url_loopback

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None, reason="SCHEDULER_TEST_POSTGRES_URL not set"
)

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)


async def _insert_run(conn, plan_id, version):
    await conn.execute(
        """
        INSERT INTO scheduler.control_plan_runs (
            plan_id, plan_version, input_content_hash, draft_content_hash,
            optimizer_status, prediction_status, requirement_run_id, requirement_version,
            model_snapshot_id, model_release_id, model_release_content_hash, horizon_start,
            horizon_end, model_step_seconds, max_intermediate_trims, canonical_input_document_text,
            model_snapshot_document_text, optimizer_result_document_text, optimizer_result_sha256,
            created_by_subject
        ) VALUES ($1, $2, $3, $4, 'infeasible', 'not_requested', $5, 1, $6, 'release-v1', $6,
                  now(), now() + interval '6 days', 3600, 1, '{}', '{}', '{}', $6, 'op')
        """,
        plan_id, version, "1" * 64, "2" * 64, uuid4(), "3" * 64,
    )


async def _insert_event(conn, plan_id, version, event_type, *, intent_id, worker_id=None, occurred_at=NOW):
    await conn.execute(
        "INSERT INTO scheduler.control_command_execution_events "
        "(event_id, plan_id, plan_version, intent_id, event_type, worker_id, occurred_at) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7)",
        uuid4(), plan_id, version, intent_id, event_type, worker_id, occurred_at,
    )


async def _insert_receipt(conn, plan_id, version, intent_id, *, status, reason_code):
    await conn.execute(
        """
        INSERT INTO scheduler.control_command_validation_receipts (
            intent_id, plan_id, plan_version, receipt_id, correlation_id, request_id,
            idempotency_key, intent_content_hash, capability_hash, status, reason_code,
            validated_at, receipt_document_text, receipt_content_sha256, dispatched_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, '{}', $13, $12)
        """,
        intent_id, plan_id, version, uuid4(), uuid4(), f"req.{intent_id}",
        f"idem.{intent_id}", "a" * 64, "b" * 64, status, reason_code, NOW, "c" * 64,
    )


async def _insert_observation(conn, plan_id, version, *, gate, verdict, mode="observe"):
    await conn.execute(
        """
        INSERT INTO scheduler.control_gate_readback_observations (
            observation_id, plan_id, plan_version, canonical_gate_id, observed_level,
            expected_level, quality, verdict, reconciliation_mode, observed_at
        ) VALUES ($1, $2, $3, $4, 2, 3, 'ok', $5, $6, $7)
        """,
        uuid4(), plan_id, version, gate, verdict, mode, NOW,
    )


def _sessions():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(_sqlalchemy_url())
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_machine_boundary_reads_over_real_postgres():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)
        # intent 1: claimed + an accepted receipt; intent 2: pending (no event/receipt).
        intent1 = await _insert_outbox_intent(
            conn, plan_id, version, event_sequence=1, not_before=NOW, deadline=NOW + timedelta(days=1)
        )
        intent2 = await _insert_outbox_intent(
            conn, plan_id, version, event_sequence=2, not_before=NOW, deadline=NOW + timedelta(days=1)
        )
        await _insert_event(conn, plan_id, version, "claimed", intent_id=intent1, occurred_at=NOW)
        await _insert_receipt(
            conn, plan_id, version, intent1, status="validation_accepted", reason_code=None
        )
        # a plan-level hold, then a resume LATER → not currently held.
        await _insert_event(conn, plan_id, version, "held", intent_id=None, worker_id="readback-reconciler", occurred_at=NOW)
        await _insert_event(
            conn, plan_id, version, "resumed", intent_id=None, worker_id="op", occurred_at=NOW + timedelta(minutes=5)
        )
        await _insert_observation(conn, plan_id, version, gate="M(0,0;1,0)", verdict="mismatch", mode="enforce")
    finally:
        await conn.close()

    engine, sessions = _sessions()
    repo = PostgresControlPlanProjectionRepository()
    try:
        async with sessions() as session:
            timeline = await repo.load_intent_timeline_projection(session, plan_id, version)
            observations = await repo.load_readback_observations_projection(session, plan_id, version)
            state = await repo.load_execution_state_projection(session, plan_id, version)
            missing = await repo.load_intent_timeline_projection(session, uuid4(), 1)
    finally:
        await engine.dispose()

    # timeline: ordered by event_sequence; intent1 claimed+accepted, intent2 pending.
    assert [e.intent_id for e in timeline.intents] == [intent1, intent2]
    assert timeline.intents[0].execution_state == "claimed"
    assert timeline.intents[0].receipt_status == "validation_accepted"
    assert timeline.intents[0].claimed_at == NOW
    assert timeline.intents[1].execution_state == "pending"
    assert timeline.intents[1].receipt_status is None

    # observations
    assert len(observations.observations) == 1
    assert observations.observations[0].verdict == "mismatch"
    assert observations.observations[0].reconciliation_mode == "enforce"

    # execution state: held then resumed later → not held, both events present in order.
    assert state.is_held is False
    assert [e.event_type for e in state.hold_events] == ["held", "resumed"]

    # an unknown plan → None (the endpoint maps this to 404).
    assert missing is None
