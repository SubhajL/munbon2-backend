"""PR 6.3b — the scheduler -> SCADA machine-boundary READBACK client.

Read-only companion to the validation client: builds exactly ONE URL (the module constant
``_READBACK_PATH``), authenticated with the SAME dedicated service token (the scheduler never
holds operator creds). Mirrors the validation client's injectable transport, host-only base URL,
and fail-closed status mapping. There is no write/actuate method anywhere.
"""

from __future__ import annotations

from typing import Callable, Optional

import httpx

from .scada_client_errors import (
    ScadaContractViolation,
    ScadaServiceAuthError,
    ScadaUnavailableError,
)
from .scada_http import SCADA_TIMEOUT, require_hostonly_base_url

_READBACK_PATH = "/internal/v1/gate-readback"


class ScadaReadbackClient:
    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], str],
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._base_url = require_hostonly_base_url(base_url)
        self._token_provider = token_provider
        self._client = client or httpx.AsyncClient(timeout=SCADA_TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_gate_readback(self) -> dict:
        """Return the machine-boundary readback as ``{canonical_gate_id: {observed_level, quality}}``.
        Fail-closed: 503/transport -> Unavailable, 401 -> ServiceAuth, non-200/non-JSON/bad-shape
        -> ContractViolation."""
        token = self._token_provider()
        url = self._base_url + _READBACK_PATH
        try:
            response = await self._client.get(
                url, headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.RequestError as error:
            raise ScadaUnavailableError(
                f"SCADA readback endpoint unreachable: {error}"
            ) from error

        code = response.status_code
        if code == 503:
            raise ScadaUnavailableError("SCADA readback endpoint is dark or unavailable (503)")
        if code == 401:
            raise ScadaServiceAuthError("SCADA rejected the service token (401)")
        if code != 200:
            raise ScadaContractViolation(f"unexpected SCADA readback status {code}")

        try:
            body = response.json()
        except ValueError as error:
            raise ScadaContractViolation("SCADA readback response is not valid JSON") from error
        if not isinstance(body, dict) or not isinstance(body.get("gates"), dict):
            raise ScadaContractViolation("SCADA readback response has no gates object")

        readings: dict = {}
        for gate_id, gate in body["gates"].items():
            if not isinstance(gate, dict):
                raise ScadaContractViolation(f"readback for gate {gate_id!r} is not an object")
            observed = gate.get("observed_level")
            quality = gate.get("quality")
            if observed is not None and not isinstance(observed, int):
                raise ScadaContractViolation(
                    f"observed_level for gate {gate_id!r} is not an integer or null"
                )
            if not isinstance(quality, str):
                raise ScadaContractViolation(f"quality for gate {gate_id!r} is not a string")
            readings[gate_id] = {"observed_level": observed, "quality": quality}
        return readings
