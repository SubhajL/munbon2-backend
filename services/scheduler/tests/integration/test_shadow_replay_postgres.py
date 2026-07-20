"""PR 6.5a — deterministic end-to-end shadow replay over a disposable Postgres.

Drives the REAL chain (canonical requirement → draft → prediction → approval → activation →
validation-receipt dispatch) and proves PR 6.5's done-gate on two axes:
- RETRY idempotence: re-running against the SAME persisted DB yields identical lineage+receipts and
  adds ZERO rows to ANY scheduler.control_* table.
- COMPUTE determinism: two INDEPENDENT fresh-schema runs produce identical content hashes (so the
  optimizer/prediction is deterministic — something the same-DB retry cannot show, since create_draft
  replays the stored draft).
The SCADA client is validation-only (no Modbus write path). Set SCHEDULER_TEST_POSTGRES_URL to a
DISPOSABLE loopback Postgres.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import text

import migrations.migrate as migrate
from core.command_intent import command_intent_content_hash
from schemas.control_plan import DraftControlPlanRequest
from schemas.machine_boundary import CommandIntent
from services.clients.scada_validation_client import ScadaValidationClient
from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)
from tests.integration.test_control_plan_postgres import _sqlalchemy_url
from tests.integration.test_open_loop_worker_postgres import _connect
from tests.integration.test_scheduler_postgres import _test_url_loopback
from tests.shadow_replay_harness import run_shadow_replay

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None, reason="SCHEDULER_TEST_POSTGRES_URL not set"
)

# Within the draft's rotation windows (06:00–18:00) yet before the horizon-end deadline
# (2026-07-21T00:00) — so every activated intent is DUE (claimable), none past deadline.
CLOCK = datetime(2026, 7, 20, 18, 30, 0, tzinfo=timezone.utc)
FIXED_RECEIPT_ID = "99999999-9999-4999-8999-999999999999"


def _deterministic_scada_client():
    """A validation-only SCADA stand-in that echoes the dispatched intent's OWN identity + content
    hash (recomputed the scheduler's way) with a FIXED receipt_id/validated_at — so the receipt is
    byte-reproducible across runs."""

    def handler(request: httpx.Request) -> httpx.Response:
        intent_document = json.loads(request.content)
        intent = CommandIntent.model_validate(intent_document)
        return httpx.Response(
            200,
            json={
                "schema_version": 1,
                "receipt_id": FIXED_RECEIPT_ID,
                "intent_id": intent_document["intent_id"],
                "correlation_id": intent_document["correlation_id"],
                "request_id": intent_document["request_id"],
                "idempotency_key": intent_document["idempotency_key"],
                "intent_content_hash": command_intent_content_hash(intent),
                "capability_hash": intent_document["capability_hash"],
                "status": "validation_accepted",
                "validated_at": "2026-07-20T18:30:00.000Z",
                "reason_code": None,
            },
        )

    return ScadaValidationClient(
        "http://scada.local",
        lambda: "service-token",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _sessions():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(_sqlalchemy_url())
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _reset_schema():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
    finally:
        await conn.close()


async def _replay(session):
    return await run_shadow_replay(
        session,
        draft_request=DraftControlPlanRequest.model_validate(draft_payload()),
        actor="operator-1",
        clock=lambda: CLOCK,
        flow_client=FakeControlFlowClient(snapshot_mirror()),
        ros_client=FakeRosGisClient([requirement_item()]),
        scada_client=_deterministic_scada_client(),
    )


async def _all_control_table_counts(session) -> dict[str, int]:
    """Row counts of EVERY scheduler table — so 'zero new rows on retry' is table-agnostic, not
    inferred from receipts alone."""
    tables = (
        await session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'scheduler' ORDER BY table_name"
            )
        )
    ).scalars().all()
    counts = {}
    for table in tables:
        counts[table] = (
            await session.execute(text(f'SELECT count(*) FROM scheduler."{table}"'))
        ).scalar_one()
    return counts


@pytest.mark.asyncio
async def test_shadow_replay_is_restart_and_retry_deterministic():
    await _reset_schema()
    engine, sessions = _sessions()
    try:
        async with sessions() as s1:
            first = await _replay(s1)
        async with sessions() as s:
            before = await _all_control_table_counts(s)
        # Restart/retry: a fresh session against the SAME persisted DB — create_draft replays the
        # same plan, the guarded transitions are skipped, and dispatch re-runs idempotently.
        async with sessions() as s2:
            second = await _replay(s2)
        async with sessions() as s:
            after = await _all_control_table_counts(s)
    finally:
        await engine.dispose()

    assert first == second
    assert first.lifecycle_state == "shadow_active"
    # Non-vacuous: the chain actually produced command intents + a matching accepted receipt each.
    assert len(first.intents) > 0
    assert len(first.receipts) == len(first.intents)
    assert all(status == "validation_accepted" for _, status, _ in first.receipts)
    # Exactly-once, table-agnostic: the retry added ZERO rows to ANY scheduler table.
    assert before == after


@pytest.mark.asyncio
async def test_shadow_replay_compute_is_deterministic_across_independent_runs():
    # Two INDEPENDENT fresh-schema runs recompute the whole chain; identical content hashes prove
    # the optimizer + prediction are deterministic (the same-DB retry replays the stored draft and
    # so cannot show this). plan_id/intent idempotency_keys differ (fresh uuid4 allocate), so only
    # the content-addressed hashes compare across independent runs.
    await _reset_schema()
    engine, sessions = _sessions()
    try:
        async with sessions() as s:
            a = await _replay(s)
    finally:
        await engine.dispose()

    await _reset_schema()
    engine, sessions = _sessions()
    try:
        async with sessions() as s:
            b = await _replay(s)
    finally:
        await engine.dispose()

    assert a.input_content_hash == b.input_content_hash
    assert a.draft_content_hash == b.draft_content_hash
    assert a.intents != b.intents  # plan-id-keyed idempotency keys differ across independent runs
