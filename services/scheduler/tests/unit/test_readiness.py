"""Scheduler dependency-truth readiness (PR 4.4a-2).

`/ready` is fail-closed: it is ready ONLY when every tracked migration id+checksum
matches `scheduler.schema_migrations`, all six control tables exist, and the Redis
revocation store answers a ping. Any drift/missing/unreachable → not ready (503),
and the body never leaks a hostname, credential, or raw exception text.

The pure evaluators are unit-tested directly; the I/O path is driven by a fake
engine + fake redis (no real Postgres/Redis needed for the bare gate). The
real-DB assertion lives in the env-gated integration suite.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.readiness import (
    EXPECTED_CONTROL_TABLES,
    ReadinessResult,
    check_scheduler_readiness,
    evaluate_control_tables,
    evaluate_migrations,
    evaluate_worker_health,
)
import migrations.migrate as migrate

_NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)


def _real_tracked() -> dict[str, str]:
    return {
        mid: migrate.migration_checksum(mid) for mid in migrate.discover_migration_ids()
    }


# --- fake engine / redis ----------------------------------------------------
class _FakeResult:
    def __init__(self, *, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def first(self):
        return self._row

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, *, registry, present, applied_rows, fail=False):
        self._registry = registry
        self._present = present
        self._applied_rows = applied_rows
        self._fail = fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        if self._fail:
            raise OSError("connection to server at 10.0.0.9 failed: password auth")
        sql = str(stmt)
        if "to_regclass" in sql:
            row = ["scheduler.schema_migrations" if self._registry else None]
            for table in EXPECTED_CONTROL_TABLES:
                row.append(f"scheduler.{table}" if self._present.get(table) else None)
            return _FakeResult(row=tuple(row))
        if "FROM scheduler.schema_migrations" in sql:
            return _FakeResult(rows=list(self._applied_rows))
        return _FakeResult()


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    def connect(self):
        return self._conn


class _FakeRedisClient:
    def __init__(self, *, pong=True, fail=False):
        self._pong = pong
        self._fail = fail

    async def ping(self):
        if self._fail:
            raise ConnectionError("redis at 10.0.0.9:6379 refused connection")
        return self._pong


class _FakeRedis:
    def __init__(self, client, heartbeat=None):
        self.client = client
        self._heartbeat = heartbeat

    async def get(self, key):
        return self._heartbeat


def _healthy_engine():
    tracked = _real_tracked()
    return _FakeEngine(
        _FakeConn(
            registry=True,
            present={t: True for t in EXPECTED_CONTROL_TABLES},
            applied_rows=list(tracked.items()),
        )
    )


# --- pure evaluators --------------------------------------------------------
class TestEvaluateMigrations:
    def test_exact_match_is_ok(self):
        tracked = {"0001_a": "aa", "0002_b": "bb"}
        assert evaluate_migrations(tracked, dict(tracked)) == "ok"

    def test_missing_tracked_migration_is_missing(self):
        tracked = {"0001_a": "aa", "0002_b": "bb"}
        assert evaluate_migrations(tracked, {"0001_a": "aa"}) == "missing"

    def test_checksum_mismatch_is_drift(self):
        tracked = {"0001_a": "aa"}
        assert evaluate_migrations(tracked, {"0001_a": "DIFFERENT"}) == "drift"

    def test_extra_applied_migration_is_drift(self):
        tracked = {"0001_a": "aa"}
        assert evaluate_migrations(tracked, {"0001_a": "aa", "0009_x": "xx"}) == "drift"


class TestEvaluateControlTables:
    def test_all_present_is_ok(self):
        assert (
            evaluate_control_tables({t: True for t in EXPECTED_CONTROL_TABLES}) == "ok"
        )

    def test_any_missing_is_missing(self):
        present = {t: True for t in EXPECTED_CONTROL_TABLES}
        present[EXPECTED_CONTROL_TABLES[0]] = False
        assert evaluate_control_tables(present) == "missing"

    def test_expected_tables_are_every_migration_owned_control_table(self):
        # PR 7.1a: readiness proves EVERY migration-owned table (0001-0012) —
        # a dropped execution/receipt/readback/authority ledger must not leave
        # /ready green while the control plane is broken.
        assert set(EXPECTED_CONTROL_TABLES) == {
            "control_plan_runs",
            "control_plan_requirements",
            "gate_plan_events",
            "control_state_transitions",
            "section_delivery_ledger",
            "control_plan_campaign_versions",
            "control_command_outbox",
            "control_active_gate_authority",
            "control_command_execution_events",
            "control_command_validation_receipts",
            "control_gate_readback_observations",
            "control_authority_grants",
            "control_authority_grant_events",
            "control_command_execution_receipts",
        }

    def test_required_baseline_contains_every_migration_through_0013(self):
        # A partially packaged deployment (SQL pairs missing) must fail closed.
        from core.readiness import REQUIRED_BASELINE_MIGRATION_IDS

        assert REQUIRED_BASELINE_MIGRATION_IDS == frozenset(
            {
                "0001_control_plan_drafts",
                "0002_predicted_delivery_ledger",
                "0003_control_plan_review_lifecycle",
                "0004_control_plan_list_indexes",
                "0005_control_plan_provenance_v2",
                "0006_control_plan_campaign_identity",
                "0007_control_plan_shadow_activation",
                "0008_control_plan_active_supersede",
                "0009_open_loop_execution",
                "0010_shadow_dispatch_receipts",
                "0011_gate_readback_observations",
                "0012_authority_grants",
                "0013_operator_approved_execution",
            }
        )


# --- I/O path (fake engine + redis) -----------------------------------------
class TestCheckSchedulerReadiness:
    @pytest.mark.asyncio
    async def test_ready_when_migrations_tables_and_redis_all_ok(self):
        result = await check_scheduler_readiness(
            _healthy_engine(), _FakeRedis(_FakeRedisClient(pong=True))
        )
        assert isinstance(result, ReadinessResult)
        assert result.ready is True
        assert result.checks == {
            "migrations": "ok",
            "control_tables": "ok",
            "redis": "ok",
        }

    @pytest.mark.asyncio
    async def test_ready_rejects_checksum_drift(self):
        tracked = _real_tracked()
        drifted = list(tracked.items())
        drifted[0] = (drifted[0][0], "0" * 64)  # corrupt one applied checksum
        engine = _FakeEngine(
            _FakeConn(
                registry=True,
                present={t: True for t in EXPECTED_CONTROL_TABLES},
                applied_rows=drifted,
            )
        )
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["migrations"] == "drift"

    @pytest.mark.asyncio
    async def test_ready_rejects_missing_control_table(self):
        tracked = _real_tracked()
        present = {t: True for t in EXPECTED_CONTROL_TABLES}
        present["section_delivery_ledger"] = False
        engine = _FakeEngine(
            _FakeConn(
                registry=True, present=present, applied_rows=list(tracked.items())
            )
        )
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["control_tables"] == "missing"

    @pytest.mark.asyncio
    async def test_ready_rejects_missing_campaign_versions_table(self):
        # PR 4.4b-4: the campaign-identity mapping is a source-of-truth table.
        # If 0006's table is absent, readiness must report control_tables missing.
        tracked = _real_tracked()
        present = {t: True for t in EXPECTED_CONTROL_TABLES}
        present["control_plan_campaign_versions"] = False
        engine = _FakeEngine(
            _FakeConn(
                registry=True, present=present, applied_rows=list(tracked.items())
            )
        )
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["control_tables"] == "missing"

    @pytest.mark.asyncio
    async def test_ready_rejects_unmigrated_registry(self):
        engine = _FakeEngine(
            _FakeConn(
                registry=False,
                present={t: False for t in EXPECTED_CONTROL_TABLES},
                applied_rows=[],
            )
        )
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["migrations"] == "missing"

    @pytest.mark.asyncio
    async def test_not_ready_when_redis_unreachable(self):
        result = await check_scheduler_readiness(
            _healthy_engine(), _FakeRedis(_FakeRedisClient(fail=True))
        )
        assert result.ready is False
        assert result.checks["redis"] == "unreachable"

    @pytest.mark.asyncio
    async def test_not_ready_when_redis_client_absent(self):
        result = await check_scheduler_readiness(_healthy_engine(), _FakeRedis(None))
        assert result.ready is False
        assert result.checks["redis"] == "unreachable"

    @pytest.mark.asyncio
    async def test_database_unreachable_never_leaks_exception_text(self):
        engine = _FakeEngine(
            _FakeConn(registry=True, present={}, applied_rows=[], fail=True)
        )
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        # No hostname / credential / raw-exception leak in the body.
        blob = repr(result.checks)
        assert "10.0.0.9" not in blob
        assert "password" not in blob
        assert result.checks == {"database": "unreachable"}

    # FIX 4 (MEDIUM): computing the tracked-migration checksums can raise (a
    # missing/unreadable SQL file). That must fail closed as a safe not-ready
    # "error" — never propagate to an HTTP 500 leaking the file path.
    @pytest.mark.asyncio
    async def test_unreadable_migration_file_is_error_not_500(self, monkeypatch):
        engine = _healthy_engine()  # capture real applied rows before patching

        def _boom():
            raise migrate.MigrationError(
                "unknown migration '0001_control_plan_drafts' "
                "(/repo/migrations/0001_control_plan_drafts.up.sql missing)"
            )

        monkeypatch.setattr(migrate, "discover_migration_ids", _boom)
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["migrations"] == "error"
        # The raised file path / message must not leak into the body.
        blob = repr(result.checks)
        assert ".up.sql" not in blob
        assert "/repo/" not in blob

    # FIX 6 (MEDIUM): an empty tracked manifest (SQL files omitted from the
    # deployment) must NOT pass by comparing empty==empty.
    @pytest.mark.asyncio
    async def test_empty_migration_manifest_is_not_ready(self, monkeypatch):
        engine = _healthy_engine()
        monkeypatch.setattr(migrate, "discover_migration_ids", lambda: [])
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["migrations"] == "incomplete"

    @pytest.mark.asyncio
    async def test_baseline_missing_manifest_is_not_ready(self, monkeypatch):
        # A partial package that has 0001/0002 but is missing the 0003 baseline id
        # is caught as "incomplete" (subset check), not silently accepted.
        engine = _healthy_engine()
        monkeypatch.setattr(
            migrate,
            "discover_migration_ids",
            lambda: ["0001_control_plan_drafts", "0002_predicted_delivery_ledger"],
        )
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["migrations"] == "incomplete"

    @pytest.mark.asyncio
    async def test_baseline_missing_0006_is_not_ready(self, monkeypatch):
        # PR 4.4b-4: a manifest that carries 0001-0005 but DROPPED the 0006
        # campaign-identity migration is "incomplete" — 0006 is a required baseline
        # id, so an otherwise-complete package missing only 0006 still fails closed.
        engine = _healthy_engine()
        monkeypatch.setattr(
            migrate,
            "discover_migration_ids",
            lambda: [
                "0001_control_plan_drafts",
                "0002_predicted_delivery_ledger",
                "0003_control_plan_review_lifecycle",
                "0004_control_plan_list_indexes",
                "0005_control_plan_provenance_v2",
            ],
        )
        result = await check_scheduler_readiness(engine, _FakeRedis(_FakeRedisClient()))
        assert result.ready is False
        assert result.checks["migrations"] == "incomplete"


class TestEvaluateWorkerHealth:
    def test_disabled_when_not_armed(self):
        # Dark-by-default: an absent heartbeat is irrelevant when the worker isn't armed.
        assert evaluate_worker_health(False, None, _NOW, 180) == "disabled"

    def test_missing_when_armed_and_no_heartbeat(self):
        assert evaluate_worker_health(True, None, _NOW, 180) == "missing"

    def test_stale_when_beat_older_than_threshold(self):
        old = (_NOW - timedelta(seconds=200)).isoformat()
        assert evaluate_worker_health(True, old, _NOW, 180) == "stale"

    def test_ok_when_beat_within_threshold(self):
        fresh = (_NOW - timedelta(seconds=10)).isoformat()
        assert evaluate_worker_health(True, fresh, _NOW, 180) == "ok"

    def test_error_when_beat_is_unparseable(self):
        assert evaluate_worker_health(True, "not-a-timestamp", _NOW, 180) == "error"


class TestReadinessWorkerGate:
    @pytest.mark.asyncio
    async def test_operator_approved_mode_arms_the_shared_dispatch_heartbeat(
        self, monkeypatch
    ):
        import core.config

        monkeypatch.setattr(
            core.config,
            "settings",
            SimpleNamespace(
                control_execution_mode="operator_approved_open_loop",
                scheduler_scada_base_url="http://scada.local",
                scheduler_service_jwt_secret="dedicated-secret",
                control_worker_heartbeat_stale_seconds=180,
                control_worker_health_gates_readiness=False,
            ),
        )
        fresh = (_NOW - timedelta(seconds=5)).isoformat()

        result = await check_scheduler_readiness(
            _healthy_engine(),
            _FakeRedis(_FakeRedisClient(pong=True), heartbeat=fresh),
            now=_NOW,
        )

        assert result.checks["dispatch_worker"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness_fails_when_migration_or_worker_unhealthy(self):
        # With the OPT-IN gate enabled (separate dispatch/read deployments), armed + a stale
        # heartbeat → not ready, even though migrations/tables/redis are OK.
        old = (_NOW - timedelta(seconds=500)).isoformat()
        result = await check_scheduler_readiness(
            _healthy_engine(),
            _FakeRedis(_FakeRedisClient(pong=True), heartbeat=old),
            worker_armed=True,
            heartbeat_stale_seconds=180,
            worker_health_gates_readiness=True,
            now=_NOW,
        )
        assert result.ready is False
        assert result.checks["dispatch_worker"] == "stale"

    @pytest.mark.asyncio
    async def test_stale_worker_is_reported_but_does_NOT_block_reads_by_default(self):
        # DEFAULT (gate off): a stale heartbeat is REPORTED for visibility/alerting but must NOT
        # flip the LB-facing ready bool — a dead out-of-process tick can never black out the
        # read-only dashboard. This is the reviewers' required blast-radius behavior.
        old = (_NOW - timedelta(seconds=500)).isoformat()
        result = await check_scheduler_readiness(
            _healthy_engine(),
            _FakeRedis(_FakeRedisClient(pong=True), heartbeat=old),
            worker_armed=True,
            heartbeat_stale_seconds=180,
            worker_health_gates_readiness=False,
            now=_NOW,
        )
        assert result.ready is True  # reads still served
        assert (
            result.checks["dispatch_worker"] == "stale"
        )  # but the staleness is visible

    @pytest.mark.asyncio
    async def test_gated_readiness_fails_when_armed_and_worker_heartbeat_missing(self):
        result = await check_scheduler_readiness(
            _healthy_engine(),
            _FakeRedis(_FakeRedisClient(pong=True), heartbeat=None),
            worker_armed=True,
            heartbeat_stale_seconds=180,
            worker_health_gates_readiness=True,
            now=_NOW,
        )
        assert result.ready is False
        assert result.checks["dispatch_worker"] == "missing"

    @pytest.mark.asyncio
    async def test_readiness_ignores_worker_when_execution_disabled(self):
        # NOT armed: a stale/absent heartbeat must NOT make the service not-ready, and the
        # worker must not even appear in the checks (blast-radius isolation).
        result = await check_scheduler_readiness(
            _healthy_engine(),
            _FakeRedis(_FakeRedisClient(pong=True), heartbeat=None),
            worker_armed=False,
            heartbeat_stale_seconds=180,
            worker_health_gates_readiness=True,  # even with the gate on, disarmed = invisible
            now=_NOW,
        )
        assert result.ready is True
        assert "dispatch_worker" not in result.checks

    @pytest.mark.asyncio
    async def test_readiness_ok_when_armed_and_worker_fresh(self):
        fresh = (_NOW - timedelta(seconds=5)).isoformat()
        result = await check_scheduler_readiness(
            _healthy_engine(),
            _FakeRedis(_FakeRedisClient(pong=True), heartbeat=fresh),
            worker_armed=True,
            heartbeat_stale_seconds=180,
            worker_health_gates_readiness=True,
            now=_NOW,
        )
        assert result.ready is True
        assert result.checks["dispatch_worker"] == "ok"


class TestHealthLivenessOnly:
    @pytest.mark.asyncio
    async def test_health_endpoint_makes_only_liveness_claims(self):
        # /health is process liveness ONLY: it must never assert dependency health.
        from main import health_check

        body = await health_check()
        assert body["status"] == "healthy"
        assert set(body) == {"status", "service", "version"}
        assert "database" not in body
        assert "redis" not in body
