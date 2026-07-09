"""
DatabaseManager.connect_all ordering/failure contract: InfluxDB connects and pings
first; a failed ping must abort the sequence (no later store is touched) with the
specific ping error. Stub-based; no real connections.
"""
import pytest

from db.connections import DatabaseManager


class _Stub:
    def __init__(self):
        self.connected = False

    async def connect(self):
        self.connected = True

    async def ping(self):
        return True


class _StubFailPing(_Stub):
    async def ping(self):
        return False


@pytest.mark.asyncio
async def test_connect_all_connects_every_store_on_successful_ping():
    dbm = DatabaseManager()
    dbm.influxdb, dbm.timescale = _Stub(), _Stub()
    dbm.postgres, dbm.redis = _Stub(), _Stub()

    await dbm.connect_all()

    assert dbm.influxdb.connected
    assert dbm.timescale.connected
    assert dbm.postgres.connected
    assert dbm.redis.connected


@pytest.mark.asyncio
async def test_influx_ping_failure_aborts_before_other_stores():
    dbm = DatabaseManager()
    dbm.influxdb = _StubFailPing()
    dbm.timescale, dbm.postgres, dbm.redis = _Stub(), _Stub(), _Stub()

    with pytest.raises(Exception, match="InfluxDB ping failed"):
        await dbm.connect_all()

    # Fail-fast: nothing after the failed ping may have been connected.
    assert not dbm.timescale.connected
    assert not dbm.postgres.connected
    assert not dbm.redis.connected
