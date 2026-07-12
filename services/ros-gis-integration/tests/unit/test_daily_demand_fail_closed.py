"""PR 2.6b: demand inputs must never be fabricated on dependency failure.

Adversarial-review finding #10 (WAVE_2-4_PLAN §1.5): `_get_active_plots` caught
ANY database error and silently returned `_get_mock_plots()` — synthetic plots
that downstream demand calculation would store as real ROS/GIS output, even
with mock mode off. Mock data must be reachable ONLY through the explicit
USE_MOCK_SERVER profile; a real-mode dependency failure aborts the run (with a
structured error log).

The review's second pass found the original "real" path was itself unrunnable:
DatabaseManager exposed no `get_connection`, and the SQL used ambiguous
unqualified columns — so these tests also pin the real interface and the
query shape, not just the failure semantics.
"""

from contextlib import asynccontextmanager

import asyncpg
import pytest

from config import settings
from db.database_manager import DatabaseManager
from services.daily_demand_calculator import DailyDemandCalculator


class FailingConnectDB:
    """DB whose connection acquisition fails (outage at connect time)."""

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
    """DB that connects but whose query fails (outage mid-request)."""

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
    """Fails the test if the mock profile ever touches the database."""

    def get_connection(self):
        raise AssertionError("mock profile must not touch the database")


def test_fakes_mirror_the_real_database_interface():
    # The fakes above stand in for DatabaseManager.get_connection; if the real
    # class does not expose it, every green test here is false assurance
    # (exactly what the first version of this file did).
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
    # Both ros_gis.plots and ros_gis.sections carry a `zone` column; an
    # unqualified filter is ambiguous SQL (Postgres 42702) and aborts every
    # zone-filtered run.
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
    # zones=[] must mean "no zones" (empty filter result), not fall through
    # the falsy check into "all zones".
    monkeypatch.setattr(settings, "use_mock_server", False)
    calc = DailyDemandCalculator()
    calc.db = RecordingDB()

    await calc._get_active_plots(zones=[])

    (query, params) = calc.db.conn.queries[0]
    assert "p.zone = ANY($1)" in query
    assert params == ([],)
