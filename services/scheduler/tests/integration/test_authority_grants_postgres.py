"""PR 7.1a authority grants on real Postgres (env-gated).

Set SCHEDULER_TEST_POSTGRES_URL to a DISPOSABLE loopback Postgres. Proves what
the unit fakes cannot: migration 0012 applies/rolls back/reapplies (and its
down REFUSES once evidence exists), both tables are trigger-immutable, the
grant + birth event commit atomically, one-grant-per-plan-version is
DB-enforced, and two RACING revocations persist exactly ONE terminal event
(partial unique index + advisory-lock append compose)."""

import asyncio
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

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)
GRANTS = "scheduler.control_authority_grants"
EVENTS = "scheduler.control_authority_grant_events"

pytestmark = pytest.mark.skipif(
    _test_url_loopback() is None,
    reason="SCHEDULER_TEST_POSTGRES_URL not set",
)


def test_rollback_locks_parent_before_child():
    down_sql = migrate.MIGRATIONS_DIR.joinpath(
        "0012_authority_grants.down.sql"
    ).read_text()
    parent_lock = "LOCK TABLE scheduler.control_authority_grants"
    child_lock = "LOCK TABLE scheduler.control_authority_grant_events"
    assert (
        down_sql.index(parent_lock)
        < down_sql.index("IF EXISTS (SELECT 1")
        < down_sql.index(child_lock)
    )


def _candidate(plan_id, plan_version):
    from core.authority_grant import AuthorityGrantCandidate

    sha_a, sha_b, sha_c = "a" * 64, "b" * 64, "c" * 64
    return AuthorityGrantCandidate(
        plan_id=plan_id,
        plan_version=plan_version,
        model_release_id="hydraulic-model-2026.06",
        model_release_content_hash=sha_a,
        engine_descriptor_content_hash=sha_b,
        commandability_evidence={
            "schema_version": 1,
            "model_release_id": "hydraulic-model-2026.06",
            "model_release_content_hash": sha_a,
            "engine_descriptor_content_hash": sha_b,
            "commandable": True,
            "approval_refs": ["RID-approval-2026-118"],
        },
        capability_release_id="field-registry-2026.06",
        capability_hash=sha_c,
        scope={
            "schema_version": 1,
            "gate_paths": [
                {
                    "section_id": "sec-1",
                    "canonical_gate_id": "G1",
                    "path_reach_ids": ["R-1"],
                }
            ],
        },
        flow_lower_exclusive_m3s=0.0,
        flow_upper_inclusive_m3s=8.0,
        initialization={"kind": "dry"},
        maximum_continuous_open_seconds=6 * 3600,
        maximum_intermediate_trims=1,
        shadow_evidence_sha256="d" * 64,
        hold_drill_evidence_sha256="e" * 64,
        rollback_drill_evidence_sha256="f" * 64,
        evidence_manifest={"schema_version": 1, "refs": ["drill-log-1"]},
        expires_at=NOW + 12 * timedelta(hours=1),
    )


async def _outbox_hashes(conn, plan_id, version):
    rows = await conn.fetch(
        "SELECT intent_content_hash FROM scheduler.control_command_outbox "
        "WHERE plan_id = $1 AND plan_version = $2 ORDER BY event_sequence",
        plan_id,
        version,
    )
    return [row["intent_content_hash"] for row in rows]


def _rows_for(candidate, intent_hashes, *, actor="supervisor-1"):
    """Build a (grant_row, birth_event_row) pair the way the service does, so
    verify_stored_grant passes on load."""
    from core.authority_grant import (
        AUTHORITY_GRANT_SCHEMA_VERSION,
        build_grant_document,
        grant_content_sha256,
        intent_set_sha256,
    )
    from core.canonical_json import canonicalize, sha256_hex
    from repositories.control_plan_repository import AuthorityGrantRow
    from services.authority_grant_service import AuthorityGrantService

    intent_set = intent_set_sha256(intent_hashes)
    document = build_grant_document(
        candidate, intent_content_hashes=tuple(intent_hashes)
    )
    grant_id = uuid4()
    grant = AuthorityGrantRow(
        grant_id=grant_id,
        authority_schema_version=AUTHORITY_GRANT_SCHEMA_VERSION,
        plan_id=candidate.plan_id,
        plan_version=candidate.plan_version,
        model_release_id=candidate.model_release_id,
        model_release_content_hash=candidate.model_release_content_hash,
        engine_descriptor_content_hash=candidate.engine_descriptor_content_hash,
        model_release_commandable=True,
        commandability_evidence_document_text=canonicalize(
            dict(candidate.commandability_evidence)
        ),
        commandability_evidence_sha256=sha256_hex(
            canonicalize(dict(candidate.commandability_evidence))
        ),
        capability_release_id=candidate.capability_release_id,
        capability_hash=candidate.capability_hash,
        scope_document_text=canonicalize(dict(candidate.scope)),
        scope_sha256=sha256_hex(canonicalize(dict(candidate.scope))),
        intent_set_sha256=intent_set,
        flow_lower_exclusive_m3s=candidate.flow_lower_exclusive_m3s,
        flow_upper_inclusive_m3s=candidate.flow_upper_inclusive_m3s,
        initialization_document_text=canonicalize(dict(candidate.initialization)),
        initialization_sha256=sha256_hex(canonicalize(dict(candidate.initialization))),
        maximum_continuous_open_seconds=candidate.maximum_continuous_open_seconds,
        maximum_intermediate_trims=candidate.maximum_intermediate_trims,
        grant_document_text=canonicalize(document),
        grant_content_sha256=grant_content_sha256(document),
        created_by_subject=actor,
        request_id="req-1",
    )
    birth = AuthorityGrantService._build_event(
        grant_id,
        1,
        "granted",
        effective_expires_at=candidate.expires_at,
        shadow_evidence_sha256=candidate.shadow_evidence_sha256,
        hold_drill_evidence_sha256=candidate.hold_drill_evidence_sha256,
        rollback_drill_evidence_sha256=candidate.rollback_drill_evidence_sha256,
        evidence_manifest=candidate.evidence_manifest,
        actor_subject=actor,
        reason="pilot authority",
        authorization_evidence={
            "authorization_policy_version": "control-plan-rbac-v1",
            "claim_policy_mode": "strict",
            "subject": actor,
            "roles": ["supervisor"],
            "token_identity_sha256": "9" * 64,
            "request_id": "req-1",
            "evidence_refs": ["ticket-118"],
        },
        occurred_at=NOW,
    )
    return grant, birth


def _revocation_builder(grant_id, reason):
    """DELIBERATELY GUARDLESS: no already-revoked check, so a lost race hits
    the one-revocation partial unique index and must surface as
    AuthorityRevocationConflictError via the IntegrityError translation —
    proving the DB backstop, not the service-level courtesy check."""
    from services.authority_grant_service import AuthorityGrantService

    def build(sequence, existing):
        return AuthorityGrantService._build_event(
            grant_id,
            sequence,
            "revoked",
            effective_expires_at=None,
            shadow_evidence_sha256=None,
            hold_drill_evidence_sha256=None,
            rollback_drill_evidence_sha256=None,
            evidence_manifest=None,
            actor_subject="supervisor-1",
            reason=reason,
            authorization_evidence={
                "claim_policy_mode": "compat",
                "subject": "supervisor-1",
            },
            occurred_at=NOW + timedelta(hours=1),
        )

    return build


async def _fresh_schema(conn):
    await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
    outcomes = dict(await migrate.apply_all_migrations(conn))
    assert outcomes["0012_authority_grants"] == "applied"


@pytest.mark.asyncio
async def test_migration_0012_apply_rollback_reapply_and_refusal():
    conn = await _connect()
    try:
        await _fresh_schema(conn)
        assert await conn.fetchval(f"SELECT count(*) FROM {GRANTS}") == 0
        # Empty tables: down applies cleanly, then reapply.
        await migrate.rollback_migration(conn, "0012_authority_grants")
        assert (
            await conn.fetchval(
                "SELECT to_regclass('scheduler.control_authority_grants')"
            )
            is None
        )
        outcomes = dict(await migrate.apply_all_migrations(conn))
        assert outcomes["0012_authority_grants"] == "applied"
        # With evidence present: down REFUSES (forward-fix doctrine).
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                PostgresControlPlanRepository,
            )

            repository = PostgresControlPlanRepository()
            hashes = await _outbox_hashes(conn, plan_id, version)
            grant, birth = _rows_for(_candidate(plan_id, version), hashes)
            async with sessions() as session:
                stored, inserted = await repository.insert_authority_grant(
                    session, grant, lambda: birth
                )
            assert inserted is True
        finally:
            await engine.dispose()
        with pytest.raises(asyncpg.exceptions.RaiseError):
            await migrate.rollback_migration(conn, "0012_authority_grants")
    finally:
        # Leave the database pristine: the alphabetically-later integration
        # files guard on finding NO pre-existing scheduler schema.
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_rollback_refuses_without_waiting_on_event_table_lock():
    conn = await _connect()
    blocker = await _connect()
    try:
        await _fresh_schema(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                PostgresControlPlanRepository,
            )

            repository = PostgresControlPlanRepository()
            hashes = await _outbox_hashes(conn, plan_id, version)
            grant, birth = _rows_for(_candidate(plan_id, version), hashes)
            async with sessions() as session:
                await repository.insert_authority_grant(session, grant, lambda: birth)
        finally:
            await engine.dispose()

        await blocker.execute("BEGIN")
        await blocker.execute(
            "LOCK TABLE scheduler.control_authority_grant_events "
            "IN ROW EXCLUSIVE MODE"
        )
        await conn.execute("SET statement_timeout = '1s'")
        with pytest.raises(asyncpg.exceptions.RaiseError):
            await migrate.rollback_migration(conn, "0012_authority_grants")
    finally:
        if not blocker.is_closed():
            await blocker.execute("ROLLBACK")
            await blocker.close()
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_authority_tables_are_immutable_and_atomic():
    conn = await _connect()
    try:
        await _fresh_schema(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                AuthorityGrantConflictError,
                PostgresControlPlanRepository,
            )

            repository = PostgresControlPlanRepository()
            candidate = _candidate(plan_id, version)
            hashes = await _outbox_hashes(conn, plan_id, version)
            grant, birth = _rows_for(candidate, hashes)
            async with sessions() as session:
                stored, inserted = await repository.insert_authority_grant(
                    session, grant, lambda: birth
                )
            assert inserted is True
            # Atomic: BOTH rows landed.
            assert await conn.fetchval(f"SELECT count(*) FROM {GRANTS}") == 1
            assert await conn.fetchval(f"SELECT count(*) FROM {EVENTS}") == 1
            # Replay: identical content returns the SAME grant, no new rows.
            replay_grant, replay_birth = _rows_for(candidate, hashes)
            async with sessions() as session:
                stored2, inserted2 = await repository.insert_authority_grant(
                    session, replay_grant, lambda: replay_birth
                )
            assert inserted2 is False
            assert stored2.grant_id == grant.grant_id
            assert await conn.fetchval(f"SELECT count(*) FROM {EVENTS}") == 1
            # One-per-plan: different content for the same plan conflicts.
            different = _candidate(plan_id, version)
            different = type(different)(
                **{
                    **different.__dict__,
                    "expires_at": NOW + timedelta(hours=6),
                }
            )
            other_grant, other_birth = _rows_for(different, hashes)
            async with sessions() as session:
                with pytest.raises(AuthorityGrantConflictError):
                    await repository.insert_authority_grant(
                        session, other_grant, lambda: other_birth
                    )
            # Immutability triggers on BOTH tables.
            for statement in (
                f"UPDATE {GRANTS} SET created_by_subject = 'x'",
                f"DELETE FROM {GRANTS}",
                f"UPDATE {EVENTS} SET reason = 'x'",
                f"DELETE FROM {EVENTS}",
            ):
                with pytest.raises(asyncpg.exceptions.RaiseError):
                    await conn.execute(statement)
            # Loading verifies integrity end-to-end on the real rows.
            async with sessions() as session:
                loaded = await repository.load_authority_grant_for_plan(
                    session, plan_id, version
                )
            assert loaded is not None
            assert loaded[0].grant_content_sha256 == grant.grant_content_sha256
            assert [event.event_type for event in loaded[1]] == ["granted"]
        finally:
            await engine.dispose()
    finally:
        # Leave the database pristine: the alphabetically-later integration
        # files guard on finding NO pre-existing scheduler schema.
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mismatched_field", "mismatched_value"),
    [
        ("correlation_id", uuid4()),
        ("request_id", "different-request"),
        ("idempotency_key", "different-idempotency-key"),
        ("intent_content_hash", "9" * 64),
        ("capability_hash", "8" * 64),
    ],
)
async def test_authority_receipt_coverage_rejects_identity_mismatches(
    mismatched_field, mismatched_value
):
    """An accepted receipt is not authority evidence unless it is bound to
    the exact plan/version, immutable intent hash, and capability hash."""
    conn = await _connect()
    try:
        await _fresh_schema(conn)
        plan_id, version, [intent_id] = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        outbox = await conn.fetchrow(
            "SELECT correlation_id, request_id, idempotency_key, "
            "intent_content_hash, capability_hash "
            "FROM scheduler.control_command_outbox WHERE intent_id = $1",
            intent_id,
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                PostgresControlPlanRepository,
                ValidationReceiptRow,
            )
            from core.canonical_json import canonicalize, sha256_hex
            from schemas.machine_boundary import ValidationReceipt

            repository = PostgresControlPlanRepository()
            receipt_id = uuid4()
            receipt_values = {
                "correlation_id": outbox["correlation_id"],
                "request_id": outbox["request_id"],
                "idempotency_key": outbox["idempotency_key"],
                "intent_content_hash": outbox["intent_content_hash"],
                "capability_hash": outbox["capability_hash"],
            }
            receipt_values[mismatched_field] = mismatched_value
            receipt_document = canonicalize(
                ValidationReceipt(
                    schema_version=1,
                    receipt_id=str(receipt_id),
                    intent_id=str(intent_id),
                    correlation_id=str(receipt_values["correlation_id"]),
                    request_id=receipt_values["request_id"],
                    idempotency_key=receipt_values["idempotency_key"],
                    intent_content_hash=receipt_values["intent_content_hash"],
                    capability_hash=receipt_values["capability_hash"],
                    status="validation_accepted",
                    reason_code=None,
                    validated_at=NOW.isoformat().replace("+00:00", "Z"),
                ).model_dump()
            )
            receipt = ValidationReceiptRow(
                intent_id=intent_id,
                plan_id=plan_id,
                plan_version=version,
                receipt_id=receipt_id,
                correlation_id=receipt_values["correlation_id"],
                request_id=receipt_values["request_id"],
                idempotency_key=receipt_values["idempotency_key"],
                intent_content_hash=receipt_values["intent_content_hash"],
                capability_hash=receipt_values["capability_hash"],
                status="validation_accepted",
                reason_code=None,
                validated_at=NOW,
                receipt_document_text=receipt_document,
                receipt_content_sha256=sha256_hex(receipt_document),
                dispatch_worker_id="test-worker",
                dispatched_at=NOW,
            )
            async with sessions() as session:
                assert await repository.record_validation_receipt(session, receipt)
            async with sessions() as session:
                counts = await repository.load_authority_evidence_counts(
                    session, plan_id, version
                )
            assert counts == type(counts)(
                outbox_intent_count=1,
                accepted_receipt_intent_count=1,
                matching_receipt_intent_count=0,
            )
        finally:
            await engine.dispose()
    finally:
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_concurrent_revocations_persist_one_terminal_event():
    conn = await _connect()
    try:
        await _fresh_schema(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                AuthorityRevocationConflictError,
                PostgresControlPlanRepository,
            )

            repository = PostgresControlPlanRepository()
            hashes = await _outbox_hashes(conn, plan_id, version)
            grant, birth = _rows_for(_candidate(plan_id, version), hashes)
            async with sessions() as session:
                await repository.insert_authority_grant(session, grant, lambda: birth)

            async def revoke(reason):
                async with sessions() as session:
                    try:
                        await repository.append_authority_grant_event(
                            session,
                            grant.grant_id,
                            _revocation_builder(grant.grant_id, reason),
                        )
                        return "revoked"
                    except AuthorityRevocationConflictError:
                        return "lost"

            outcomes = await asyncio.gather(revoke("racer-a"), revoke("racer-b"))
            assert sorted(outcomes) == ["lost", "revoked"]
            assert (
                await conn.fetchval(
                    f"SELECT count(*) FROM {EVENTS} WHERE event_type = 'revoked'"
                )
                == 1
            )
        finally:
            await engine.dispose()
    finally:
        # Leave the database pristine: the alphabetically-later integration
        # files guard on finding NO pre-existing scheduler schema.
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_grant_refused_once_the_plan_loses_shadow_active():
    """QCHECK TOCTOU backstop: the repository re-derives lifecycle state from
    control_state_transitions INSIDE the RECOVERY-locked transaction — a plan
    invalidated after (unlocked) service validation can never receive a grant."""
    conn = await _connect()
    try:
        await _fresh_schema(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        await conn.execute(
            "INSERT INTO scheduler.control_state_transitions (plan_id, plan_version, "
            "transition_sequence, transition_type, from_state, to_state, actor_subject)"
            " VALUES ($1, $2, 5, 'invalidated', 'shadow_active', 'invalidated', 'op')",
            plan_id,
            version,
        )
        engine, sessions = _sessions()
        try:
            from repositories.control_plan_repository import (
                PlanNotShadowActiveForAuthorityError,
                PostgresControlPlanRepository,
            )

            repository = PostgresControlPlanRepository()
            hashes = await _outbox_hashes(conn, plan_id, version)
            grant, birth = _rows_for(_candidate(plan_id, version), hashes)
            async with sessions() as session:
                with pytest.raises(PlanNotShadowActiveForAuthorityError):
                    await repository.insert_authority_grant(
                        session, grant, lambda: birth
                    )
            assert await conn.fetchval(f"SELECT count(*) FROM {GRANTS}") == 0
        finally:
            await engine.dispose()
    finally:
        # Leave the database pristine: the alphabetically-later integration
        # files guard on finding NO pre-existing scheduler schema.
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_grant_expiring_while_waiting_for_recovery_lock_is_not_persisted():
    """The birth clock is sampled after RECOVERY_LOCK_ID is acquired.

    Holding that lock past the requested expiry must roll back the tentative
    grant row instead of consuming the plan version's one immutable grant.
    """
    conn = await _connect()
    blocker = await _connect()
    try:
        await _fresh_schema(conn)
        plan_id, version, _ = await _seed_active_plan(
            conn, not_before=NOW, deadline=NOW + timedelta(hours=5)
        )
        from core.authority_grant import AuthorityEvidenceError
        from repositories.control_plan_repository import (
            RECOVERY_LOCK_ID,
            PostgresControlPlanRepository,
        )
        from services.authority_grant_service import AuthorityGrantService

        candidate = _candidate(plan_id, version)
        candidate = type(candidate)(
            **{
                **candidate.__dict__,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=0.5),
            }
        )
        hashes = await _outbox_hashes(conn, plan_id, version)
        grant, _ = _rows_for(candidate, hashes)

        def build_birth():
            locked_now = datetime.now(timezone.utc)
            if locked_now >= candidate.expires_at:
                raise AuthorityEvidenceError(
                    "expiry_invalid", "the authority lease expired before commit"
                )
            return AuthorityGrantService._build_event(
                grant.grant_id,
                1,
                "granted",
                effective_expires_at=candidate.expires_at,
                shadow_evidence_sha256=candidate.shadow_evidence_sha256,
                hold_drill_evidence_sha256=candidate.hold_drill_evidence_sha256,
                rollback_drill_evidence_sha256=(
                    candidate.rollback_drill_evidence_sha256
                ),
                evidence_manifest=candidate.evidence_manifest,
                actor_subject="supervisor-1",
                reason="pilot authority",
                authorization_evidence={
                    "authorization_policy_version": "control-plan-rbac-v1",
                    "claim_policy_mode": "strict",
                    "subject": "supervisor-1",
                    "roles": ["supervisor"],
                    "token_identity_sha256": "9" * 64,
                    "request_id": "req-1",
                    "evidence_refs": ["ticket-118"],
                },
                occurred_at=locked_now,
            )

        engine, sessions = _sessions()
        try:
            repository = PostgresControlPlanRepository()
            await blocker.execute("SELECT pg_advisory_lock($1)", RECOVERY_LOCK_ID)

            async def issue_grant():
                async with sessions() as session:
                    return await repository.insert_authority_grant(
                        session, grant, build_birth
                    )

            issue_task = asyncio.create_task(issue_grant())
            await asyncio.sleep(0.8)
            await blocker.execute("SELECT pg_advisory_unlock($1)", RECOVERY_LOCK_ID)
            with pytest.raises(AuthorityEvidenceError) as caught:
                await issue_task
            assert caught.value.reason == "expiry_invalid"
            assert await conn.fetchval(f"SELECT count(*) FROM {GRANTS}") == 0
            assert await conn.fetchval(f"SELECT count(*) FROM {EVENTS}") == 0
        finally:
            await engine.dispose()
    finally:
        if not blocker.is_closed():
            await blocker.execute("SELECT pg_advisory_unlock_all()")
            await blocker.close()
        await conn.execute("DROP SCHEMA IF EXISTS scheduler CASCADE")
        await conn.close()
