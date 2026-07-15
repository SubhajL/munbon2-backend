from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from db.daily_requirement_run_store import PostgresDailyRequirementRunStore
from services.daily_requirement_producer import (
    CalculatedRequirement,
    RequirementBatch,
    RequirementContribution,
    RequirementSnapshot,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 16, 2, tzinfo=UTC)


class _Connection:
    def __init__(self):
        self.executions = []

    async def execute(self, sql, *args):
        self.executions.append((sql, args))


class _DatabaseManager:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def get_connection(self):
        yield self.conn


@pytest.mark.asyncio
async def test_locked_connection_holds_and_releases_postgres_advisory_lock():
    conn = _Connection()
    store = PostgresDailyRequirementRunStore(_DatabaseManager(conn))

    async with store.locked_connection() as yielded:
        assert yielded is conn
        assert "pg_advisory_lock" in conn.executions[0][0]

    assert "pg_advisory_unlock" in conn.executions[-1][0]
    assert conn.executions[0][1] == conn.executions[-1][1]


@pytest.mark.asyncio
async def test_store_adapts_calculated_dataclasses_to_publication_repository(
    monkeypatch,
):
    calls = []

    async def start_requirement_run(conn, **kwargs):
        calls.append(("start", conn, kwargs))
        return {"run_id": "run-1"}

    async def publish_requirement_run(
        conn, run_id, requirements, contributions, *, published_at
    ):
        calls.append(
            (
                "publish",
                conn,
                run_id,
                requirements,
                contributions,
                published_at,
            )
        )

    monkeypatch.setattr(
        "db.daily_requirement_run_store.start_requirement_run", start_requirement_run
    )
    monkeypatch.setattr(
        "db.daily_requirement_run_store.publish_requirement_run",
        publish_requirement_run,
    )
    snapshot = RequirementSnapshot(
        sections=(),
        eto_monthly_mm={},
        kc_weekly={},
        effective_rainfall_monthly_mm={},
        section_dataset_version_id=11,
        gate_mapping_dataset_version_id=12,
        crop_register_version="crop-v1",
        weather_version="weather-v1",
        annual_plan_version="annual-v1",
        input_cutoff_at=NOW,
    )
    requirement = CalculatedRequirement(
        requirement_id=uuid4(),
        service_date=date(2026, 7, 16),
        zone=1,
        section_id="01-01-01-03",
        required_net_volume_m3=Decimal("1.000000"),
        required_gross_volume_m3=Decimal("2.000000"),
        delivery_window_start=NOW,
        delivery_window_end=datetime(2026, 7, 17, 2, tzinfo=UTC),
        quality="estimated",
        input_versions={"crop": "v1"},
        content_hash="a" * 64,
    )
    contribution = RequirementContribution(
        requirement_id=requirement.requirement_id,
        area_id=requirement.section_id,
        area_rai=Decimal("1.000000"),
        crop_type="rice",
        crop_stage="seedling",
        net_volume_m3=Decimal("1.000000"),
        source_payload_hash="b" * 64,
    )
    batch = RequirementBatch("c" * 64, (requirement,), (contribution,))
    store = PostgresDailyRequirementRunStore(None)

    run = await store.start(
        "conn",
        snapshot,
        date(2026, 7, 16),
        date(2026, 7, 22),
        "c" * 64,
        NOW,
    )
    await store.publish("conn", run, batch, NOW)

    assert calls[0][2] == {
        "as_of_date": date(2026, 7, 16),
        "horizon_start": date(2026, 7, 16),
        "horizon_end": date(2026, 7, 22),
        "input_cutoff_at": NOW,
        "section_dataset_version_id": 11,
        "gate_mapping_dataset_version_id": 12,
        "crop_register_version": "crop-v1",
        "weather_version": "weather-v1",
        "method_version": "daily-requirement-v1",
        "content_hash": "c" * 64,
        "computed_at": NOW,
    }
    assert calls[1][3] == [requirement.__dict__]
    assert calls[1][4] == [contribution.__dict__]


@pytest.mark.asyncio
async def test_find_published_fails_abandoned_calculation_before_retry(monkeypatch):
    failed = []
    run_id = uuid4()

    class _LookupConnection:
        def __init__(self):
            self.call = None

        async def fetchrow(self, sql, *args):
            self.call = (sql, args)
            return {
                "run_id": run_id,
                "as_of_date": date(2026, 7, 16),
                "content_hash": "a" * 64,
                "status": "calculating",
            }

    async def fail_requirement_run(conn, failed_run_id, reason):
        failed.append((failed_run_id, reason))

    monkeypatch.setattr(
        "db.daily_requirement_run_store.fail_requirement_run", fail_requirement_run
    )

    conn = _LookupConnection()
    result = await PostgresDailyRequirementRunStore(None).find_published(
        conn, date(2026, 7, 16), "a" * 64
    )

    assert result is None
    assert failed == [(run_id, "recovered abandoned daily requirement calculation")]


@pytest.mark.asyncio
async def test_find_published_reuses_superseded_run_for_historical_transport_retry():
    run_id = uuid4()

    class _LookupConnection:
        def __init__(self):
            self.call = None

        async def fetchrow(self, sql, *args):
            self.call = (sql, args)
            return {
                "run_id": run_id,
                "as_of_date": date(2026, 7, 16),
                "content_hash": "a" * 64,
                "status": "superseded",
            }

    conn = _LookupConnection()
    result = await PostgresDailyRequirementRunStore(None).find_published(
        conn, date(2026, 7, 16), "a" * 64
    )

    assert result == {
        "run_id": run_id,
        "as_of_date": date(2026, 7, 16),
        "content_hash": "a" * 64,
        "status": "superseded",
    }
    assert "'superseded'" in conn.call[0]
