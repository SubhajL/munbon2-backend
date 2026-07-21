"""Fixed-path Scheduler client for Auth TOTP step-up verification."""

from __future__ import annotations

import re
import json
from typing import Optional

import httpx

from .scada_http import require_hostonly_http_base_url

_VERIFY_PATH = "/api/v1/auth/verify-2fa"
_TIMEOUT = httpx.Timeout(5.0, connect=2.0)
_TOTP = re.compile(r"^[0-9]{6}$")


class StepUpRejectedError(Exception):
    """The principal or TOTP code was rejected."""


class StepUpUnavailableError(Exception):
    """Auth could not verify step-up, so the mutation must stop."""


class StepUpContractError(Exception):
    """Auth returned a response outside the verification contract."""


class AuthStepUpClient:
    def __init__(
        self, base_url: str, client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self._base_url = require_hostonly_http_base_url(base_url, "Auth")
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT)

    async def close(self) -> None:
        await self._client.aclose()

    async def verify_step_up(self, access_token: str, code: str) -> None:
        if not isinstance(access_token, str) or not access_token.strip():
            raise StepUpRejectedError("an access token is required")
        if not isinstance(code, str) or _TOTP.fullmatch(code) is None:
            raise StepUpRejectedError("a six-digit TOTP code is required")
        try:
            response = await self._client.post(
                self._base_url + _VERIFY_PATH,
                content=json.dumps({"code": code}, separators=(",", ":")),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.RequestError as error:
            raise StepUpUnavailableError(
                "Auth step-up endpoint is unavailable"
            ) from error
        if response.status_code in {401, 403}:
            raise StepUpRejectedError("Auth rejected the principal or TOTP code")
        if response.status_code >= 500:
            raise StepUpUnavailableError("Auth step-up endpoint is unavailable")
        if response.status_code != 200:
            raise StepUpContractError(
                f"unexpected Auth step-up status {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as error:
            raise StepUpContractError("Auth step-up response is not JSON") from error
        if not isinstance(body, dict) or type(body.get("success")) is not bool:
            raise StepUpContractError(
                "Auth step-up response has no boolean success field"
            )
        if body["success"] is not True:
            raise StepUpRejectedError("Auth rejected the TOTP code")
