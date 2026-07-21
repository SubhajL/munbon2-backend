import httpx
import pytest

from services.clients.scada_client_errors import (
    ScadaContractViolation,
    ScadaServiceAuthError,
    ScadaUnavailableError,
)
from services.clients.scada_execution_client import ScadaExecutionClient, _EXECUTE_PATH

INTENT_ID = "11111111-1111-4111-8111-111111111111"
IDEM = "cmd.plan.1.1"
ORIGINAL = "a" * 64
EXECUTION = "b" * 64
GRANT_ID = "77777777-7777-4777-8777-777777777777"
AUTHORITY_NOT_AFTER = "2026-07-20T03:05:00.000Z"


def receipt(**over):
    body = {
        "schema_version": 1,
        "receipt_id": "99999999-9999-4999-8999-999999999999",
        "intent_id": INTENT_ID,
        "idempotency_key": IDEM,
        "grant_id": GRANT_ID,
        "authority_not_after": AUTHORITY_NOT_AFTER,
        "original_intent_content_hash": ORIGINAL,
        "execution_intent_content_hash": EXECUTION,
        "capability_hash": "c" * 64,
        "purpose": "operator_approved",
        "status": "execution_succeeded",
        "reason_code": None,
        "target_level": 3,
        "observed_level": 3,
        "readback_quality": "ok",
        "writes": [],
        "executed_at": "2026-07-20T03:00:00.000Z",
    }
    body.update(over)
    return body


async def execute(handler):
    client = ScadaExecutionClient(
        "http://scada.local",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return await client.execute_intent(
        {
            "intent": {"capability_hash": "c" * 64, "target_level": 3},
            "purpose": "operator_approved",
        },
        token="bound-token",
        intent_id=INTENT_ID,
        idempotency_key=IDEM,
        grant_id=GRANT_ID,
        authority_not_after=AUTHORITY_NOT_AFTER,
        original_intent_content_hash=ORIGINAL,
        execution_intent_content_hash=EXECUTION,
    )


@pytest.mark.asyncio
async def test_execute_posts_only_to_the_execute_path_and_revalidates_echoes():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=receipt())

    result = await execute(handler)
    assert result.receipt.status == "execution_succeeded"
    assert seen == {
        "url": "http://scada.local" + _EXECUTE_PATH,
        "auth": "Bearer bound-token",
    }


@pytest.mark.asyncio
async def test_execute_rejects_mismatched_execution_hash():
    with pytest.raises(ScadaContractViolation):
        await execute(
            lambda request: httpx.Response(
                200, json=receipt(execution_intent_content_hash="d" * 64)
            )
        )


@pytest.mark.asyncio
async def test_execute_rejects_mismatched_grant_binding():
    with pytest.raises(ScadaContractViolation):
        await execute(
            lambda request: httpx.Response(
                200,
                json=receipt(grant_id="88888888-8888-4888-8888-888888888888"),
            )
        )


@pytest.mark.asyncio
async def test_execute_rejects_a_receipt_with_noncontractual_readback_quality():
    with pytest.raises(ScadaContractViolation):
        await execute(
            lambda request: httpx.Response(
                200, json=receipt(readback_quality="looks-fine")
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override",
    [
        {"capability_hash": "d" * 64},
        {"target_level": 4, "observed_level": 4},
    ],
)
async def test_execute_rejects_a_receipt_that_disagrees_with_the_requested_target(
    override,
):
    with pytest.raises(ScadaContractViolation):
        await execute(lambda request: httpx.Response(200, json=receipt(**override)))


@pytest.mark.asyncio
async def test_execute_rejects_success_receipt_on_rejection_http_status():
    with pytest.raises(ScadaContractViolation):
        await execute(lambda request: httpx.Response(422, json=receipt()))


@pytest.mark.asyncio
async def test_execute_maps_auth_and_dark_failures():
    with pytest.raises(ScadaServiceAuthError):
        await execute(lambda request: httpx.Response(403, json={"error": "scope"}))
    with pytest.raises(ScadaUnavailableError):
        await execute(lambda request: httpx.Response(503, json={"error": "dark"}))
