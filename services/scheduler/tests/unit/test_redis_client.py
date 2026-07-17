import asyncio
import pytest

from core.redis import RedisClient


class _StubRedis:
    async def lrange(self, key, start, end):
        return ["{\"id\":1}", "{\"id\":2}", "not-json"]


@pytest.mark.asyncio
async def test_get_list_parses_json_values():
    client = RedisClient()
    client.client = _StubRedis()
    values = await client.get_list("any")
    assert isinstance(values, list)
    assert values[0] == {"id": 1}
    assert values[1] == {"id": 2}
    assert values[2] == "not-json"
