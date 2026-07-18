"""Scheduler dependency-truth readiness (PR 4.4a-2).

`/ready` is fail-closed: it is ready ONLY when every tracked migration id+checksum
matches `scheduler.schema_migrations`, all six control tables exist, and the Redis
revocation store answers a ping. Any drift/missing/unreachable → not ready (503),
and the body never leaks a hostname, credential, or raw exception text.

The pure evaluators are unit-tested directly; the I/O path is driven by a fake
engine + fake redis (no real Postgres/Redis needed for the bare gate). The
real-DB assertion lives in the env-gated integration suite.
"""

import pytest

from core.readiness import (
    EXPECTED_CONTROL_TABLES,
    ReadinessResult,
    check_scheduler_readiness,
    evaluate_control_tables,
    evaluate_migrations,
)
import migrations.migrate as migrate


def _real_tracked() -> dict[str, str]:
    return {mid: migrate.migration_checksum(mid) for mid in migrate.discover_migration_ids()}


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
    def __init__(self, client):
        self.client = client


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
        assert evaluate_control_tables({t: True for t in EXPECTED_CONTROL_TABLES}) == "ok"

    def test_any_missing_is_missing(self):
        present = {t: True for t in EXPECTED_CONTROL_TABLES}
        present[EXPECTED_CONTROL_TABLES[0]] = False
        assert evaluate_control_tables(present) == "missing"

    def test_expected_tables_are_the_six_control_tables(self):
        # PR 4.4b-4 adds the campaign-identity mapping as a source-of-truth table:
        # readiness must prove it exists, or every draft read fails closed.
        assert set(EXPECTED_CONTROL_TABLES) == {
            "control_plan_runs",
            "control_plan_requirements",
            "gate_plan_events",
            "control_state_transitions",
            "section_delivery_ledger",
            "control_plan_campaign_versions",
        }


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
            _FakeConn(registry=True, present=present, applied_rows=list(tracked.items()))
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
            _FakeConn(registry=True, present=present, applied_rows=list(tracked.items()))
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
