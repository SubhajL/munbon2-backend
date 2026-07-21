"""PR 7.2 durable execution receipts on disposable loopback Postgres."""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

import migrations.migrate as migrate
from core.canonical_json import canonicalize, sha256_hex
from repositories.control_plan_repository import ExecutionEventRow, ExecutionReceiptRow
from tests.integration.test_authority_grants_postgres import (
    NOW,
    _candidate,
    _outbox_hashes,
    _rows_for,
)
from tests.integration.test_open_loop_worker_postgres import (
    _connect,
    _seed_active_plan,
    _sessions,
)
from tests.integration.test_scheduler_postgres import _test_url_loopback

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None,
    reason="SCHEDULER_TEST_POSTGRES_URL not set",
)


@pytest.mark.asyncio
async def test_operator_hold_waits_for_the_inflight_authority_execution_lock():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                PostgresControlPlanRepository,
            )

            repository = PostgresControlPlanRepository()
            async with sessions() as execution_session, sessions() as hold_session:
                await repository.acquire_authority_execution_lock(
                    execution_session, uuid4()
                )
                hold = ExecutionEventRow(
                    event_id=uuid4(),
                    intent_id=None,
                    event_type="held",
                    worker_id="integration-test",
                    detail_document_text="operator hold",
                    occurred_at=NOW,
                )
                append = asyncio.create_task(
                    repository.append_execution_events(
                        hold_session, plan_id, version, [hold]
                    )
                )
                await asyncio.sleep(0.1)
                assert append.done() is False
                await execution_session.rollback()
                await asyncio.wait_for(append, timeout=2)
        finally:
            await engine.dispose()
    finally:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_execution_receipt_migration_is_immutable_atomic_and_forward_fix_only():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes["0013_operator_approved_execution"] == "applied"

        await migrate.rollback_migration(conn, "0013_operator_approved_execution")
        assert (
            await conn.fetchval(
                "SELECT to_regclass('scheduler.control_command_execution_receipts')"
            )
            is None
        )
        assert (
            await migrate.apply_migration(conn, "0013_operator_approved_execution")
            == "applied"
        )

        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                PostgresControlPlanRepository,
            )

            repository = PostgresControlPlanRepository()
            grant, birth = _rows_for(
                _candidate(plan_id, version),
                await _outbox_hashes(conn, plan_id, version),
            )
            async with sessions() as session:
                await repository.insert_authority_grant(session, grant, lambda: birth)

            outbox = await conn.fetchrow(
                "SELECT intent_id, idempotency_key, intent_content_hash, "
                "capability_hash, target_level "
                "FROM scheduler.control_command_outbox "
                "WHERE plan_id = $1 AND plan_version = $2 "
                "ORDER BY event_sequence LIMIT 1",
                plan_id,
                version,
            )
            receipt_id = uuid4()
            execution_hash = "9" * 64
            document = canonicalize(
                {
                    "schema_version": 1,
                    "receipt_id": str(receipt_id),
                    "intent_id": str(outbox["intent_id"]),
                    "idempotency_key": outbox["idempotency_key"],
                    "grant_id": str(grant.grant_id),
                    "authority_not_after": (NOW + timedelta(minutes=5))
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "original_intent_content_hash": outbox["intent_content_hash"],
                    "execution_intent_content_hash": execution_hash,
                    "capability_hash": outbox["capability_hash"],
                    "purpose": "operator_approved",
                    "status": "execution_failed",
                    "reason_code": "write_failed",
                    "target_level": outbox["target_level"],
                    "observed_level": None,
                    "readback_quality": "unavailable",
                    "writes": [],
                    "executed_at": NOW.isoformat().replace("+00:00", "Z"),
                }
            )
            receipt = ExecutionReceiptRow(
                intent_id=UUID(str(outbox["intent_id"])),
                plan_id=plan_id,
                plan_version=version,
                grant_id=grant.grant_id,
                authority_not_after=NOW + timedelta(minutes=5),
                receipt_id=receipt_id,
                idempotency_key=outbox["idempotency_key"],
                original_intent_content_hash=outbox["intent_content_hash"],
                execution_intent_content_hash=execution_hash,
                capability_hash=outbox["capability_hash"],
                purpose="operator_approved",
                status="execution_failed",
                reason_code="write_failed",
                target_level=outbox["target_level"],
                observed_level=None,
                readback_quality="unavailable",
                writes_document_text="[]",
                executed_at=NOW,
                receipt_document_text=document,
                receipt_content_sha256=sha256_hex(document),
                dispatch_worker_id="integration-test",
                dispatched_at=NOW,
            )
            hold = ExecutionEventRow(
                event_id=uuid4(),
                intent_id=None,
                event_type="held",
                worker_id="integration-test",
                detail_document_text="write failed",
                occurred_at=NOW,
            )
            async with sessions() as session:
                inserted = await repository.record_execution_receipt(
                    session, receipt, hold_event=hold
                )

            assert inserted is True
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM scheduler.control_command_execution_receipts"
                )
                == 1
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM scheduler.control_command_execution_events "
                    "WHERE event_type = 'held'"
                )
                == 1
            )
            with pytest.raises(asyncpg.exceptions.RaiseError):
                await conn.execute(
                    "UPDATE scheduler.control_command_execution_receipts "
                    "SET status = 'execution_succeeded'"
                )
            with pytest.raises(asyncpg.exceptions.RaiseError):
                await migrate.rollback_migration(
                    conn, "0013_operator_approved_execution"
                )
        finally:
            await engine.dispose()
    finally:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()
