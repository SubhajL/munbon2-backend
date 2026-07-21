import httpx
import pytest
from fastapi import HTTPException

from api.v1.operator_controls import get_auth_step_up_client
from core.config import settings
from services.clients.auth_step_up_client import (
    AuthStepUpClient,
    StepUpContractError,
    StepUpRejectedError,
    StepUpUnavailableError,
)


def _client(handler):
    return AuthStepUpClient(
        "http://auth.local",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


class TestAuthStepUpClient:
    @pytest.mark.asyncio
    async def test_verified_code_forwards_access_token_and_returns(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["authorization"] = request.headers.get("authorization")
            seen["body"] = request.read()
            return httpx.Response(200, json={"success": True, "message": "verified"})

        await _client(handler).verify_step_up("access-token", "123456")
        assert seen == {
            "url": "http://auth.local/api/v1/auth/verify-2fa",
            "authorization": "Bearer access-token",
            "body": b'{"code":"123456"}',
        }

    @pytest.mark.asyncio
    async def test_invalid_code_is_rejected(self):
        client = _client(lambda request: httpx.Response(200, json={"success": False}))
        with pytest.raises(StepUpRejectedError):
            await client.verify_step_up("token", "000000")

    @pytest.mark.asyncio
    async def test_auth_outage_fails_closed(self):
        def handler(request):
            raise httpx.ConnectError("down", request=request)

        with pytest.raises(StepUpUnavailableError):
            await _client(handler).verify_step_up("token", "123456")

    @pytest.mark.asyncio
    async def test_malformed_success_body_is_contract_error(self):
        client = _client(lambda request: httpx.Response(200, json={"success": "yes"}))
        with pytest.raises(StepUpContractError):
            await client.verify_step_up("token", "123456")

    @pytest.mark.asyncio
    async def test_unauthorized_token_is_rejected(self):
        client = _client(lambda request: httpx.Response(401, json={"error": "bad"}))
        with pytest.raises(StepUpRejectedError):
            await client.verify_step_up("token", "123456")

    def test_embedded_path_is_rejected(self):
        with pytest.raises(ValueError):
            AuthStepUpClient("http://auth.local/api/v1/auth/verify-2fa")

    @pytest.mark.asyncio
    async def test_malformed_runtime_auth_url_is_a_bounded_503(self, monkeypatch):
        monkeypatch.setattr(settings, "auth_service_url", "http://auth.local/path")

        with pytest.raises(HTTPException) as caught:
            await anext(get_auth_step_up_client())

        assert (caught.value.status_code, caught.value.detail) == (
            503,
            "Auth step-up configuration is invalid",
        )
