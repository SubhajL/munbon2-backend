from datetime import date, datetime, timezone
from decimal import Decimal
import importlib
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import water_requirements
from db.water_requirement_repository import (
    get_daily_requirements,
    get_section_requirement_history,
)

UTC = timezone.utc
SERVICE_DATE = date(2026, 7, 16)
NOW = datetime(2026, 7, 16, 3, tzinfo=UTC)
RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
REQUIREMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


def _requirement_row(**overrides) -> dict:
    row = {
        "requirement_id": REQUIREMENT_ID,
        "run_id": RUN_ID,
        "version": 2,
        "service_date": SERVICE_DATE,
        "section_id": "section-1",
        "zone": 1,
        "required_net_volume_m3": Decimal("800.000000"),
        "required_gross_volume_m3": Decimal("1000.000000"),
        "delivery_window_start": datetime(2026, 7, 16, 6, tzinfo=UTC),
        "delivery_window_end": datetime(2026, 7, 16, 18, tzinfo=UTC),
        "quality": "estimated",
        "as_of_date": SERVICE_DATE,
        "published_at": datetime(2026, 7, 16, 2, 30, tzinfo=UTC),
        "run_status": "published",
    }
    row.update(overrides)
    return row


class _ReadConnection:
    def __init__(self, daily_rows=(), section_rows=()):
        self.daily_rows = list(daily_rows)
        self.section_rows = list(section_rows)
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        if "latest_run" in sql:
            return self.daily_rows
        if "requirement.section_id = $1" in sql:
            return self.section_rows
        raise AssertionError(f"unexpected query: {sql}")


def _client(conn: _ReadConnection, now: datetime = NOW) -> TestClient:
    app = FastAPI()
    app.include_router(water_requirements.router)

    async def connection_override():
        yield conn

    app.dependency_overrides[
        water_requirements.get_requirement_connection
    ] = connection_override
    app.dependency_overrides[water_requirements.get_current_time] = lambda: now
    return TestClient(app)


@pytest.mark.asyncio
async def test_get_daily_requirements_uses_latest_published_run_for_date_and_zone():
    conn = _ReadConnection(daily_rows=[_requirement_row()])

    result = await get_daily_requirements(conn, SERVICE_DATE, 1)

    assert result == [_requirement_row()]
    sql, args = conn.calls[0]
    assert "run.status IN ('published', 'superseded')" in sql
    assert "run.status = 'published'" in sql
    assert "ROW_NUMBER() OVER" in sql
    assert args == (SERVICE_DATE, 1)


@pytest.mark.asyncio
async def test_get_section_requirement_history_exposes_published_and_superseded_versions():
    rows = [
        _requirement_row(version=1, run_status="superseded"),
        _requirement_row(),
    ]
    conn = _ReadConnection(section_rows=rows)

    result = await get_section_requirement_history(
        conn, "section-1", SERVICE_DATE, SERVICE_DATE
    )

    assert result == rows
    sql, args = conn.calls[0]
    assert "run.status IN ('published', 'superseded')" in sql
    assert "requirement.section_id = $1" in sql
    assert args == ("section-1", SERVICE_DATE, SERVICE_DATE)


def test_daily_endpoint_returns_operator_contract_from_canonical_publication():
    response = _client(_ReadConnection(daily_rows=[_requirement_row()])).get(
        "/api/v1/water-requirements/daily",
        params={"service_date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 200
    assert response.json() == {
        "serviceDate": "2026-07-16",
        "zone": 1,
        "dataStatus": "published",
        "requirements": [
            {
                "requirementId": str(REQUIREMENT_ID),
                "runId": str(RUN_ID),
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


def test_daily_endpoint_returns_no_publication_instead_of_zero():
    response = _client(_ReadConnection()).get(
        "/api/v1/water-requirements/daily",
        params={"service_date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 200
    assert response.json() == {
        "serviceDate": "2026-07-16",
        "zone": 1,
        "dataStatus": "no_publication",
        "requirements": [],
    }


def test_daily_endpoint_marks_prior_operational_day_publication_stale():
    next_day = datetime(2026, 7, 17, tzinfo=UTC)
    response = _client(
        _ReadConnection(daily_rows=[_requirement_row()]), now=next_day
    ).get(
        "/api/v1/water-requirements/daily",
        params={"service_date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 200
    assert response.json()["dataStatus"] == "stale"
    assert response.json()["requirements"][0]["dataStatus"] == "stale"


@pytest.mark.parametrize(
    ("now", "expected_status"),
    [
        (datetime(2026, 7, 16, 18, 59, tzinfo=UTC), "published"),
        (datetime(2026, 7, 16, 19, tzinfo=UTC), "stale"),
    ],
)
def test_daily_endpoint_rolls_freshness_at_0200_bangkok(now, expected_status):
    response = _client(
        _ReadConnection(daily_rows=[_requirement_row()]),
        now=now,
    ).get(
        "/api/v1/water-requirements/daily",
        params={"service_date": SERVICE_DATE.isoformat(), "zone": 1},
    )

    assert response.status_code == 200
    assert response.json()["dataStatus"] == expected_status


def test_section_endpoint_returns_superseded_and_current_versions():
    superseded_id = UUID("33333333-3333-4333-8333-333333333333")
    rows = [
        _requirement_row(
            requirement_id=superseded_id,
            version=1,
            run_status="superseded",
        ),
        _requirement_row(),
    ]
    response = _client(_ReadConnection(section_rows=rows)).get(
        "/api/v1/water-requirements/sections/section-1",
        params={"from": SERVICE_DATE.isoformat(), "to": SERVICE_DATE.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dataStatus"] == "published"
    assert [item["version"] for item in body["requirements"]] == [1, 2]
    assert [item["dataStatus"] for item in body["requirements"]] == [
        "superseded",
        "published",
    ]


def test_section_endpoint_rejects_reverse_date_range():
    response = _client(_ReadConnection()).get(
        "/api/v1/water-requirements/sections/section-1",
        params={"from": "2026-07-17", "to": "2026-07-16"},
    )

    assert response.status_code == 422


def test_ros_gis_main_registers_canonical_requirement_read_routes():
    main = importlib.import_module("main")
    route_paths = {route.path for route in main.app.routes}

    assert {
        "/api/v1/water-requirements/daily",
        "/api/v1/water-requirements/sections/{section_id}",
    }.issubset(route_paths)
