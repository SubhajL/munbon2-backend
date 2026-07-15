from datetime import date
import importlib

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import water_demand
from clients.water_requirement_client import (
    WaterRequirementClient,
    WaterRequirementClientError,
)

SERVICE_DATE = date(2026, 7, 16)


def _daily_payload() -> dict:
    return {
        "serviceDate": "2026-07-16",
        "zone": 1,
        "dataStatus": "published",
        "requirements": [
            {
                "requirementId": "22222222-2222-4222-8222-222222222222",
                "runId": "11111111-1111-4111-8111-111111111111",
                "version": 2,
                "serviceDate": "2026-07-16",
                "sectionId": "section-1",
                "zone": 1,
                "requiredVolumeM3": 800.0,
                "deliveryWindow": {
                    "start": "2026-07-16T06:00:00Z",
                    "end": "2026-07-16T18:00:00Z",
                },
                "quality": "estimated",
                "publishedAt": "2026-07-16T02:30:00Z",
                "freshness": {
                    "asOfDate": "2026-07-16",
                    "publishedAgeSeconds": 1800,
                },
                "dataStatus": "published",
            }
        ],
    }


class _RequirementClient:
    def __init__(self, *, failure: Exception | None = None):
        self.failure = failure
        self.calls = []

    async def get_daily_requirements(self, service_date: date, zone: int) -> dict:
        self.calls.append(("daily", service_date, zone))
        if self.failure is not None:
            raise self.failure
        return _daily_payload()

    async def get_section_requirement_history(
        self,
        section_id: str,
        from_date: date,
        to_date: date,
    ) -> dict:
        self.calls.append(("section", section_id, from_date, to_date))
        if self.failure is not None:
            raise self.failure
        return {
            "sectionId": section_id,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "dataStatus": "published",
            "requirements": _daily_payload()["requirements"],
        }


def _client(requirement_client: _RequirementClient) -> TestClient:
    app = FastAPI()
    app.include_router(water_demand.router)
    app.dependency_overrides[
        water_demand.get_water_requirement_client
    ] = lambda: requirement_client
    return TestClient(app)


def test_bff_daily_endpoint_preserves_canonical_fe_contract():
    requirement_client = _RequirementClient()

    response = _client(requirement_client).get(
        "/api/v1/water-demand/daily",
        params={"date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 200
    assert response.json() == _daily_payload()
    assert requirement_client.calls == [("daily", SERVICE_DATE, 1)]


def test_bff_returns_no_publication_instead_of_zero():
    requirement_client = _RequirementClient()
    payload = {
        "serviceDate": SERVICE_DATE.isoformat(),
        "zone": 1,
        "dataStatus": "no_publication",
        "requirements": [],
    }

    async def no_publication(*_):
        return payload

    requirement_client.get_daily_requirements = no_publication
    response = _client(requirement_client).get(
        "/api/v1/water-demand/daily",
        params={"date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 200
    assert response.json() == payload
    assert "requiredVolumeM3" not in response.text


def test_bff_section_daily_endpoint_reads_canonical_version_history():
    requirement_client = _RequirementClient()

    response = _client(requirement_client).get(
        "/api/v1/water-demand/sections/section-1/daily",
        params={"date": SERVICE_DATE.isoformat()},
    )

    assert response.status_code == 200
    assert response.json()["requirements"][0]["version"] == 2
    assert requirement_client.calls == [
        ("section", "section-1", SERVICE_DATE, SERVICE_DATE)
    ]


def test_bff_maps_canonical_service_failure_to_503_without_legacy_fallback():
    requirement_client = _RequirementClient(
        failure=WaterRequirementClientError("canonical service unavailable")
    )

    response = _client(requirement_client).get(
        "/api/v1/water-demand/daily",
        params={"date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Canonical water requirements unavailable"}


def test_bff_rejects_malformed_canonical_contract_without_legacy_fallback():
    requirement_client = _RequirementClient()

    async def malformed(*_):
        return {"dataStatus": "published", "requirements": []}

    requirement_client.get_daily_requirements = malformed
    response = _client(requirement_client).get(
        "/api/v1/water-demand/daily",
        params={"date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Invalid canonical water requirement response"}


def test_mutable_daily_demand_query_remains_only_on_deprecated_legacy_path():
    app = FastAPI()
    app.include_router(water_demand.router)
    openapi = app.openapi()

    assert (
        openapi["paths"]["/api/v1/water-demand/legacy/sections/{section_id}/daily"][
            "get"
        ]["deprecated"]
        is True
    )
    assert "/api/v1/water-demand/sections/{section_id}/daily" in openapi["paths"]


def test_bff_main_registers_canonical_daily_and_section_routes():
    main = importlib.import_module("main")
    route_paths = {route.path for route in main.app.routes}

    assert {
        "/api/v1/water-demand/daily",
        "/api/v1/water-demand/sections/{section_id}/daily",
        "/api/v1/water-demand/legacy/sections/{section_id}/daily",
    }.issubset(route_paths)


@pytest.mark.asyncio
async def test_water_requirement_client_calls_ros_gis_canonical_read_paths(monkeypatch):
    calls = []

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return _daily_payload()

    class _AsyncClient:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, params):
            calls.append(("get", url, params))
            return _Response()

    monkeypatch.setattr(httpx, "AsyncClient", _AsyncClient)
    client = WaterRequirementClient(base_url="http://ros-gis.test")

    result = await client.get_daily_requirements(SERVICE_DATE, 1)
    await client.get_section_requirement_history(
        "section 1",
        SERVICE_DATE,
        SERVICE_DATE,
    )

    assert result == _daily_payload()
    assert calls[1] == (
        "get",
        "http://ros-gis.test/api/v1/water-requirements/daily",
        {"service_date": "2026-07-16", "zone": 1},
    )
    assert calls[3] == (
        "get",
        "http://ros-gis.test/api/v1/water-requirements/sections/section%201",
        {"from": "2026-07-16", "to": "2026-07-16"},
    )
