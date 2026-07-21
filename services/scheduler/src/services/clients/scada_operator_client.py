"""Read-only Scheduler client for live SCADA operator readiness evidence."""

from __future__ import annotations

from typing import Optional

import httpx

from core.device_capabilities import (
    DeviceCapabilityConfigError,
    validate_device_capability_snapshot,
)
from schemas.machine_boundary import DeviceCapabilitySnapshot

from .scada_http import SCADA_TIMEOUT, require_hostonly_base_url

_HEALTH_PATH = "/health"
_CAPABILITIES_PATH = "/internal/v1/device-capabilities"


class ScadaOperatorUnavailableError(Exception):
    """SCADA readiness evidence is unavailable, so the mutation must stop."""


class ScadaOperatorContractError(Exception):
    """SCADA returned data outside the operator-read contract."""


class ScadaOperatorClient:
    def __init__(
        self, base_url: str, client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self._base_url = require_hostonly_base_url(base_url)
        self._client = client or httpx.AsyncClient(timeout=SCADA_TIMEOUT)

    async def close(self) -> None:
        await self._client.aclose()

    async def is_healthy(self) -> bool:
        response = await self._get(_HEALTH_PATH)
        try:
            body = response.json()
        except ValueError as error:
            raise ScadaOperatorContractError(
                "SCADA health response is not JSON"
            ) from error
        if body != {"status": "healthy", "service": "scada-gate-control"}:
            raise ScadaOperatorContractError("SCADA health response is not healthy")
        return True

    async def get_device_capabilities(
        self, access_token: str
    ) -> DeviceCapabilitySnapshot:
        if not isinstance(access_token, str) or not access_token.strip():
            raise ScadaOperatorContractError("an operator access token is required")
        response = await self._get(
            _CAPABILITIES_PATH,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            body = response.json()
            return validate_device_capability_snapshot(body)
        except ValueError as error:
            raise ScadaOperatorContractError(
                "SCADA capability response is not JSON"
            ) from error
        except DeviceCapabilityConfigError as error:
            raise ScadaOperatorContractError(str(error)) from error

    async def _get(self, path: str, headers: Optional[dict] = None) -> httpx.Response:
        try:
            response = await self._client.get(self._base_url + path, headers=headers)
        except httpx.RequestError as error:
            raise ScadaOperatorUnavailableError(
                "SCADA operator read is unavailable"
            ) from error
        if response.status_code == 503 or response.status_code >= 500:
            raise ScadaOperatorUnavailableError("SCADA operator read is unavailable")
        if response.status_code != 200:
            raise ScadaOperatorContractError(
                f"unexpected SCADA operator status {response.status_code}"
            )
        return response
