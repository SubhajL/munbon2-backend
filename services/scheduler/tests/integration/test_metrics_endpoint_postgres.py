"""Integration: the DB-derived /metrics collector over a disposable loopback Postgres (PR 6.4).

Seeds the durable tables directly, then renders metrics through the real async engine and
asserts the exact series values. Set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback PG.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

import migrations.migrate as migrate
from api.metrics import render_metrics
from tests.integration.test_control_plan_postgres import _sqlalchemy_url
from tests.integration.test_open_loop_worker_postgres import (
    _connect,
    _insert_mutex,
    _insert_outbox_intent,
)
from tests.integration.test_scheduler_postgres import _test_url_loopback

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None, reason="SCHEDULER_TEST_POSTGRES_URL not set"
)

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)


class _FakeRedis:
    def __init__(self, heartbeat=None):
        self._heartbeat = heartbeat

    async def get(self, key):
        return self._heartbeat


async def _insert_run(conn, plan_id, version, *, optimizer_status, prediction_status):
    # The 0005 feasible-prediction-branch CHECK requires a feasible run to carry the full v1
    # prediction artifact (run id, summaries, request/response docs, sha); an infeasible run
    # leaves them NULL (the existing seeder form).
    feasible = optimizer_status == "feasible"
    pred_run_id = "4" * 64 if feasible else None
    pred_summaries = "[]" if feasible else None
    pred_request = "{}" if feasible else None
    pred_response = "{}" if feasible else None
    pred_sha = "5" * 64 if feasible else None
    await conn.execute(
        """
        INSERT INTO scheduler.control_plan_runs (
            plan_id, plan_version, input_content_hash, draft_content_hash,
            optimizer_status, prediction_status, requirement_run_id,
            requirement_version, model_snapshot_id, model_release_id,
            model_release_content_hash, horizon_start, horizon_end,
            model_step_seconds, max_intermediate_trims,
            canonical_input_document_text, model_snapshot_document_text,
            optimizer_result_document_text, optimizer_result_sha256, created_by_subject,
            prediction_run_id, prediction_member_summaries, prediction_request_document_text,
            prediction_response_document_text, prediction_response_sha256
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, 1, $8, 'release-v1',
            $8, now(), now() + interval '6 days', 3600, 1, '{}', '{}', '{}', $8, 'op',
            $9, $10, $11, $12, $13
        )
        """,
        plan_id,
        version,
        hashlib.sha256(f"in:{plan_id}".encode()).hexdigest(),
        hashlib.sha256(f"draft:{plan_id}".encode()).hexdigest(),
        optimizer_status,
        prediction_status,
        uuid4(),
        "3" * 64,
        pred_run_id,
        pred_summaries,
        pred_request,
        pred_response,
        pred_sha,
    )


async def _insert_receipt(conn, plan_id, version, *, status, reason_code):
    intent_id = uuid4()
    await conn.execute(
        """
        INSERT INTO scheduler.control_command_validation_receipts (
            intent_id, plan_id, plan_version, receipt_id, correlation_id, request_id,
            idempotency_key, intent_content_hash, capability_hash, status, reason_code,
            validated_at, receipt_document_text, receipt_content_sha256, dispatched_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, now(), '{}', $12, now())
        """,
        intent_id, plan_id, version, uuid4(), uuid4(), f"req.{intent_id}",
        f"idem.{intent_id}", "a" * 64, "b" * 64, status, reason_code, "c" * 64,
    )


async def _insert_observation(conn, plan_id, version, *, gate, verdict):
    await conn.execute(
        """
        INSERT INTO scheduler.control_gate_readback_observations (
            observation_id, plan_id, plan_version, canonical_gate_id, observed_level,
            expected_level, quality, verdict, reconciliation_mode, observed_at
        ) VALUES ($1, $2, $3, $4, 2, 3, 'ok', $5, 'observe', now())
        """,
        uuid4(), plan_id, version, gate, verdict,
    )


async def _insert_claimed_event(conn, plan_id, version, intent_id, occurred_at):
    await conn.execute(
        "INSERT INTO scheduler.control_command_execution_events "
        "(event_id, plan_id, plan_version, intent_id, event_type, occurred_at) "
        "VALUES ($1, $2, $3, $4, 'claimed', $5)",
        uuid4(), plan_id, version, intent_id, occurred_at,
    )


def _series(body: str, name: str) -> float | None:
    for line in body.splitlines():
        if line.startswith(name + " "):
            return float(line[len(name) + 1 :])
    return None


@pytest.mark.asyncio
async def test_metrics_endpoint_reports_db_derived_counts():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        feasible_plan, infeasible_plan = uuid4(), uuid4()
        await _insert_run(
            conn, feasible_plan, 1, optimizer_status="feasible", prediction_status="completed"
        )
        await _insert_run(
            conn,
            infeasible_plan,
            1,
            optimizer_status="infeasible",
            prediction_status="not_requested",
        )
        await _insert_receipt(conn, feasible_plan, 1, status="validation_accepted", reason_code=None)
        await _insert_receipt(
            conn, feasible_plan, 1, status="validation_rejected", reason_code="freshness_failed"
        )
        await _insert_observation(conn, feasible_plan, 1, gate="G1", verdict="mismatch")
        # A claimed-but-unreceipted intent on a plan that STILL HOLDS AUTHORITY (mutex present),
        # claimed 60s before the scrape → pending=1, lag=60.
        await _insert_mutex(conn, feasible_plan, 1, section="sec-a", gate="Ga")
        pending_intent = await _insert_outbox_intent(
            conn, feasible_plan, 1, event_sequence=1, not_before=NOW, deadline=NOW + timedelta(days=1)
        )
        await _insert_claimed_event(
            conn, feasible_plan, 1, pending_intent, NOW - timedelta(seconds=60)
        )
    finally:
        await conn.close()

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_sqlalchemy_url())
    try:
        body = (
            await render_metrics(engine, _FakeRedis(heartbeat=NOW.isoformat()), now=NOW)
        ).decode()
    finally:
        await engine.dispose()

    assert _series(body, 'control_plan_runs_total{status="feasible"}') == 1.0
    assert _series(body, 'control_plan_runs_total{status="infeasible"}') == 1.0
    assert _series(body, 'control_prediction_runs_total{status="completed"}') == 1.0
    assert _series(body, 'control_prediction_runs_total{status="not_requested"}') == 1.0
    assert _series(body, 'control_intent_validations_total{status="validation_accepted"}') == 1.0
    assert _series(body, 'control_intent_validations_total{status="validation_rejected"}') == 1.0
    assert _series(body, 'command_intent_rejections_total{reason="freshness_failed"}') == 1.0
    # a reason that never occurred is still present at 0 (cardinality guarantee).
    assert _series(body, 'command_intent_rejections_total{reason="target_invalid"}') == 0.0
    assert _series(body, 'gate_readback_mismatch_total{gate="G1"}') == 1.0
    assert _series(body, "command_intent_dispatch_pending") == 1.0
    assert _series(body, "command_intent_lag_seconds") == 60.0
    assert (
        _series(body, 'scheduler_dispatch_worker_heartbeat_present{worker="shadow_dispatch"}')
        == 1.0
    )
    assert _series(body, "scheduler_metrics_scrape_error") == 0.0


@pytest.mark.asyncio
async def test_pending_excludes_receipted_and_authority_released_intents():
    """The pending/lag set = claimed ∧ ¬receipted ∧ plan-still-holds-authority. A receipted
    intent drops out (the dispatcher owes it nothing); a claimed intent on a plan that no longer
    holds authority (superseded/invalidated) drops out too — so one orphan can't pin lag forever.
    """
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)

        # Plan A: active (mutex) + claimed intent WITH a receipt → excluded (nothing owed).
        plan_a = uuid4()
        await _insert_run(conn, plan_a, 1, optimizer_status="feasible", prediction_status="completed")
        await _insert_mutex(conn, plan_a, 1, section="sec-a", gate="Ga")
        intent_a = await _insert_outbox_intent(
            conn, plan_a, 1, event_sequence=1, not_before=NOW, deadline=NOW + timedelta(days=1)
        )
        await _insert_claimed_event(conn, plan_a, 1, intent_a, NOW - timedelta(seconds=300))
        # a receipt for intent_a → it is no longer pending
        await conn.execute(
            """
            INSERT INTO scheduler.control_command_validation_receipts (
                intent_id, plan_id, plan_version, receipt_id, correlation_id, request_id,
                idempotency_key, intent_content_hash, capability_hash, status, reason_code,
                validated_at, receipt_document_text, receipt_content_sha256, dispatched_at
            ) VALUES ($1, $2, 1, $3, $4, $5, $6, $7, $8, 'validation_accepted', NULL,
                      now(), '{}', $9, now())
            """,
            intent_a, plan_a, uuid4(), uuid4(), f"req.{intent_a}", f"idem.{intent_a}",
            "a" * 64, "b" * 64, "c" * 64,
        )

        # Plan B: active (mutex) + claimed intent, NO receipt → PENDING (the only one counted).
        plan_b = uuid4()
        await _insert_run(conn, plan_b, 1, optimizer_status="infeasible", prediction_status="not_requested")
        await _insert_mutex(conn, plan_b, 1, section="sec-b", gate="Gb")
        intent_b = await _insert_outbox_intent(
            conn, plan_b, 1, event_sequence=1, not_before=NOW, deadline=NOW + timedelta(days=1)
        )
        await _insert_claimed_event(conn, plan_b, 1, intent_b, NOW - timedelta(seconds=30))

        # Plan C: claimed intent but NO mutex (authority released — terminal/orphaned) → excluded
        # even though it is claimed-and-unreceipted and OLD.
        plan_c = uuid4()
        await _insert_run(conn, plan_c, 1, optimizer_status="infeasible", prediction_status="not_requested")
        intent_c = await _insert_outbox_intent(
            conn, plan_c, 1, event_sequence=1, not_before=NOW, deadline=NOW + timedelta(days=1)
        )
        await _insert_claimed_event(conn, plan_c, 1, intent_c, NOW - timedelta(days=90))
    finally:
        await conn.close()

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_sqlalchemy_url())
    try:
        body = (await render_metrics(engine, _FakeRedis(), now=NOW)).decode()
    finally:
        await engine.dispose()

    # Only plan B's intent counts: pending=1, lag=30 (NOT the 90-day orphan, NOT the receipted).
    assert _series(body, "command_intent_dispatch_pending") == 1.0
    assert _series(body, "command_intent_lag_seconds") == 30.0


@pytest.mark.asyncio
async def test_metrics_scrape_survives_db_error():
    """A DB failure yields scheduler_metrics_scrape_error=1 at HTTP 200, never a 500."""

    class _BrokenEngine:
        def begin(self):
            raise RuntimeError("connection reset")

    body = (await render_metrics(_BrokenEngine(), _FakeRedis(), now=NOW)).decode()
    assert _series(body, "scheduler_metrics_scrape_error") == 1.0
