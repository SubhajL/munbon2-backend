import httpx
import pytest
from fastapi import HTTPException

from api.v1.operator_controls import get_scada_operator_client
from core.config import settings
from core.device_capabilities import empty_device_capability_snapshot
from services.clients.scada_operator_client import (
    ScadaOperatorClient,
    ScadaOperatorContractError,
    ScadaOperatorUnavailableError,
)


def _client(handler):
    return ScadaOperatorClient(
        "http://scada.local",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


class TestScadaOperatorClient:
    @pytest.mark.asyncio
    async def test_reads_health_and_operator_capabilities_from_fixed_paths(self):
        seen = []
        snapshot = empty_device_capability_snapshot().model_dump()

        def handler(request):
            seen.append((request.url.path, request.headers.get("authorization")))
            if request.url.path == "/health":
                return httpx.Response(
                    200, json={"status": "healthy", "service": "scada-gate-control"}
                )
            return httpx.Response(200, json=snapshot)

        client = _client(handler)
        assert await client.is_healthy() is True
        loaded = await client.get_device_capabilities("operator-token")
        assert loaded == empty_device_capability_snapshot()
        assert seen == [
            ("/health", None),
            ("/internal/v1/device-capabilities", "Bearer operator-token"),
        ]

    @pytest.mark.asyncio
    async def test_unhealthy_or_unreachable_scada_is_unavailable(self):
        client = _client(lambda request: httpx.Response(503, json={"status": "down"}))
        with pytest.raises(ScadaOperatorUnavailableError):
            await client.is_healthy()

    @pytest.mark.asyncio
    async def test_malformed_capability_snapshot_is_contract_error(self):
        client = _client(lambda request: httpx.Response(200, json={"capabilities": {}}))
        with pytest.raises(ScadaOperatorContractError):
            await client.get_device_capabilities("token")

    @pytest.mark.asyncio
    async def test_hash_mismatched_capability_snapshot_is_contract_error(self):
        snapshot = empty_device_capability_snapshot().model_dump()
        snapshot["capability_hash"] = "a" * 64
        client = _client(lambda request: httpx.Response(200, json=snapshot))
        with pytest.raises(ScadaOperatorContractError):
            await client.get_device_capabilities("token")

    def test_client_exposes_no_machine_write_method_or_path(self):
        public = {name for name in dir(ScadaOperatorClient) if not name.startswith("_")}
        assert public == {"close", "get_device_capabilities", "is_healthy"}

    def test_embedded_machine_path_is_rejected(self):
        with pytest.raises(ValueError):
            ScadaOperatorClient("http://scada.local/api/gates/g1/command-level")

    @pytest.mark.asyncio
    async def test_malformed_runtime_scada_url_is_a_bounded_503(self, monkeypatch):
        monkeypatch.setattr(
            settings,
            "scheduler_scada_base_url",
            "http://scada.local/api/gates/g1/command-level",
        )

        with pytest.raises(HTTPException) as caught:
            await anext(get_scada_operator_client())

        assert (caught.value.status_code, caught.value.detail) == (
            503,
            "live SCADA configuration is invalid",
        )
