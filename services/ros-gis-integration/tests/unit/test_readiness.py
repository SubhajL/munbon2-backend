import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi.responses import JSONResponse

import main
from db import database_manager as database_module
from db.database_manager import DatabaseManager


def _request(manager):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(db_manager=manager))
    )


def _json_body(response: JSONResponse) -> dict:
    return json.loads(response.body)


class _Acquire:
    def __init__(self, error=None):
        self.error = error

    async def __aenter__(self):
        if self.error is not None:
            raise self.error
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def fetchval(self, query):
        return 1


class _Pool:
    def __init__(self, error=None):
        self.error = error

    def acquire(self):
        return _Acquire(self.error)


class _Redis:
    async def ping(self):
        return True


class _FailingRedis:
    async def ping(self):
        raise RuntimeError("redis://operator:secret@internal-cache.example/0")


@pytest.mark.asyncio
async def test_health_is_process_only_and_never_calls_dependencies(monkeypatch):
    dependency_check = AsyncMock(side_effect=AssertionError("must not be called"))
    monkeypatch.setattr(main.db_manager, "check_health", dependency_check)

    response = await main.health_check()

    assert response == {
        "status": "healthy",
        "service": main.settings.service_name,
        "version": main.app.version,
    }
    dependency_check.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("health", "producer_enabled"),
    [
        ({"postgres": False, "redis": True}, False),
        ({"postgres": True, "redis": False}, False),
        (
            {
                "postgres": True,
                "redis": True,
                "requirement_source_postgres": False,
            },
            True,
        ),
    ],
)
async def test_ready_returns_503_when_any_required_database_is_unhealthy(
    monkeypatch, health, producer_enabled
):
    manager = SimpleNamespace(check_health=AsyncMock(return_value=health))
    monkeypatch.setattr(main.settings, "daily_requirement_enabled", producer_enabled)

    response = await main.readiness_check(_request(manager))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    assert _json_body(response) == {
        "status": "not ready",
        "service": main.settings.service_name,
        "version": main.app.version,
        "checks": {
            name: "ok" if healthy else "unhealthy" for name, healthy in health.items()
        },
    }


@pytest.mark.asyncio
async def test_ready_returns_200_without_hardcoded_external_services():
    manager = SimpleNamespace(
        check_health=AsyncMock(return_value={"postgres": True, "redis": True})
    )

    response = await main.readiness_check(_request(manager))

    assert response == {
        "status": "ready",
        "service": main.settings.service_name,
        "version": main.app.version,
        "checks": {"postgres": "ok", "redis": "ok"},
    }
    assert "external_services" not in response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("producer_enabled", "expected"),
    [
        (False, {"postgres": True, "redis": True}),
        (
            True,
            {
                "postgres": True,
                "redis": True,
                "requirement_source_postgres": False,
            },
        ),
    ],
)
async def test_database_health_requires_source_postgres_only_when_producer_enabled(
    monkeypatch, producer_enabled, expected
):
    manager = DatabaseManager()
    manager._pg_pool = _Pool()
    manager._requirement_source_pool = _Pool(RuntimeError("source unavailable"))
    manager._redis_client = _Redis()
    monkeypatch.setattr(
        database_module.settings, "daily_requirement_enabled", producer_enabled
    )

    assert await manager.check_health() == expected


@pytest.mark.asyncio
async def test_database_health_logs_only_safe_error_types(monkeypatch):
    manager = DatabaseManager()
    manager.logger = SimpleNamespace(error=Mock())
    manager._pg_pool = _Pool(
        RuntimeError("postgresql://operator:secret@internal-db.example/munbon")
    )
    manager._requirement_source_pool = _Pool(
        RuntimeError("postgresql://source:secret@internal-source.example/munbon")
    )
    manager._redis_client = _FailingRedis()
    monkeypatch.setattr(database_module.settings, "daily_requirement_enabled", True)

    assert await manager.check_health() == {
        "postgres": False,
        "redis": False,
        "requirement_source_postgres": False,
    }
    logged = repr(manager.logger.error.call_args_list)
    assert "secret" not in logged
    assert "internal-db" not in logged
    assert "internal-source" not in logged
    assert "internal-cache" not in logged


@pytest.mark.asyncio
async def test_ready_failure_then_recovery_returns_200_without_restart():
    class _MutableManager:
        healthy = False

        async def check_health(self):
            return {"postgres": self.healthy, "redis": True}

    manager = _MutableManager()
    original_manager = main.app.state.db_manager
    main.app.state.db_manager = manager
    try:
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://ros.test"
        ) as client:
            failed = await client.get("/ready")
            manager.healthy = True
            recovered = await client.get("/ready")
    finally:
        main.app.state.db_manager = original_manager

    assert failed.status_code == 503
    assert failed.json()["status"] == "not ready"
    assert recovered.status_code == 200
    assert recovered.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_exception_fails_closed_without_url_host_or_secret_leakage():
    manager = SimpleNamespace(
        check_health=AsyncMock(
            side_effect=RuntimeError(
                "postgresql://operator:secret@internal-db.example/munbon"
            )
        )
    )

    response = await main.readiness_check(_request(manager))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    body = response.body.decode()
    assert "secret" not in body
    assert "internal-db" not in body
    assert _json_body(response) == {
        "status": "not ready",
        "service": main.settings.service_name,
        "version": main.app.version,
        "checks": {"dependencies": "unreachable"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed_health", [None, [], "internal-db-secret"])
async def test_ready_malformed_health_result_fails_closed_without_leakage(
    malformed_health,
):
    manager = SimpleNamespace(check_health=AsyncMock(return_value=malformed_health))

    response = await main.readiness_check(_request(manager))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    assert "internal-db-secret" not in response.body.decode()
    assert _json_body(response)["checks"] == {"dependencies": "unreachable"}
