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
MANUAL_RUN_TOKEN = "local-internal-trigger-value"


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


class _ManualJob:
    def __init__(self):
        self.calls = []

    async def run_once(self, as_of_date):
        self.calls.append(as_of_date)
        return type(
            "Result",
            (),
            {
                "status": "published",
                "run_id": RUN_ID,
                "as_of_date": as_of_date,
                "requirement_count": 287,
            },
        )()


class _FailingJob:
    def __init__(self, error: Exception):
        self.error = error

    async def run_once(self, as_of_date):
        raise self.error


def _manual_run_client(job) -> TestClient:
    app = FastAPI()
    app.state.daily_requirement_manual_token = MANUAL_RUN_TOKEN
    app.include_router(water_requirements.router)
    app.dependency_overrides[water_requirements.get_daily_requirement_job] = lambda: job
    return TestClient(app, raise_server_exceptions=False)


def _post_manual_run(client: TestClient, *, token: str = MANUAL_RUN_TOKEN):
    return client.post(
        "/api/v1/water-requirements/runs",
        json={"asOfDate": "2026-07-16"},
        headers={"X-Munbon-Internal-Token": token},
    )


def test_manual_run_rejects_missing_or_invalid_internal_trigger_token():
    job = _ManualJob()
    client = _manual_run_client(job)

    assert [
        client.post(
            "/api/v1/water-requirements/runs",
            json={"asOfDate": "2026-07-16"},
        ).status_code,
        _post_manual_run(client, token="wrong-trigger-value").status_code,
    ] == [403, 403]
    assert job.calls == []


def test_manual_run_returns_explicit_incomplete_input_response():
    from services.requirement_source_loader import RequirementSourceError

    reason = "section 01-01-01-03 has no planting date for 2026-07-16"
    response = _post_manual_run(
        _manual_run_client(_FailingJob(RequirementSourceError(reason)))
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "status": "failed_incomplete_source",
            "reason": reason,
            "asOfDate": "2026-07-16",
        }
    }


def test_manual_run_does_not_reclassify_unexpected_value_error():
    response = _post_manual_run(
        _manual_run_client(_FailingJob(ValueError("negative volume")))
    )

    assert response.status_code == 500


def test_manual_run_openapi_documents_requirement_source_error():
    app = FastAPI()
    app.include_router(water_requirements.router)

    responses = app.openapi()["paths"]["/api/v1/water-requirements/runs"]["post"][
        "responses"
    ]

    assert "409" in responses


def test_manual_run_endpoint_calls_the_registered_daily_requirement_job():
    conn = _ReadConnection()
    job = _ManualJob()
    app = FastAPI()
    app.include_router(water_requirements.router)

    async def connection_override():
        yield conn

    app.dependency_overrides[
        water_requirements.get_requirement_connection
    ] = connection_override
    app.dependency_overrides[water_requirements.get_daily_requirement_job] = lambda: job

    app.state.daily_requirement_manual_token = MANUAL_RUN_TOKEN
    response = _post_manual_run(TestClient(app))

    assert response.status_code == 200
    assert response.json() == {
        "status": "published",
        "runId": str(RUN_ID),
        "asOfDate": "2026-07-16",
        "requirementCount": 287,
    }
    assert job.calls == [SERVICE_DATE]


class _CropSettingConnection:
    def __init__(self, area_rai=Decimal("953")):
        self.area_rai = area_rai
        self.insert = None

    async def fetchrow(self, sql, *args):
        if "sections_current" in sql:
            return {"area_rai": self.area_rai}
        if "INSERT INTO ros_gis.section_crop_settings" in sql:
            self.insert = (sql, args)
            return {
                "setting_id": args[0],
                "section_id": args[1],
                "crop_type": args[2],
                "planted_area_rai": args[3],
                "expected_harvest_date": args[4],
                "source": args[5],
                "as_of_date": args[6],
                "updated_by": args[7],
            }
        raise AssertionError(f"unexpected query: {sql}")


def _crop_client(conn):
    app = FastAPI()
    app.include_router(water_requirements.router)

    async def connection_override():
        yield conn

    app.dependency_overrides[
        water_requirements.get_requirement_connection
    ] = connection_override
    return TestClient(app)


def test_crop_setting_endpoint_appends_fe_configuration_linked_to_d1_section():
    conn = _CropSettingConnection()
    response = _crop_client(conn).post(
        "/api/v1/water-requirements/crop-settings/01-01-01-03",
        json={
            "cropType": "rice",
            "plantedAreaRai": "900",
            "expectedHarvestDate": "2026-11-01",
            "source": "operator-fe",
            "asOfDate": "2026-07-16",
            "updatedBy": "rid-operator",
        },
    )

    assert response.status_code == 200
    assert response.json() | {"settingId": "ignored"} == {
        "settingId": "ignored",
        "sectionId": "01-01-01-03",
        "cropType": "rice",
        "plantedAreaRai": "900",
        "expectedHarvestDate": "2026-11-01",
        "source": "operator-fe",
        "asOfDate": "2026-07-16",
        "updatedBy": "rid-operator",
    }
    assert conn.insert is not None


def test_crop_setting_endpoint_rejects_area_above_authoritative_gis_section():
    response = _crop_client(_CropSettingConnection()).post(
        "/api/v1/water-requirements/crop-settings/01-01-01-03",
        json={
            "cropType": "rice",
            "plantedAreaRai": "954",
            "expectedHarvestDate": "2026-11-01",
            "source": "operator-fe",
            "asOfDate": "2026-07-16",
            "updatedBy": "rid-operator",
        },
    )

    assert response.status_code == 422
    assert "953" in response.json()["detail"]


@pytest.mark.parametrize("field", ["cropType", "source", "updatedBy"])
def test_crop_setting_endpoint_rejects_whitespace_only_provenance(field):
    payload = {
        "cropType": "rice",
        "plantedAreaRai": "900",
        "expectedHarvestDate": "2026-11-01",
        "source": "operator-fe",
        "asOfDate": "2026-07-16",
        "updatedBy": "rid-operator",
    }
    payload[field] = "   "

    response = _crop_client(_CropSettingConnection()).post(
        "/api/v1/water-requirements/crop-settings/01-01-01-03",
        json=payload,
    )

    assert response.status_code == 422


def test_ros_gis_main_registers_canonical_requirement_read_routes():
    main = importlib.import_module("main")
    route_paths = {route.path for route in main.app.routes}

    assert {
        "/api/v1/water-requirements/runs",
        "/api/v1/water-requirements/crop-settings/{section_id}",
        "/api/v1/water-requirements/daily",
        "/api/v1/water-requirements/sections/{section_id}",
    }.issubset(route_paths)
