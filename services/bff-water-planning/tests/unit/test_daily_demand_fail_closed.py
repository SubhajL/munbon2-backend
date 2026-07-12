"""Wave 2.6b: demand inputs must never be fabricated on dependency failure.

This is the WIRED copy of the defect the adversarial review flagged in
ros-gis-integration (WAVE_2-4_PLAN §1.5 finding #10): `_get_active_plots`
caught ANY database error and silently returned `_get_mock_plots()` —
synthetic plots that the daily_demand_scheduler would compute and store as
real demand output. The same review also proved the "real" path could never
run: DatabaseManager exposed no `get_connection` at all, so every call raised
AttributeError straight into the fabricating except.
"""

from contextlib import asynccontextmanager

import asyncpg
import pytest

from config import settings
from db.database_manager import DatabaseManager
from services.daily_demand_calculator import DailyDemandCalculator


class FailingConnectDB:
    def __init__(self, exc: Exception):
        self._exc = exc

    @asynccontextmanager
    async def get_connection(self):
        raise self._exc
        yield  # pragma: no cover


class _FailingFetchConnection:
    def __init__(self, exc: Exception):
        self._exc = exc

    async def fetch(self, query, *params):
        raise self._exc


class FailingFetchDB:
    def __init__(self, exc: Exception):
        self._conn = _FailingFetchConnection(exc)

    @asynccontextmanager
    async def get_connection(self):
        yield self._conn


class _RecordingConnection:
    def __init__(self):
        self.queries = []

    async def fetch(self, query, *params):
        self.queries.append((query, params))
        return []


class RecordingDB:
    def __init__(self):
        self.conn = _RecordingConnection()

    @asynccontextmanager
    async def get_connection(self):
        yield self.conn


class MustNotConnectDB:
    def get_connection(self):
        raise AssertionError("mock profile must not touch the database")


def test_fakes_mirror_the_real_database_interface():
    assert callable(getattr(DatabaseManager, "get_connection", None)), (
        "DatabaseManager.get_connection is missing - the real-mode plots path "
        "cannot run and these fakes test an interface production does not have"
    )


DB_FAILURES = [
    RuntimeError("db down"),
    asyncpg.PostgresError("db down"),
    ConnectionError("db down"),
]


@pytest.mark.parametrize("exc", DB_FAILURES, ids=lambda e: type(e).__name__)
@pytest.mark.asyncio
async def test_real_mode_connect_failure_aborts_instead_of_fabricating(
    monkeypatch, exc
):
    monkeypatch.setattr(settings, "use_mock_server", False)
    calc = DailyDemandCalculator()
    calc.db = FailingConnectDB(exc)

    with pytest.raises(type(exc), match="db down"):
        await calc._get_active_plots()


@pytest.mark.parametrize("exc", DB_FAILURES, ids=lambda e: type(e).__name__)
@pytest.mark.asyncio
async def test_real_mode_query_failure_aborts_instead_of_fabricating(
    monkeypatch, exc
):
    monkeypatch.setattr(settings, "use_mock_server", False)
    calc = DailyDemandCalculator()
    calc.db = FailingFetchDB(exc)

    with pytest.raises(type(exc), match="db down"):
        await calc._get_active_plots(zones=[2])


@pytest.mark.asyncio
async def test_mock_plots_served_only_under_explicit_mock_profile(monkeypatch):
    monkeypatch.setattr(settings, "use_mock_server", True)
    calc = DailyDemandCalculator()
    calc.db = MustNotConnectDB()

    plots = await calc._get_active_plots(zones=[2])

    assert plots, "the explicit mock profile should still serve mock plots"
    assert all(plot["zone"] == 2 for plot in plots)


@pytest.mark.asyncio
async def test_query_columns_are_table_qualified(monkeypatch):
    monkeypatch.setattr(settings, "use_mock_server", False)
    calc = DailyDemandCalculator()
    calc.db = RecordingDB()

    await calc._get_active_plots(zones=[2, 3])

    (query, params) = calc.db.conn.queries[0]
    assert "p.status = 'active'" in query
    assert "p.zone = ANY($1)" in query
    assert params == ([2, 3],)


@pytest.mark.asyncio
async def test_empty_zone_list_filters_to_no_zones(monkeypatch):
    monkeypatch.setattr(settings, "use_mock_server", False)
    calc = DailyDemandCalculator()
    calc.db = RecordingDB()

    await calc._get_active_plots(zones=[])

    (query, params) = calc.db.conn.queries[0]
    assert "p.zone = ANY($1)" in query
    assert params == ([],)
