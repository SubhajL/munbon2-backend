"""PR 6.3a — the scheduler -> SCADA machine-boundary VALIDATION client.

Validation-only by construction: the class builds exactly ONE URL — the module constant
``_VALIDATE_PATH`` — and exposes exactly one network method, ``validate_intent``. There is
no field, method, or config that can hold an execute/actuate URL, and the base URL is
validated to carry NO path, so ``{base}{_VALIDATE_PATH}`` can never resolve to
``/api/gates/:id/command-level``. It mirrors ``control_flow_client``: injectable
``httpx.AsyncClient`` (tests pass a ``MockTransport``), a module ``_TIMEOUT``, fail-closed
status mapping, and echoed-field re-verification of the returned receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import httpx
from pydantic import ValidationError

from schemas.machine_boundary import ValidationReceipt
from .scada_client_errors import (
    ScadaContractViolation,
    ScadaIntentRejectedError,
    ScadaServiceAuthError,
    ScadaUnavailableError,
)
from .scada_http import SCADA_TIMEOUT, require_hostonly_base_url

# The ONLY path this client ever builds. Not configurable — a validation client can never
# hold an execute URL.
_VALIDATE_PATH = "/internal/v1/command-intents/validate"


@dataclass(frozen=True)
class ValidationDispatchResult:
    receipt: ValidationReceipt
    receipt_document_text: str  # verbatim response body, stored for the durable audit
    status: str  # validation_accepted | validation_rejected
    conflict: bool  # True ONLY on a 409 idempotency_conflict (a failure, never a success)


class ScadaValidationClient:
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

    async def validate_intent(
        self,
        intent_document: dict,
        *,
        expected_content_hash: str,
        intent_id: str,
        idempotency_key: str,
    ) -> ValidationDispatchResult:
        """POST a schema-valid CommandIntent to SCADA's validate endpoint with a FRESH
        service token, and return the durable ValidationReceipt (or raise a typed error)."""
        token = self._token_provider()
        url = self._base_url + _VALIDATE_PATH
        try:
            response = await self._client.post(
                url,
                json=intent_document,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as error:
            raise ScadaUnavailableError(
                f"SCADA validate endpoint unreachable: {error}"
            ) from error

        code = response.status_code
        if code == 503:
            raise ScadaUnavailableError("SCADA validate endpoint is dark or unavailable (503)")
        if code == 401:
            raise ScadaServiceAuthError("SCADA rejected the service token (401)")
        if code == 422:
            raise ScadaIntentRejectedError(
                "SCADA rejected the intent schema (422 schema_invalid) — a compile bug"
            )
        if code not in (200, 409):
            raise ScadaContractViolation(f"unexpected SCADA status {code}")

        try:
            body = response.json()
        except ValueError as error:
            raise ScadaContractViolation("SCADA response is not valid JSON") from error
        if not isinstance(body, dict):
            raise ScadaContractViolation("SCADA response is not a JSON object")
        try:
            receipt = ValidationReceipt.model_validate(body)
        except ValidationError as error:
            raise ScadaContractViolation(
                f"SCADA receipt violates the validation-receipt contract: {error}"
            ) from error

        # Echoed-field re-verification: a mis-routed or store-contaminated receipt filed
        # against the wrong intent must never be persisted.
        if (
            str(receipt.intent_id) != str(intent_id)
            or receipt.idempotency_key != idempotency_key
            or receipt.intent_content_hash != expected_content_hash
        ):
            raise ScadaContractViolation(
                "SCADA receipt does not echo the dispatched intent identity"
            )

        return ValidationDispatchResult(
            receipt=receipt,
            receipt_document_text=response.text,
            status=receipt.status,
            conflict=(code == 409),
        )
