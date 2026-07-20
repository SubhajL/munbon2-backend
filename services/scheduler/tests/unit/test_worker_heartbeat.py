"""Unit tests for the shadow-dispatch worker heartbeat (PR 6.4-sched)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.worker_heartbeat import (
    DISPATCH_HEARTBEAT_KEY,
    HEARTBEAT_TTL_SECONDS,
    heartbeat_age_seconds,
    read_dispatch_heartbeat,
    record_dispatch_heartbeat,
)

NOW = datetime(2026, 7, 20, 3, 0, 0, tzinfo=timezone.utc)


class _FakeRedis:
    def __init__(self, *, raise_on_set=False, raise_on_get=False, value=None):
        self.raise_on_set = raise_on_set
        self.raise_on_get = raise_on_get
        self.value = value
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def set(self, key, value, expire=None):
        if self.raise_on_set:
            raise ConnectionError("redis down")
        self.set_calls.append((key, value, expire))
        self.value = value

    async def get(self, key):
        if self.raise_on_get:
            raise ConnectionError("redis down")
        return self.value


class TestRecordDispatchHeartbeat:
    @pytest.mark.asyncio
    async def test_writes_iso_instant_under_the_shared_key_with_ttl(self):
        redis = _FakeRedis()
        ok = await record_dispatch_heartbeat(redis, now=NOW)
        assert ok is True
        assert redis.set_calls == [(DISPATCH_HEARTBEAT_KEY, NOW.isoformat(), HEARTBEAT_TTL_SECONDS)]

    @pytest.mark.asyncio
    async def test_a_redis_failure_is_swallowed_never_fails_the_tick(self):
        redis = _FakeRedis(raise_on_set=True)
        ok = await record_dispatch_heartbeat(redis, now=NOW)
        assert ok is False  # no exception propagated


class TestReadDispatchHeartbeat:
    @pytest.mark.asyncio
    async def test_returns_stored_value(self):
        redis = _FakeRedis(value=NOW.isoformat())
        assert await read_dispatch_heartbeat(redis) == NOW.isoformat()

    @pytest.mark.asyncio
    async def test_a_read_failure_returns_none_not_raise(self):
        redis = _FakeRedis(raise_on_get=True)
        assert await read_dispatch_heartbeat(redis) is None


class TestHeartbeatAgeSeconds:
    def test_none_when_absent(self):
        assert heartbeat_age_seconds(None, NOW) is None

    def test_none_when_unparseable_or_naive(self):
        assert heartbeat_age_seconds("not-a-date", NOW) is None
        assert heartbeat_age_seconds("2026-07-20T03:00:00", NOW) is None  # no tzinfo

    def test_positive_age_for_a_past_beat(self):
        beat = (NOW - timedelta(seconds=90)).isoformat()
        assert heartbeat_age_seconds(beat, NOW) == 90.0

    def test_future_beat_is_clamped_to_zero(self):
        beat = (NOW + timedelta(seconds=30)).isoformat()
        assert heartbeat_age_seconds(beat, NOW) == 0.0
