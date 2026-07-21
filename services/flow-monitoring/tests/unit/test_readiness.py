"""Flow-monitoring dependency-truth readiness (PR 4.4a-2).

`/health` is process liveness only; `/ready` is ready ONLY when Postgres is
healthy, a valid commandable=false engineering-prior release is loaded, the
non-commanding prediction service is initialized, BOTH prediction tables exist,
and the prediction migration checksum matches. Anything else → not ready (503).

The pure evaluators + the readiness orchestrator are unit-tested with fakes
(no real Postgres for the bare gate); the real-DB assertion is env-gated.
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

import migrations.migrate as migrate
from core.model_release import EvidenceClass
from core.readiness import (
    ReadinessResult,
    check_flow_readiness,
    evaluate_commandability_approval,
    evaluate_migrations,
    evaluate_release,
)


def _real_tracked() -> dict[str, str]:
    return {
        mid: migrate.migration_checksum(mid) for mid in migrate.discover_migration_ids()
    }


def _release(*, commandable=False, evidence=EvidenceClass.ENGINEERING_PRIOR):
    return SimpleNamespace(commandable=commandable, evidence_class=evidence)


# --- fake asyncpg pool ------------------------------------------------------
class _FakeConn:
    def __init__(self, *, tables_present, registry, applied_rows, fail=False):
        self._tables_present = tables_present
        self._registry = registry
        self._applied_rows = applied_rows
        self._fail = fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def fetchval(self, sql):
        if self._fail:
            raise OSError("connection to 10.0.0.9:5432 failed: password authentication")
        if "prediction_runs" in sql:
            return "flow_monitoring.prediction_runs" if self._tables_present else None
        if "prediction_artifacts" in sql:
            return (
                "flow_monitoring.prediction_artifacts" if self._tables_present else None
            )
        if "schema_migrations" in sql:
            return "flow_monitoring.schema_migrations" if self._registry else None
        return None

    async def fetch(self, sql):
        if self._fail:
            raise OSError("db down")
        return list(self._applied_rows)


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return self._conn


def _db_manager(
    *,
    postgres_ok=True,
    pool_conn=None,
    health_raises=False,
    health_hangs=False,
    ping_hangs=False,
):
    async def check_health():
        # Readiness must NOT call this any more (FIX 5): a hung multi-store health
        # check would otherwise stall a healthy-PG readiness. `health_hangs` proves
        # readiness never awaits it.
        if health_hangs:
            await asyncio.sleep(30)
        if health_raises:
            raise OSError("db manager unreachable")
        return {
            "postgres": postgres_ok,
            "redis": True,
            "timescale": True,
            "influxdb": True,
        }

    async def ping():
        if ping_hangs:
            await asyncio.sleep(30)
        return postgres_ok

    postgres = SimpleNamespace(
        pool=_FakePool(pool_conn) if pool_conn is not None else None,
        ping=ping,
    )
    return SimpleNamespace(check_health=check_health, postgres=postgres)


def _healthy_conn():
    return _FakeConn(
        tables_present=True,
        registry=True,
        applied_rows=[
            {"migration_id": mid, "checksum": cs} for mid, cs in _real_tracked().items()
        ],
    )


def _app(*, release=None, service=object(), approval=None):
    state = SimpleNamespace(
        hydraulic_model_release=release,
        control_prediction_service=service,
        commandability_approval=approval,
    )
    return SimpleNamespace(state=state)


# --- pure evaluators --------------------------------------------------------
class TestEvaluateRelease:
    def test_missing_release_is_missing(self):
        assert evaluate_release(None) == "missing"

    def test_valid_noncommandable_engineering_prior_is_ok(self):
        assert evaluate_release(_release()) == "ok"

    def test_commandable_release_is_rejected(self):
        assert evaluate_release(_release(commandable=True)) == "commandable"

    def test_wrong_evidence_class_is_rejected(self):
        assert evaluate_release(_release(evidence="observed")) == "wrong_evidence"


class TestEvaluateCommandabilityApproval:
    @pytest.mark.parametrize(
        ("approval", "expected"),
        [
            (None, "unconfigured"),
            ({"approval_state": "not_approved", "approval": None}, "not_approved"),
            (
                {"approval_state": "approved", "approval": {"approved_by_role": "RID"}},
                "approved",
            ),
            ({"approval_state": "approved", "approval": None}, "invalid"),
        ],
    )
    def test_reports_only_safe_bounded_status(self, approval, expected):
        assert evaluate_commandability_approval(approval) == expected


# --- readiness orchestration ------------------------------------------------
class TestCheckFlowReadiness:
    @pytest.mark.asyncio
    async def test_ready_when_release_service_tables_and_migration_all_ok(self):
        result = await check_flow_readiness(
            _app(release=_release()),
            _db_manager(pool_conn=_healthy_conn()),
        )
        assert isinstance(result, ReadinessResult)
        assert result.ready is True
        assert result.checks == {
            "database": "ok",
            "model_release": "ok",
            "commandability_approval": "unconfigured",
            "prediction_service": "ok",
            "prediction_persistence": "ok",
        }

    @pytest.mark.asyncio
    async def test_invalid_approval_state_fails_readiness_closed(self):
        result = await check_flow_readiness(
            _app(
                release=_release(),
                approval={"approval_state": "approved", "approval": None},
            ),
            _db_manager(pool_conn=_healthy_conn()),
        )

        assert result.ready is False
        assert result.checks["commandability_approval"] == "invalid"

    @pytest.mark.asyncio
    async def test_not_ready_without_a_loaded_release(self):
        result = await check_flow_readiness(
            _app(release=None),
            _db_manager(pool_conn=_healthy_conn()),
        )
        assert result.ready is False
        assert result.checks["model_release"] == "missing"

    @pytest.mark.asyncio
    async def test_not_ready_when_prediction_migration_absent(self):
        conn = _FakeConn(tables_present=False, registry=False, applied_rows=[])
        result = await check_flow_readiness(
            _app(release=_release()), _db_manager(pool_conn=conn)
        )
        assert result.ready is False
        assert result.checks["prediction_persistence"] == "not_migrated"

    @pytest.mark.asyncio
    async def test_not_ready_on_prediction_migration_checksum_drift(self):
        drifted = [
            {"migration_id": mid, "checksum": "0" * 64} for mid in _real_tracked()
        ]
        conn = _FakeConn(tables_present=True, registry=True, applied_rows=drifted)
        result = await check_flow_readiness(
            _app(release=_release()), _db_manager(pool_conn=conn)
        )
        assert result.ready is False
        assert result.checks["prediction_persistence"] == "drift"

    @pytest.mark.asyncio
    async def test_not_ready_when_prediction_service_uninitialized(self):
        result = await check_flow_readiness(
            _app(release=_release(), service=None),
            _db_manager(pool_conn=_healthy_conn()),
        )
        assert result.ready is False
        assert result.checks["prediction_service"] == "uninitialized"

    @pytest.mark.asyncio
    async def test_not_ready_when_postgres_unhealthy(self):
        result = await check_flow_readiness(
            _app(release=_release()),
            _db_manager(postgres_ok=False, pool_conn=_healthy_conn()),
        )
        assert result.ready is False
        assert result.checks["database"] == "unhealthy"
        assert result.checks["prediction_persistence"] == "unreachable"

    @pytest.mark.asyncio
    async def test_db_error_never_leaks_exception_text(self):
        conn = _FakeConn(tables_present=True, registry=True, applied_rows=[], fail=True)
        result = await check_flow_readiness(
            _app(release=_release()), _db_manager(pool_conn=conn)
        )
        assert result.ready is False
        blob = repr(result.checks)
        assert "10.0.0.9" not in blob
        assert "password" not in blob
        assert result.checks["prediction_persistence"] == "unreachable"

    # FIX 5 (MEDIUM): only PostgreSQL gates readiness. A hung InfluxDB/Timescale/
    # Redis (i.e. a hanging multi-store check_health) must NOT block a healthy-PG
    # readiness — the service pings PG directly instead.
    @pytest.mark.asyncio
    async def test_ready_when_pg_up_even_if_multistore_health_would_hang(self):
        dbm = _db_manager(pool_conn=_healthy_conn(), health_hangs=True)
        start = time.perf_counter()
        result = await check_flow_readiness(_app(release=_release()), dbm)
        elapsed = time.perf_counter() - start
        assert result.ready is True
        assert result.checks["database"] == "ok"
        # Would hang ~30s if readiness still called the multi-store check_health.
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_not_ready_when_postgres_ping_hangs_past_timeout(self):
        # The direct PG ping is itself bounded: a hung ping fails closed, fast.
        dbm = _db_manager(pool_conn=_healthy_conn(), ping_hangs=True)
        start = time.perf_counter()
        result = await check_flow_readiness(
            _app(release=_release()), dbm, postgres_probe_timeout_seconds=0.1
        )
        elapsed = time.perf_counter() - start
        assert result.ready is False
        assert result.checks["database"] == "unhealthy"
        assert result.checks["prediction_persistence"] == "unreachable"
        assert elapsed < 2.0

    # FIX 4 (MEDIUM): an unreadable tracked migration file fails closed as a safe
    # "error", never an HTTP 500 leaking the file path.
    @pytest.mark.asyncio
    async def test_unreadable_migration_file_is_error_not_500(self, monkeypatch):
        dbm = _db_manager(pool_conn=_healthy_conn())  # build before patching

        def _boom():
            raise migrate.MigrationError(
                "unknown migration '0001_prediction_persistence' "
                "(/repo/migrations/0001_prediction_persistence.up.sql missing)"
            )

        monkeypatch.setattr(migrate, "discover_migration_ids", _boom)
        result = await check_flow_readiness(_app(release=_release()), dbm)
        assert result.ready is False
        assert result.checks["prediction_persistence"] == "error"
        blob = repr(result.checks)
        assert ".up.sql" not in blob
        assert "/repo/" not in blob

    # FIX 6 (MEDIUM): an empty tracked manifest (SQL files omitted) must NOT pass
    # by comparing empty==empty.
    @pytest.mark.asyncio
    async def test_empty_migration_manifest_is_not_ready(self, monkeypatch):
        dbm = _db_manager(pool_conn=_healthy_conn())
        monkeypatch.setattr(migrate, "discover_migration_ids", lambda: [])
        result = await check_flow_readiness(_app(release=_release()), dbm)
        assert result.ready is False
        assert result.checks["prediction_persistence"] == "incomplete"


class TestHealthLivenessOnly:
    @pytest.mark.asyncio
    async def test_flow_health_is_liveness_only(self):
        from main import health_check

        body = await health_check()
        assert body["status"] == "healthy"
        assert "databases" not in body  # /health makes no dependency claim
        assert set(body) == {"status", "service", "version"}
