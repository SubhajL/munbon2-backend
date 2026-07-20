"""PR 6.3a — the SCADA validation client's fail-closed status mapping, echoed-field
re-verification, and validation-ONLY (no-execute) construction."""

import httpx
import pytest

from services.clients.scada_client_errors import (
    ScadaContractViolation,
    ScadaIntentRejectedError,
    ScadaServiceAuthError,
    ScadaUnavailableError,
)
from services.clients.scada_validation_client import (
    ScadaValidationClient,
    _VALIDATE_PATH,
)

INTENT_ID = "11111111-1111-4111-8111-111111111111"
CORRELATION_ID = "22222222-2222-4222-8222-222222222222"
RECEIPT_ID = "99999999-9999-4999-8999-999999999999"
IDEM = "campaign-eeee-week37-gate-M00-seq-1"
CONTENT_HASH = "a" * 64
CAP_HASH = "b" * 64
INTENT_DOC = {"schema_version": 1, "intent_id": INTENT_ID}  # the client only forwards it


def _receipt(status="validation_accepted", reason_code=None, *, intent_id=INTENT_ID,
             idempotency_key=IDEM, content_hash=CONTENT_HASH):
    return {
        "schema_version": 1,
        "receipt_id": RECEIPT_ID,
        "intent_id": intent_id,
        "correlation_id": CORRELATION_ID,
        "request_id": "req-01HZY.machine-boundary_001",
        "idempotency_key": idempotency_key,
        "intent_content_hash": content_hash,
        "capability_hash": CAP_HASH,
        "status": status,
        "validated_at": "2026-07-20T03:00:00.000Z",
        "reason_code": reason_code,
    }


def _client(handler, *, token="service-token"):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ScadaValidationClient("http://scada.local", lambda: token, client=http)


def _respond(status_code, json_body=None, *, text_body=None):
    def handler(request):
        if text_body is not None:
            return httpx.Response(status_code, text=text_body)
        return httpx.Response(status_code, json=json_body)

    return handler


async def _validate(client):
    return await client.validate_intent(
        INTENT_DOC,
        expected_content_hash=CONTENT_HASH,
        intent_id=INTENT_ID,
        idempotency_key=IDEM,
    )


class TestValidateIntentStatusMapping:
    @pytest.mark.asyncio
    async def test_200_accepted_returns_receipt(self):
        result = await _validate(_client(_respond(200, _receipt())))
        assert result.status == "validation_accepted"
        assert result.conflict is False
        assert result.receipt.reason_code is None

    @pytest.mark.asyncio
    async def test_200_rejected_is_a_successful_validation(self):
        # A merit rejection is a SUCCESSFUL validation (SCADA returns 200) and must be usable.
        body = _receipt("validation_rejected", "capability_mismatch")
        result = await _validate(_client(_respond(200, body)))
        assert result.status == "validation_rejected"
        assert result.receipt.reason_code == "capability_mismatch"
        assert result.conflict is False

    @pytest.mark.asyncio
    async def test_409_is_flagged_as_conflict(self):
        body = _receipt("validation_rejected", "idempotency_conflict")
        result = await _validate(_client(_respond(409, body)))
        assert result.conflict is True

    @pytest.mark.asyncio
    async def test_422_raises_intent_rejected(self):
        with pytest.raises(ScadaIntentRejectedError):
            await _validate(_client(_respond(422, {"reason_code": "schema_invalid"})))

    @pytest.mark.asyncio
    async def test_401_raises_service_auth(self):
        with pytest.raises(ScadaServiceAuthError):
            await _validate(_client(_respond(401, {"error": "bad token"})))

    @pytest.mark.asyncio
    async def test_503_raises_unavailable(self):
        with pytest.raises(ScadaUnavailableError):
            await _validate(_client(_respond(503, {"error": "dark"})))

    @pytest.mark.asyncio
    async def test_transport_error_raises_unavailable(self):
        def handler(request):
            raise httpx.ConnectError("refused", request=request)

        with pytest.raises(ScadaUnavailableError):
            await _validate(_client(handler))

    @pytest.mark.asyncio
    async def test_unexpected_status_is_contract_violation(self):
        with pytest.raises(ScadaContractViolation):
            await _validate(_client(_respond(418, {"nope": True})))

    @pytest.mark.asyncio
    async def test_non_json_body_is_contract_violation(self):
        with pytest.raises(ScadaContractViolation):
            await _validate(_client(_respond(200, text_body="<html>not json</html>")))

    @pytest.mark.asyncio
    async def test_contract_invalid_receipt_is_contract_violation(self):
        # accepted receipt carrying a reason_code violates the ValidationReceipt invariant.
        bad = _receipt("validation_accepted", "capability_mismatch")
        with pytest.raises(ScadaContractViolation):
            await _validate(_client(_respond(200, bad)))


class TestEchoedFieldReVerification:
    @pytest.mark.asyncio
    async def test_mismatched_content_hash_is_contract_violation(self):
        body = _receipt(content_hash="c" * 64)  # not the dispatched hash
        with pytest.raises(ScadaContractViolation):
            await _validate(_client(_respond(200, body)))

    @pytest.mark.asyncio
    async def test_mismatched_intent_id_is_contract_violation(self):
        body = _receipt(intent_id="deadbeef-dead-4ead-8ead-deaddeaddead")
        with pytest.raises(ScadaContractViolation):
            await _validate(_client(_respond(200, body)))


class TestValidationOnlyConstruction:
    @pytest.mark.asyncio
    async def test_posts_only_to_the_validate_path_with_the_service_token(self):
        seen = {}

        def handler(request):
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            return httpx.Response(200, json=_receipt())

        await _validate(_client(handler, token="the-service-token"))
        assert seen["url"] == "http://scada.local" + _VALIDATE_PATH
        assert seen["auth"] == "Bearer the-service-token"

    def test_the_only_path_is_the_validate_path(self):
        assert _VALIDATE_PATH == "/internal/v1/command-intents/validate"
        assert "command-level" not in _VALIDATE_PATH
        assert "horn" not in _VALIDATE_PATH

    def test_base_url_with_an_embedded_path_is_rejected(self):
        # A base carrying a path could smuggle an operator/execute route into {base}{path}.
        with pytest.raises(ValueError):
            ScadaValidationClient(
                "http://scada.local/api/gates/waste-way/command-level",
                lambda: "t",
                client=httpx.AsyncClient(transport=httpx.MockTransport(_respond(200))),
            )

    def test_base_url_must_be_absolute(self):
        with pytest.raises(ValueError):
            ScadaValidationClient(
                "scada.local",
                lambda: "t",
                client=httpx.AsyncClient(transport=httpx.MockTransport(_respond(200))),
            )

    def test_base_url_with_userinfo_is_rejected(self):
        # `http://realhost@evil.com` would ship the bearer SERVICE TOKEN to evil.com.
        with pytest.raises(ValueError):
            ScadaValidationClient(
                "http://realhost@evil.com",
                lambda: "t",
                client=httpx.AsyncClient(transport=httpx.MockTransport(_respond(200))),
            )
