"""PR 6.3a shadow dispatcher on real Postgres (env-gated).

Set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback Postgres. Verifies what a unit
test cannot: migration 0010 applies (append-only + one-receipt-per-intent PK), that a full
claim -> dispatch -> persist tick stores EXACTLY ONE receipt, that a restart/retry re-run
produces zero new rows (SCADA's idempotent replay + ON CONFLICT compose), and that
record_validation_receipt is exactly-once under a real PK conflict.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest

import migrations.migrate as migrate
from tests.integration.test_open_loop_worker_postgres import (
    _connect,
    _seed_active_plan,
    _sessions,
)
from tests.integration.test_scheduler_postgres import _test_url_loopback

RECEIPTS = "scheduler.control_command_validation_receipts"
NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None,
    reason="SCHEDULER_TEST_POSTGRES_URL not set",
)


def _mock_scada_client(intent_id, *, status="validation_accepted", reason_code=None,
                       status_code=200):
    def handler(request):
        return httpx.Response(
            status_code,
            json={
                "schema_version": 1,
                "receipt_id": "99999999-9999-4999-8999-999999999999",
                "intent_id": str(intent_id),
                "correlation_id": "22222222-2222-4222-8222-222222222222",
                "request_id": f"req.{intent_id}",
                "idempotency_key": f"idem.{intent_id}",
                "intent_content_hash": "b" * 64,
                "capability_hash": "a" * 64,
                "status": status,
                "validated_at": "2026-07-20T03:00:00.000Z",
                "reason_code": reason_code,
            },
        )

    from services.clients.scada_validation_client import ScadaValidationClient

    return ScadaValidationClient(
        "http://scada.local",
        lambda: "service-token",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _dispatch_service(repo, scada_client):
    from services.open_loop_execution_service import OpenLoopExecutionService
    from services.shadow_dispatch_service import ShadowDispatchService

    open_loop = OpenLoopExecutionService(
        repo, clock=lambda: NOW, execution_mode="shadow"
    )
    return ShadowDispatchService(repo, scada_client, open_loop, clock=lambda: NOW)


@pytest.mark.asyncio
async def test_migration_0010_applies_and_is_append_only():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes["0010_shadow_dispatch_receipts"] == "applied"
        plan_id, version, [intent_id] = await _seed_active_plan(
            conn,
            not_before=NOW - timedelta(hours=1),
            deadline=NOW + timedelta(hours=5),
        )
        await conn.execute(
            f"""INSERT INTO {RECEIPTS} (
                intent_id, plan_id, plan_version, receipt_id, correlation_id, request_id,
                idempotency_key, intent_content_hash, capability_hash, status, reason_code,
                validated_at, receipt_document_text, receipt_content_sha256,
                dispatch_worker_id, dispatched_at
            ) VALUES ($1,$2,$3,$4,$5,'r','k',$6,$7,'validation_accepted',NULL,
                      now(),'{{}}',$8,'w',now())""",
            intent_id, plan_id, version, uuid4(), uuid4(), "b" * 64, "a" * 64, "c" * 64,
        )
        # Append-only: UPDATE and DELETE are rejected by the immutability trigger.
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(
                f"UPDATE {RECEIPTS} SET status='validation_rejected' WHERE intent_id=$1",
                intent_id,
            )
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute(f"DELETE FROM {RECEIPTS} WHERE intent_id=$1", intent_id)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_full_tick_persists_one_receipt_and_is_restart_safe():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, [intent_id] = await _seed_active_plan(
            conn,
            not_before=NOW - timedelta(hours=1),
            deadline=NOW + timedelta(hours=5),
        )
    finally:
        await conn.close()

    engine, sessions = _sessions()
    try:
        from repositories.control_plan_repository import PostgresControlPlanRepository

        repo = PostgresControlPlanRepository()
        client = _mock_scada_client(intent_id)
        service = _dispatch_service(repo, client)
        async with sessions() as session:
            report = await service.run_shadow_dispatch_once(session, plan_id, version)
        assert report.action == "dispatched"
        assert report.persisted_receipts == 1
        # Restart / retry: the same tick re-run dispatches nothing new (already receipted).
        async with sessions() as session:
            again = await service.run_shadow_dispatch_once(session, plan_id, version)
        assert again.persisted_receipts == 0
        await client.aclose()
    finally:
        await engine.dispose()

    conn = await _connect()
    try:
        count = await conn.fetchval(
            f"SELECT count(*) FROM {RECEIPTS} WHERE intent_id=$1", intent_id
        )
        assert count == 1
        row = await conn.fetchrow(
            f"SELECT status, receipt_content_sha256 FROM {RECEIPTS} WHERE intent_id=$1",
            intent_id,
        )
        assert row["status"] == "validation_accepted"
        assert len(row["receipt_content_sha256"]) == 64
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_record_validation_receipt_is_exactly_once_under_pk_conflict():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, [intent_id] = await _seed_active_plan(
            conn,
            not_before=NOW - timedelta(hours=1),
            deadline=NOW + timedelta(hours=5),
        )
    finally:
        await conn.close()

    engine, sessions = _sessions()
    try:
        from repositories.control_plan_repository import (
            PostgresControlPlanRepository,
            ValidationReceiptRow,
        )

        repo = PostgresControlPlanRepository()

        def _row():
            return ValidationReceiptRow(
                intent_id=intent_id, plan_id=plan_id, plan_version=version,
                receipt_id=uuid4(), correlation_id=uuid4(), request_id="r",
                idempotency_key=f"idem.{intent_id}", intent_content_hash="b" * 64,
                capability_hash="a" * 64, status="validation_accepted", reason_code=None,
                validated_at=NOW, receipt_document_text="{}",
                receipt_content_sha256="c" * 64, dispatch_worker_id="w", dispatched_at=NOW,
            )

        async with sessions() as session:
            first = await repo.record_validation_receipt(session, _row())
        async with sessions() as session:
            second = await repo.record_validation_receipt(session, _row())
        assert first is True
        assert second is False  # ON CONFLICT (intent_id) DO NOTHING
    finally:
        await engine.dispose()

    conn = await _connect()
    try:
        count = await conn.fetchval(
            f"SELECT count(*) FROM {RECEIPTS} WHERE intent_id=$1", intent_id
        )
        assert count == 1
    finally:
        await conn.close()
