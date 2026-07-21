from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import ValidationError

from schemas.machine_execution import ExecutionReceipt
from services.clients.scada_client_errors import (
    ScadaContractViolation,
    ScadaServiceAuthError,
    ScadaUnavailableError,
)
from services.clients.scada_http import SCADA_TIMEOUT, require_hostonly_base_url

_EXECUTE_PATH = "/internal/v1/command-intents/execute"


@dataclass(frozen=True)
class ExecutionDispatchResult:
    receipt: ExecutionReceipt
    receipt_document_text: str


class ScadaExecutionClient:
    def __init__(self, base_url: str, client: Optional[httpx.AsyncClient] = None):
        self._base_url = require_hostonly_base_url(base_url)
        self._client = client or httpx.AsyncClient(timeout=SCADA_TIMEOUT)

    async def aclose(self):
        await self._client.aclose()

    async def execute_intent(
        self,
        request_document: dict,
        *,
        token: str,
        intent_id: str,
        idempotency_key: str,
        grant_id: str,
        authority_not_after: str,
        original_intent_content_hash: str,
        execution_intent_content_hash: str,
    ) -> ExecutionDispatchResult:
        try:
            response = await self._client.post(
                self._base_url + _EXECUTE_PATH,
                json=request_document,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as error:
            raise ScadaUnavailableError(
                f"SCADA execute endpoint unreachable: {error}"
            ) from error
        if response.status_code == 503:
            raise ScadaUnavailableError(
                "SCADA execute endpoint is dark or unavailable (503)"
            )
        if response.status_code in (401, 403):
            raise ScadaServiceAuthError("SCADA rejected the bound execute token")
        if response.status_code not in (200, 409, 422):
            raise ScadaContractViolation(
                f"unexpected SCADA execute status {response.status_code}"
            )
        try:
            receipt = ExecutionReceipt.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise ScadaContractViolation(
                "SCADA execution receipt violates its contract"
            ) from error
        if (
            receipt.intent_id != str(intent_id)
            or receipt.idempotency_key != idempotency_key
            or receipt.grant_id != grant_id
            or receipt.authority_not_after != authority_not_after
            or receipt.original_intent_content_hash != original_intent_content_hash
            or receipt.execution_intent_content_hash != execution_intent_content_hash
            or receipt.purpose != request_document.get("purpose")
        ):
            raise ScadaContractViolation(
                "SCADA execution receipt does not echo the request binding"
            )
        requested_intent = request_document.get("intent")
        if not isinstance(requested_intent, dict) or (
            receipt.capability_hash != requested_intent.get("capability_hash")
            or receipt.target_level != requested_intent.get("target_level")
        ):
            raise ScadaContractViolation(
                "SCADA execution receipt disagrees with the requested target"
            )
        expected_status = (
            409
            if receipt.reason_code == "idempotency_conflict"
            else 422
            if receipt.status == "execution_rejected"
            else 200
        )
        if response.status_code != expected_status:
            raise ScadaContractViolation(
                "SCADA execute status disagrees with the execution receipt"
            )
        return ExecutionDispatchResult(
            receipt=receipt, receipt_document_text=response.text
        )
