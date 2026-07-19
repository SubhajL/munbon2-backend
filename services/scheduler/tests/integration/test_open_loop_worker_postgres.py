"""PR 5.2b open-loop worker + migration 0009 on real Postgres (env-gated).

Set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback Postgres. Verifies what a
unit test cannot: that migration 0009's execution log applies (append-only + the
one-terminal-event-per-intent partial unique index), that the worker claims due
intents locally WITHOUT any dispatch, that a missed deadline atomically invalidates
the remaining campaign and RELEASES the authority mutex, that hold pauses claiming
without releasing authority (and resume lifts it, while a missed deadline still
overrides a hold), and that a new same-campaign version cannot replan an active one.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest

import migrations.migrate as migrate
from tests.integration.test_scheduler_postgres import _test_url_loopback

EVENTS = "scheduler.control_command_execution_events"
MUTEX = "scheduler.control_active_gate_authority"
NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

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
            $6, now(), now() + interval '6 days', 3600, 1, '{}', '{}', '{}', $6, 'op'
        )
        """,
        plan_id, version,
        hashlib.sha256(f"in:{plan_id}".encode()).hexdigest(),
        hashlib.sha256(f"draft:{plan_id}".encode()).hexdigest(),
        uuid4(), "3" * 64,
    )


async def _insert_campaign(conn, campaign_id, plan_id, version):
    await conn.execute(
        "INSERT INTO scheduler.control_plan_campaign_versions "
        "(campaign_id, plan_version, plan_id) VALUES ($1, $2, $3)",
        campaign_id, version, plan_id,
    )


async def _insert_outbox_intent(conn, plan_id, version, *, event_sequence, not_before,
                                deadline, intent_id=None):
    intent_id = intent_id or uuid4()
    await conn.execute(
        """
        INSERT INTO scheduler.control_command_outbox (
            intent_id, correlation_id, request_id, idempotency_key, canonical_gate_id,
            event_kind, event_sequence, gate_event_sequence, device_id, adapter_gate_id,
            capability_release_id, capability_hash, target_position_m, target_level,
            not_before, deadline, mode, intent_document_text, intent_content_hash,
            plan_id, plan_version, activation_transition_sequence
        ) VALUES (
            $1, $2, $3, $4, 'G1', 'open', $5, $5, 'dev-1', 'adapter-1', 'rel-1', $6,
            1.5, 3, $7, $8, 'shadow', '{}', $9, $10, $11, 4
        )
        """,
        intent_id, uuid4(), f"req.{intent_id}", f"idem.{intent_id}", event_sequence,
        "a" * 64, not_before, deadline, "b" * 64, plan_id, version,
    )
    return intent_id


_TO_ACTIVE = [
    ("draft_created", None, "draft"),
    ("review_requested", "draft", "under_review"),
    ("shadow_approved", "under_review", "approved_for_shadow"),
    ("shadow_activated", "approved_for_shadow", "shadow_active"),
]


async def _insert_chain(conn, plan_id, version, edges=_TO_ACTIVE):
    for sequence, (ttype, frm, to) in enumerate(edges, start=1):
        await conn.execute(
            "INSERT INTO scheduler.control_state_transitions (plan_id, plan_version, "
            "transition_sequence, transition_type, from_state, to_state, actor_subject)"
            " VALUES ($1, $2, $3, $4, $5, $6, 'op')",
            plan_id, version, sequence, ttype, frm, to,
        )


async def _insert_mutex(conn, plan_id, version, *, section="sec-1", gate="G1",
                        granted_at=NOW):
    await conn.execute(
        "INSERT INTO scheduler.control_active_gate_authority (section_id, gate_id, "
        "plan_id, plan_version, activation_transition_sequence, granted_at) "
        "VALUES ($1, $2, $3, $4, 4, $5)",
        section, gate, plan_id, version, granted_at,
    )


def _service(**kwargs):
    from repositories.control_plan_repository import PostgresControlPlanRepository
    from services.open_loop_execution_service import OpenLoopExecutionService

    return OpenLoopExecutionService(PostgresControlPlanRepository(), **kwargs)


def _sessions():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from tests.integration.test_control_plan_postgres import _sqlalchemy_url

    engine = create_async_engine(_sqlalchemy_url())
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_active_plan(conn, *, granted_at=NOW, not_before, deadline, n_intents=1):
    """A shadow_active plan holding scope (sec-1,G1) with n_intents due-ish outbox
    intents. Returns (plan_id, version, [intent_ids])."""
    plan_id, version = uuid4(), 1
    await _insert_run(conn, plan_id, version)
    await _insert_chain(conn, plan_id, version)
    await _insert_mutex(conn, plan_id, version, granted_at=granted_at)
    intent_ids = []
    for i in range(n_intents):
        intent_ids.append(
            await _insert_outbox_intent(
                conn, plan_id, version, event_sequence=i + 1,
                not_before=not_before, deadline=deadline,
            )
        )
    return plan_id, version, intent_ids


@pytest.mark.asyncio
async def test_migration_0009_execution_log_is_append_only_with_one_claim_per_intent():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes["0009_open_loop_execution"] == "applied"
        assert await conn.fetchval("SELECT to_regclass($1)", EVENTS) is not None

        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)
        intent_id = await _insert_outbox_intent(
            conn, plan_id, version, event_sequence=1, not_before=NOW,
            deadline=NOW + timedelta(days=6),
        )

        async def _insert_event(event_type, iid, eid=None):
            await conn.execute(
                "INSERT INTO scheduler.control_command_execution_events "
                "(event_id, plan_id, plan_version, intent_id, event_type, occurred_at)"
                " VALUES ($1, $2, $3, $4, $5, now())",
                eid or uuid4(), plan_id, version, iid, event_type,
            )

        await _insert_event("claimed", intent_id)
        # ONE TERMINAL event per intent: a second claim conflicts, and so does an
        # invalidate/miss for an already-claimed intent — so a concurrent claim +
        # invalidate can never both land as a contradictory pair (the H1 invariant).
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await _insert_event("claimed", intent_id)
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await _insert_event("invalidated", intent_id)
        # Append-only: UPDATE and DELETE are rejected by the immutability trigger.
        with pytest.raises(asyncpg.exceptions.RaiseError):
            await conn.execute(
                "UPDATE scheduler.control_command_execution_events SET worker_id='x'"
            )
        with pytest.raises(asyncpg.exceptions.RaiseError):
            await conn.execute(
                "DELETE FROM scheduler.control_command_execution_events"
            )
        # A per-intent event MUST carry an intent (intent_scope CHECK).
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _insert_event("claimed", None)
        # A plan-level held event MUST NOT carry an intent.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _insert_event("held", intent_id)
        # down drops the table.
        assert await migrate.rollback_migration(conn, "0009_open_loop_execution") == (
            "rolled-back"
        )
        assert await conn.fetchval("SELECT to_regclass($1)", EVENTS) is None
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_claim_due_intents_appends_one_event_and_dispatches_nothing():
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, [intent_id] = await _seed_active_plan(
            conn, granted_at=NOW,
            not_before=NOW - timedelta(seconds=60),  # inside pre-move window -> due
            deadline=NOW + timedelta(days=6),
        )
        engine, sessions = _sessions()
        service = _service(execution_mode="shadow")

        async with sessions() as session:
            claimed = await service.claim_due_intents(
                session, plan_id, version, worker_id="w1", now=NOW
            )
        assert list(claimed) == [intent_id]
        rows = await conn.fetch(
            "SELECT event_type, worker_id FROM "
            "scheduler.control_command_execution_events WHERE intent_id = $1",
            intent_id,
        )
        assert [(r["event_type"], r["worker_id"]) for r in rows] == [("claimed", "w1")]

        # Idempotent: a second claim adds NO new event (double-claim backstop).
        async with sessions() as session:
            again = await service.claim_due_intents(
                session, plan_id, version, worker_id="w1", now=NOW
            )
        assert again == ()
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_command_execution_events "
            "WHERE intent_id = $1 AND event_type = 'claimed'", intent_id
        ) == 1
        # No dispatch: the plan stays shadow_active and keeps its authority row.
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_active_gate_authority "
            "WHERE plan_id = $1", plan_id
        ) == 1
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_missed_deadline_invalidates_remaining_intents_and_releases_mutex():
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        # Three intents; all past their (shared) deadline at NOW -> the earliest is
        # missed and the rest are invalidated; the plan is invalidated + released.
        plan_id, version, intent_ids = await _seed_active_plan(
            conn, granted_at=NOW - timedelta(hours=1),
            not_before=NOW - timedelta(hours=3),
            deadline=NOW - timedelta(minutes=1),  # already past
            n_intents=3,
        )
        engine, sessions = _sessions()
        service = _service(execution_mode="shadow")

        async with sessions() as session:
            result = await service.advance_open_loop_execution(
                session, plan_id, version, worker_id="w1", now=NOW
            )
        assert result.invalidated is True

        events = {
            r["intent_id"]: r["event_type"]
            for r in await conn.fetch(
                "SELECT intent_id, event_type FROM "
                "scheduler.control_command_execution_events WHERE plan_id = $1", plan_id
            )
        }
        assert events[intent_ids[0]] == "missed"
        assert events[intent_ids[1]] == "invalidated"
        assert events[intent_ids[2]] == "invalidated"
        # The plan reached lifecycle 'invalidated' AND its authority mutex is released.
        assert await conn.fetchval(
            "SELECT to_state FROM scheduler.control_state_transitions WHERE "
            "plan_id = $1 ORDER BY transition_sequence DESC LIMIT 1", plan_id
        ) == "invalidated"
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_active_gate_authority "
            "WHERE plan_id = $1", plan_id
        ) == 0
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_hold_pauses_claiming_without_releasing_authority():
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, [intent_id] = await _seed_active_plan(
            conn, granted_at=NOW,
            not_before=NOW - timedelta(seconds=60),  # would be due
            deadline=NOW + timedelta(days=6),
        )
        engine, sessions = _sessions()
        service = _service(execution_mode="shadow")

        async with sessions() as session:
            await service.hold_control_plan(
                session, plan_id, version, "operator-1", "manual check", now=NOW
            )
        async with sessions() as session:
            claimed = await service.claim_due_intents(
                session, plan_id, version, worker_id="w1", now=NOW
            )
        assert claimed == ()  # held -> nothing claimed
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_command_execution_events "
            "WHERE event_type = 'claimed'"
        ) == 0
        # Hold is NOT a lifecycle transition: the plan stays active and KEEPS its
        # authority row (a lifecycle exit would wrongly release the scope).
        assert await conn.fetchval(
            "SELECT to_state FROM scheduler.control_state_transitions WHERE "
            "plan_id = $1 ORDER BY transition_sequence DESC LIMIT 1", plan_id
        ) == "shadow_active"
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_active_gate_authority "
            "WHERE plan_id = $1", plan_id
        ) == 1
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_new_daily_run_cannot_replan_active_campaign():
    # A new same-campaign version may be drafted, but it can neither mutate the active
    # plan's outbox nor take its scope without an explicit supersede: the immutable
    # outbox + one-per-scope mutex structurally forbid an automatic replan.
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        campaign_id = uuid4()
        active_id, v1, [intent_id] = await _seed_active_plan(
            conn, granted_at=NOW, not_before=NOW, deadline=NOW + timedelta(days=6),
        )
        await _insert_campaign(conn, campaign_id, active_id, v1)
        outbox_before = await conn.fetch(
            "SELECT intent_id, intent_content_hash FROM "
            "scheduler.control_command_outbox WHERE plan_id = $1", active_id
        )
        transitions_before = await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_state_transitions WHERE plan_id=$1",
            active_id,
        )

        # A new daily run -> a new campaign version (v2), a fresh plan_id.
        successor_id, v2 = uuid4(), 2
        await _insert_run(conn, successor_id, v2)
        await _insert_campaign(conn, campaign_id, successor_id, v2)

        # The active plan's outbox + transition history are byte-for-byte unchanged.
        outbox_after = await conn.fetch(
            "SELECT intent_id, intent_content_hash FROM "
            "scheduler.control_command_outbox WHERE plan_id = $1", active_id
        )
        assert outbox_after == outbox_before
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_state_transitions WHERE plan_id=$1",
            active_id,
        ) == transitions_before

        # Activating the successor on the SAME scope without superseding is refused by
        # the one-per-scope mutex PK — no automatic replan of the active campaign.
        engine, sessions = _sessions()
        from datetime import datetime as _dt
        from repositories.control_plan_repository import (
            PostgresControlPlanRepository, ScopeConflictError, ScopeRow,
            TransitionRecord,
        )

        repo = PostgresControlPlanRepository()
        txn = TransitionRecord(
            2, "shadow_activated", "approved_for_shadow", "shadow_active", "op", None,
            None, _dt.now(timezone.utc),
        )
        scope = [ScopeRow("sec-1", "G1", 2)]
        async with sessions() as session:
            with pytest.raises(ScopeConflictError):
                await repo.insert_activation(
                    session, plan_id=successor_id, plan_version=v2, transition=txn,
                    outbox_rows=[], scope_rows=scope,
                )
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_resume_lifts_hold_and_claiming_proceeds():
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, [intent_id] = await _seed_active_plan(
            conn, granted_at=NOW,
            not_before=NOW - timedelta(seconds=60),
            deadline=NOW + timedelta(days=6),
        )
        engine, sessions = _sessions()
        service = _service(execution_mode="shadow")

        async with sessions() as session:
            await service.hold_control_plan(session, plan_id, version, "op", now=NOW)
        async with sessions() as session:
            assert await service.claim_due_intents(
                session, plan_id, version, worker_id="w1", now=NOW
            ) == ()
        # Resume lifts the hold; the same due intent now claims.
        async with sessions() as session:
            await service.resume_control_plan(
                session, plan_id, version, "op", now=NOW + timedelta(minutes=1)
            )
        async with sessions() as session:
            claimed = await service.claim_due_intents(
                session, plan_id, version, worker_id="w1",
                now=NOW + timedelta(minutes=2),
            )
        assert list(claimed) == [intent_id]
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_held_plan_still_invalidates_on_missed_deadline():
    # Safety overrides a stale pause: a missed deadline invalidates + releases even a
    # held plan (advance checks the miss before the hold).
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, granted_at=NOW - timedelta(hours=1),
            not_before=NOW - timedelta(hours=3),
            deadline=NOW - timedelta(minutes=1),  # already past
        )
        engine, sessions = _sessions()
        service = _service(execution_mode="shadow")

        async with sessions() as session:
            await service.hold_control_plan(session, plan_id, version, "op", now=NOW)
        async with sessions() as session:
            result = await service.advance_open_loop_execution(
                session, plan_id, version, worker_id="w1", now=NOW
            )
        assert result.invalidated is True
        assert await conn.fetchval(
            "SELECT to_state FROM scheduler.control_state_transitions WHERE "
            "plan_id = $1 ORDER BY transition_sequence DESC LIMIT 1", plan_id
        ) == "invalidated"
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_active_gate_authority "
            "WHERE plan_id = $1", plan_id
        ) == 0
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()
