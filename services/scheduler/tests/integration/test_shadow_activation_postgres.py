"""PR 4.3c-1 shadow-activation migration 0007 on real Postgres (env-gated).

Set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback Postgres. Verifies the
things a unit test cannot: that migration 0007 executes, that the RELAXED 0003
transition CHECKs admit shadow_active + the new edges (and still reject an illegal
edge), that the one-per-scope mutex PK enforces one active plan per (section, gate)
while remaining mutable (DELETE allowed), and that a down REFUSES once a
shadow_active row exists (forward-fix, never down).
"""

import hashlib
from uuid import uuid4

import asyncpg
import pytest

import migrations.migrate as migrate
from tests.integration.test_scheduler_postgres import _test_url_loopback

ACTIVATION_MIGRATION_ID = "0007_control_plan_shadow_activation"
OUTBOX = "scheduler.control_command_outbox"
MUTEX = "scheduler.control_active_gate_authority"

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None,
    reason="SCHEDULER_TEST_POSTGRES_URL not set",
)


async def _connect():
    return await asyncpg.connect(**migrate.postgres_connection_kwargs(_test_url_loopback()))


async def _regclass(conn, table):
    return await conn.fetchval("SELECT to_regclass($1)", table)


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


async def _insert_activation_transition(conn, plan_id, version, *, sequence, from_state):
    await conn.execute(
        """
        INSERT INTO scheduler.control_state_transitions (
            plan_id, plan_version, transition_sequence, transition_type,
            from_state, to_state, actor_subject
        ) VALUES ($1, $2, $3, 'shadow_activated', $4, 'shadow_active', 'op')
        """,
        plan_id, version, sequence, from_state,
    )


@pytest.mark.asyncio
async def test_migration_0007_relaxes_checks_and_enforces_the_scope_mutex():
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")

        # apply-all discovers 0001..0007 and applies each once; the new tables exist.
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes[ACTIVATION_MIGRATION_ID] == "applied"
        assert await _regclass(conn, OUTBOX) is not None
        assert await _regclass(conn, MUTEX) is not None

        # Rollback -> new tables gone (clean, no shadow_active rows yet); reapply.
        assert await migrate.rollback_migration(conn, ACTIVATION_MIGRATION_ID) == (
            "rolled-back"
        )
        assert await _regclass(conn, OUTBOX) is None
        assert await _regclass(conn, MUTEX) is None
        assert await migrate.apply_migration(conn, ACTIVATION_MIGRATION_ID) == "applied"

        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)

        # B1: the relaxed CHECK admits the shadow_activated edge (approved -> active).
        await _insert_activation_transition(
            conn, plan_id, version, sequence=2, from_state="approved_for_shadow"
        )
        # ... and still rejects an undeclared edge (shadow_activated from draft).
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _insert_activation_transition(
                conn, plan_id, version, sequence=3, from_state="draft"
            )

        # One-per-scope mutex: a second row on the SAME (section, gate) conflicts.
        await conn.execute(
            "INSERT INTO scheduler.control_active_gate_authority "
            "(section_id, gate_id, plan_id, plan_version, "
            "activation_transition_sequence) VALUES ('sec-1', 'M(0,0;1,0)', $1, $2, 2)",
            plan_id, version,
        )
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await conn.execute(
                "INSERT INTO scheduler.control_active_gate_authority "
                "(section_id, gate_id, plan_id, plan_version, "
                "activation_transition_sequence) VALUES ('sec-1', 'M(0,0;1,0)', $1, "
                "$2, 2)",
                plan_id, version,
            )
        # The mutex is MUTABLE — DELETE is allowed (no immutability trigger).
        await conn.execute(
            "DELETE FROM scheduler.control_active_gate_authority WHERE gate_id = "
            "'M(0,0;1,0)'"
        )

        # A down REFUSES while a shadow_active transition exists (re-adding the narrow
        # to_state CHECK validates existing rows), so the tables survive.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await migrate.rollback_migration(conn, ACTIVATION_MIGRATION_ID)
        assert await _regclass(conn, OUTBOX) is not None
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_insert_activation_through_the_real_repository_maps_a_scope_conflict():
    """Drive PostgresControlPlanRepository.insert_activation + the release path
    through the ACTUAL code path (unit tests use the fake; this pins the real
    IntegrityError -> ScopeConflictError mapping and the atomic mutex release)."""
    from datetime import datetime, timezone

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from repositories.control_plan_repository import (
        PostgresControlPlanRepository,
        ScopeConflictError,
        ScopeRow,
        TransitionRecord,
    )
    from tests.integration.test_control_plan_postgres import _sqlalchemy_url

    now = datetime.now(timezone.utc)

    def _activate_txn(seq):
        return TransitionRecord(
            transition_sequence=seq,
            transition_type="shadow_activated",
            from_state="approved_for_shadow",
            to_state="shadow_active",
            actor_subject="op",
            reason=None,
            transition_document_text=None,
            occurred_at=now,
        )

    scope = [
        ScopeRow(
            section_id="sec-1",
            gate_id="M(0,0;1,0)",
            activation_transition_sequence=2,
        )
    ]
    conn = await _connect()
    engine = None
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await migrate.apply_all_migrations(conn)
        plan_a, plan_b, version = uuid4(), uuid4(), 1
        await _insert_run(conn, plan_a, version)
        await _insert_run(conn, plan_b, version)

        engine = create_async_engine(_sqlalchemy_url())
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        repo = PostgresControlPlanRepository()

        async with sessions() as session:
            await repo.insert_activation(
                session, plan_id=plan_a, plan_version=version,
                transition=_activate_txn(2), outbox_rows=[], scope_rows=scope,
            )
        # A second plan taking the SAME (section, gate) must surface the mutex PK
        # conflict as ScopeConflictError — never a misclassified TransitionConflict.
        async with sessions() as session:
            with pytest.raises(ScopeConflictError):
                await repo.insert_activation(
                    session, plan_id=plan_b, plan_version=version,
                    transition=_activate_txn(2), outbox_rows=[], scope_rows=scope,
                )
        # The release path (invalidate-from-active) frees plan_a's mutex row.
        async with sessions() as session:
            await repo.append_transition_and_release_scope(
                session, plan_id=plan_a, plan_version=version,
                transition=TransitionRecord(
                    3, "invalidated", "shadow_active", "invalidated", "op", None,
                    None, now,
                ),
            )
        assert await conn.fetchval(
            "SELECT count(*) FROM scheduler.control_active_gate_authority"
        ) == 0
    finally:
        if engine is not None:
            await engine.dispose()
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_migration_0008_admits_the_active_supersede_edge():
    """0008 widens the edge graph so a shadow_active plan can be gracefully
    superseded; an undeclared edge is still rejected, and a down refuses once such a
    row exists."""
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes["0008_control_plan_active_supersede"] == "applied"

        plan_id, version = uuid4(), 1
        await _insert_run(conn, plan_id, version)
        await _insert_activation_transition(
            conn, plan_id, version, sequence=2, from_state="approved_for_shadow"
        )
        # B1(0008): the (superseded, shadow_active, superseded) edge is admitted.
        await conn.execute(
            "INSERT INTO scheduler.control_state_transitions (plan_id, plan_version,"
            " transition_sequence, transition_type, from_state, to_state, "
            "actor_subject) VALUES ($1, $2, 3, 'superseded', 'shadow_active', "
            "'superseded', 'op')",
            plan_id, version,
        )
        # ... but an undeclared edge (superseded straight from draft) is rejected.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await conn.execute(
                "INSERT INTO scheduler.control_state_transitions (plan_id, "
                "plan_version, transition_sequence, transition_type, from_state, "
                "to_state, actor_subject) VALUES ($1, $2, 4, 'superseded', 'draft', "
                "'superseded', 'op')",
                plan_id, version,
            )
        # A down REFUSES while a graceful-supersede row exists (forward-fix).
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await migrate.rollback_migration(
                conn, "0008_control_plan_active_supersede"
            )
    finally:
        try:
            await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        finally:
            await conn.close()
