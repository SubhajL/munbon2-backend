"""PR 6.3b — the SCADA readback client's fail-closed status mapping + shape validation."""

import httpx
import pytest

from services.clients.scada_client_errors import (
    ScadaContractViolation,
    ScadaServiceAuthError,
    ScadaUnavailableError,
)
from services.clients.scada_readback_client import ScadaReadbackClient, _READBACK_PATH


def _client(handler, *, token="service-token"):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ScadaReadbackClient("http://scada.local", lambda: token, client=http)


def _ok(gates):
    return lambda request: httpx.Response(200, json={"gates": gates})


class TestGetGateReadback:
    @pytest.mark.asyncio
    async def test_parses_gate_readings(self):
        client = _client(_ok({"M(0,0;1,0)": {"observed_level": 3, "quality": "ok"}}))
        readings = await client.get_gate_readback()
        assert readings == {"M(0,0;1,0)": {"observed_level": 3, "quality": "ok"}}

    @pytest.mark.asyncio
    async def test_empty_gates_is_the_dark_default(self):
        assert await _client(_ok({})).get_gate_readback() == {}

    @pytest.mark.asyncio
    async def test_null_observed_level_is_preserved(self):
        client = _client(_ok({"G1": {"observed_level": None, "quality": "unavailable"}}))
        readings = await client.get_gate_readback()
        assert readings["G1"]["observed_level"] is None

    @pytest.mark.asyncio
    async def test_503_raises_unavailable(self):
        with pytest.raises(ScadaUnavailableError):
            await _client(lambda r: httpx.Response(503, json={})).get_gate_readback()

    @pytest.mark.asyncio
    async def test_401_raises_service_auth(self):
        with pytest.raises(ScadaServiceAuthError):
            await _client(lambda r: httpx.Response(401, json={})).get_gate_readback()

    @pytest.mark.asyncio
    async def test_transport_error_raises_unavailable(self):
        def handler(request):
            raise httpx.ConnectError("refused", request=request)

        with pytest.raises(ScadaUnavailableError):
            await _client(handler).get_gate_readback()

    @pytest.mark.asyncio
    async def test_missing_gates_object_is_contract_violation(self):
        with pytest.raises(ScadaContractViolation):
            await _client(lambda r: httpx.Response(200, json={"nope": True})).get_gate_readback()

    @pytest.mark.asyncio
    async def test_non_integer_observed_level_is_contract_violation(self):
        client = _client(_ok({"G1": {"observed_level": "3", "quality": "ok"}}))
        with pytest.raises(ScadaContractViolation):
            await client.get_gate_readback()

    @pytest.mark.asyncio
    async def test_sends_service_token_to_the_readback_path(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            return httpx.Response(200, json={"gates": {}})

        await _client(handler, token="tok-123").get_gate_readback()
        assert seen["url"] == "http://scada.local" + _READBACK_PATH
        assert seen["auth"] == "Bearer tok-123"
