"""
TimescaleClient bootstrap resilience: a database without the timescaledb extension
(no create_hypertable function) must not prevent connection — the client logs and
continues so plain-Postgres deployments still boot. Stub-based; no real DB.
"""
import pytest

from db.timescale_client import TimescaleClient


class _StubConn:
    def __init__(self, executed):
        self._executed = executed

    async def execute(self, sql):
        self._executed.append(sql)
        # Simulate missing create_hypertable function by raising on that call
        if "create_hypertable" in sql:
            raise Exception("function create_hypertable does not exist")
        return None


class _Acquire:
    def __init__(self, executed):
        self._executed = executed

    async def __aenter__(self):
        return _StubConn(self._executed)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _StubPool:
    def __init__(self, executed):
        self._executed = executed

    def acquire(self):
        return _Acquire(self._executed)


@pytest.mark.asyncio
async def test_missing_hypertable_extension_is_survived_not_skipped(monkeypatch):
    import db.timescale_client as tsc

    executed = []

    async def _fake_create_pool(*args, **kwargs):
        return _StubPool(executed)

    monkeypatch.setattr(tsc.asyncpg, "create_pool", _fake_create_pool)

    client = TimescaleClient()
    await client.connect()  # must not raise despite create_hypertable failing

    assert client.pool is not None
    hypertable_attempts = [s for s in executed if "create_hypertable" in s]
    # Both hypertable conversions (water levels + flow) must still be ATTEMPTED —
    # a client that stopped calling create_hypertable entirely would also "not raise".
    assert len(hypertable_attempts) == 2
    # And the failure of the first attempt must not abort the remaining DDL.
    first_failure = executed.index(hypertable_attempts[0])
    assert len(executed) - 1 > first_failure
