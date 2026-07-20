"""PR 4.4a-3 — BFF bounded control-plan LIST pass-through.

Two layers, matching the detail projection tests:
- Client (httpx.MockTransport): forwards the operator bearer + the exact
  filters/cursor/limit as query params to GET /api/v1/control-plans, and maps
  every non-200 to a typed fail-closed error (never an empty page).
- Route (FastAPI dependency_overrides): strict-validated pass-through that
  preserves the scheduler failure taxonomy, fails closed (502) on contract
  drift, and NEVER fabricates an empty page on failure.
"""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import control_plans
from clients.scheduler_client import (
    SchedulerAuthError,
    SchedulerBadRequestError,
    SchedulerClient,
    SchedulerContractError,
    SchedulerControlPlanNotFoundError,
    SchedulerUnavailableError,
    SchedulerUpstreamError,
)

PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REQ_RUN_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CAMPAIGN_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
TOKEN = "operator-jwt-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _summary(**overrides) -> dict:
    row = {
        "plan_id": PLAN_ID,
        "plan_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "lifecycle_state": "approved_for_shadow",
        "approval_trust": True,
        "horizon_start": "2026-07-20T00:00:00Z",
        "horizon_end": "2026-07-21T00:00:00Z",
        "requirement_run_id": REQ_RUN_ID,
        "requirement_version": 3,
        "input_content_hash": "1" * 64,
        "model_snapshot_id": "a" * 64,
        "model_release_content_hash": "b" * 64,
        "optimizer_status": "feasible",
        "prediction_status": "completed",
        "prediction_run_id": "c" * 64,
        "prediction_response_sha256": "d" * 64,
        "created_by_subject": "operator-7",
        "created_at": "2026-07-18T09:30:15.123456Z",
    }
    row.update(overrides)
    return row


def _page(*, items=None, next_cursor=None) -> dict:
    return {
        "items": items if items is not None else [_summary()],
        "next_cursor": next_cursor,
        "projection_schema_version": 2,
    }


# --- client stub for route tests --------------------------------------------
class _StubSchedulerClient:
    def __init__(self, *, page=None, error=None):
        self.page = page
        self.error = error
        self.calls: list[dict] = []

    async def list_control_plans(self, *, filters, cursor, limit, bearer_token):
        self.calls.append(
            {
                "filters": filters,
                "cursor": cursor,
                "limit": limit,
                "bearer_token": bearer_token,
            }
        )
        if self.error is not None:
            raise self.error
        return self.page


def _app(stub: _StubSchedulerClient) -> TestClient:
    app = FastAPI()
    app.include_router(control_plans.router)
    app.dependency_overrides[control_plans.get_scheduler_client] = lambda: stub
    return TestClient(app)


# --- client layer (MockTransport) -------------------------------------------
def _client(handler) -> tuple[SchedulerClient, list]:
    captured: list[httpx.Request] = []

    def _wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    transport = httpx.MockTransport(_wrapped)
    return (
        SchedulerClient(base_url="http://scheduler.test", transport=transport),
        captured,
    )


@pytest.mark.asyncio
async def test_bff_list_forwards_bearer_cursor_and_filters():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page(), request=request)

    client, captured = _client(handler)
    page = await client.list_control_plans(
        filters={
            "lifecycle_state": "approved_for_shadow",
            "requirement_version": 3,
            "prediction_run_id": None,  # dropped: absent filter
        },
        cursor="opaque-cursor",
        limit=10,
        bearer_token=TOKEN,
    )

    assert page["projection_schema_version"] == 2
    assert len(captured) == 1
    request = captured[0]
    assert request.url.path == "/api/v1/control-plans"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    params = request.url.params
    assert params["lifecycle_state"] == "approved_for_shadow"
    assert params["requirement_version"] == "3"
    assert params["cursor"] == "opaque-cursor"
    assert params["limit"] == "10"
    # A None-valued filter is never sent as a query param.
    assert "prediction_run_id" not in params


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,expected",
    [
        (404, SchedulerControlPlanNotFoundError),
        (401, SchedulerAuthError),
        (403, SchedulerAuthError),
        (400, SchedulerBadRequestError),
        (422, SchedulerBadRequestError),
        (503, SchedulerUnavailableError),
        (500, SchedulerUpstreamError),
    ],
)
async def test_bff_list_client_preserves_failure_taxonomy(status, expected):
    def handler(request):
        return httpx.Response(status, json={"detail": "nope"}, request=request)

    client, _ = _client(handler)
    with pytest.raises(expected):
        await client.list_control_plans(
            filters={}, cursor=None, limit=25, bearer_token=TOKEN
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
async def test_bff_list_client_bad_request_carries_status_and_detail(status):
    def handler(request):
        return httpx.Response(
            status, json={"detail": "stale cursor"}, request=request
        )

    client, _ = _client(handler)
    with pytest.raises(SchedulerBadRequestError) as exc:
        await client.list_control_plans(
            filters={}, cursor="x", limit=25, bearer_token=TOKEN
        )
    assert exc.value.status_code == status
    assert exc.value.detail == "stale cursor"


@pytest.mark.asyncio
async def test_bff_list_client_raises_contract_error_on_non_object_200():
    def handler(request):
        return httpx.Response(200, json=[1, 2, 3], request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerContractError):
        await client.list_control_plans(
            filters={}, cursor=None, limit=25, bearer_token=TOKEN
        )


@pytest.mark.asyncio
async def test_bff_list_client_raises_unavailable_on_transport_failure():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerUnavailableError):
        await client.list_control_plans(
            filters={}, cursor=None, limit=25, bearer_token=TOKEN
        )


# --- route layer ------------------------------------------------------------
def test_bff_list_route_returns_page_and_forwards_query():
    stub = _StubSchedulerClient(page=_page(next_cursor="next-page-cursor"))
    response = _app(stub).get(
        "/api/v1/control-plans?limit=10&lifecycle_state=draft"
        "&cursor=prev-cursor&requirement_version=3",
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["next_cursor"] == "next-page-cursor"
    assert body["items"][0]["plan_id"] == PLAN_ID
    assert body["projection_schema_version"] == 2
    assert response.headers["Cache-Control"] == "no-store"
    # the operator bearer + exact filters/cursor/limit reached the client
    call = stub.calls[0]
    assert call["bearer_token"] == TOKEN
    assert call["cursor"] == "prev-cursor"
    assert call["limit"] == 10
    assert call["filters"]["lifecycle_state"] == "draft"
    assert call["filters"]["requirement_version"] == 3


def test_bff_list_page_is_strict_mirror_and_omits_large_documents():
    body = _app(_StubSchedulerClient(page=_page())).get(
        "/api/v1/control-plans", headers=AUTH
    ).json()
    item = body["items"][0]
    assert item["approval_trust"] is True
    for forbidden in (
        "optimizer_result",
        "requirements",
        "events",
        "transitions",
        "ledger",
        "entries",
        "trajectory",
    ):
        assert forbidden not in item


def test_bff_list_unknown_extra_field_fails_closed_502():
    drifted = _page()
    drifted["items"][0]["surprise_new_field"] = "unexpected"
    response = _app(_StubSchedulerClient(page=drifted)).get(
        "/api/v1/control-plans", headers=AUTH
    )
    assert response.status_code == 502


def test_bff_list_retyped_scalar_fails_closed_502():
    drifted = _page()
    drifted["items"][0]["plan_version"] = "1"  # numeric string must not coerce
    response = _app(_StubSchedulerClient(page=drifted)).get(
        "/api/v1/control-plans", headers=AUTH
    )
    assert response.status_code == 502


def test_bff_list_boolean_approval_trust_must_be_boolean_502():
    drifted = _page()
    drifted["items"][0]["approval_trust"] = "true"  # string, not bool
    response = _app(_StubSchedulerClient(page=drifted)).get(
        "/api/v1/control-plans", headers=AUTH
    )
    assert response.status_code == 502


def test_bff_list_accepts_shadow_active_in_v2():
    response = _app(
        _StubSchedulerClient(
            page=_page(items=[_summary(lifecycle_state="shadow_active")])
        )
    ).get("/api/v1/control-plans", headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["lifecycle_state"] == "shadow_active"


@pytest.mark.parametrize(
    "error,expected_status",
    [
        (SchedulerUnavailableError("scheduler is unavailable"), 503),
        (SchedulerControlPlanNotFoundError("nope"), 404),
        (SchedulerAuthError(401, "token expired"), 401),
        (SchedulerAuthError(403, "forbidden"), 403),
        # A scheduler CLIENT error (stale cursor / invalid filter) is forwarded
        # with its exact status — NOT masked as a 502/503 outage.
        (SchedulerBadRequestError(422, "stale cursor"), 422),
        (SchedulerBadRequestError(400, "bad filter"), 400),
        (SchedulerContractError("malformed"), 502),
        (SchedulerUpstreamError("boom"), 502),
    ],
)
def test_bff_list_preserves_scheduler_failure_taxonomy(error, expected_status):
    response = _app(_StubSchedulerClient(error=error)).get(
        "/api/v1/control-plans", headers=AUTH
    )
    assert response.status_code == expected_status


def test_bff_list_scheduler_422_becomes_422_retaining_detail():
    # A stale/cross-filter cursor is a scheduler 422 (CursorError). The BFF must
    # forward 422 with the detail, not mask it as a 502 outage (false alert).
    stub = _StubSchedulerClient(
        error=SchedulerBadRequestError(422, "cursor was issued for a "
                                            "different filter set")
    )
    response = _app(stub).get(
        "/api/v1/control-plans?cursor=stale", headers=AUTH
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "cursor was issued for a different filter set"
    }


def test_bff_list_projection_version_drift_fails_closed_502():
    # An upstream page announcing the retired projection_schema_version 1 is drift:
    # the strict mirror rejects it, so the route 502s rather than serving an
    # unknown-shape page as a confident 200.
    drifted = _page()
    drifted["projection_schema_version"] = 1
    response = _app(_StubSchedulerClient(page=drifted)).get(
        "/api/v1/control-plans", headers=AUTH
    )
    assert response.status_code == 502


def test_bff_list_error_response_is_not_cacheable():
    response = _app(
        _StubSchedulerClient(
            error=SchedulerUnavailableError("scheduler is unavailable")
        )
    ).get("/api/v1/control-plans", headers=AUTH)
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"


def test_bff_list_never_fabricates_empty_page_on_failure():
    stub = _StubSchedulerClient(
        error=SchedulerUnavailableError("scheduler is unavailable")
    )
    response = _app(stub).get("/api/v1/control-plans", headers=AUTH)
    assert response.status_code == 503
    body = response.json()
    # No fabricated empty page — the response is only an error detail.
    assert set(body) == {"detail"}
    assert "items" not in response.text
    assert "projection_schema_version" not in response.text


def test_bff_list_rejects_missing_bearer_without_contacting_scheduler():
    stub = _StubSchedulerClient(page=_page())
    response = _app(stub).get("/api/v1/control-plans")  # no Authorization header
    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    assert stub.calls == []


def test_bff_list_limit_out_of_range_rejected_before_scheduler_call():
    stub = _StubSchedulerClient(page=_page())
    client = _app(stub)
    responses = [
        client.get("/api/v1/control-plans?limit=51", headers=AUTH),
        client.get("/api/v1/control-plans?limit=0", headers=AUTH),
    ]
    assert [response.status_code for response in responses] == [422, 422]
    assert all(
        response.headers["cache-control"] == "no-store" for response in responses
    )
    assert stub.calls == []
