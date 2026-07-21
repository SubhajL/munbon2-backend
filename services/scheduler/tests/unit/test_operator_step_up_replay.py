import asyncio

import pytest
from fastapi import HTTPException

from api.v1.operator_controls import consume_operator_step_up


class _AtomicReplayStore:
    def __init__(self):
        self.keys = set()
        self.lock = asyncio.Lock()

    async def set_if_absent(self, key, value, *, expire):
        async with self.lock:
            if key in self.keys:
                return False
            self.keys.add(key)
            return True


@pytest.mark.asyncio
async def test_same_subject_and_totp_can_be_consumed_only_once():
    store = _AtomicReplayStore()

    await consume_operator_step_up(store, "supervisor-1", "123456")

    with pytest.raises(HTTPException) as caught:
        await consume_operator_step_up(store, "supervisor-1", "123456")
    assert (caught.value.status_code, caught.value.detail) == (
        403,
        "operator step-up code was already used",
    )


@pytest.mark.asyncio
async def test_concurrent_consumers_yield_exactly_one_success():
    store = _AtomicReplayStore()

    results = await asyncio.gather(
        consume_operator_step_up(store, "supervisor-1", "123456"),
        consume_operator_step_up(store, "supervisor-1", "123456"),
        return_exceptions=True,
    )

    assert sum(result is None for result in results) == 1
    rejected = [result for result in results if isinstance(result, HTTPException)]
    assert [(result.status_code, result.detail) for result in rejected] == [
        (403, "operator step-up code was already used")
    ]


@pytest.mark.asyncio
async def test_replay_store_failure_is_fail_closed():
    class _UnavailableStore:
        async def set_if_absent(self, key, value, *, expire):
            raise RuntimeError("down")

    with pytest.raises(HTTPException) as caught:
        await consume_operator_step_up(_UnavailableStore(), "supervisor-1", "123456")
    assert (caught.value.status_code, caught.value.detail) == (
        503,
        "operator step-up replay protection is unavailable",
    )
