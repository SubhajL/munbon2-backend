"""PR 4.4 — BFF read-only control-plan projection.

Two layers:
- Client (httpx.MockTransport): the two authenticated reads forward the operator
  bearer to BOTH endpoints, never swallow failure, and map each upstream status
  to a typed fail-closed error.
- Routes (FastAPI dependency_overrides): validated pass-through preserves exact
  lineage and every upstream state (unavailable / infeasible / invalidated /
  stale), rejects missing bearer, and fails closed (502) on contract drift.
"""

import importlib
import json

import httpx
import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import control_plans
from clients.scheduler_client import (
    SchedulerAuthError,
    SchedulerClient,
    SchedulerContractError,
    SchedulerControlPlanNotFoundError,
    SchedulerUnavailableError,
    SchedulerUpstreamError,
)

PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REQ_RUN_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
PLAN_VERSION = 3
TOKEN = "operator-jwt-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

SHADOW_DOCUMENT = {
    "machine_authority_granted": False,
    "draft_content_hash": "sha256:draft-hash",
    "requirement_set_hash": "sha256:reqset-hash",
    "prediction_response_hash": "sha256:pred-resp-hash",
    "ledger_sha256": "sha256:ledger-hash",
    "optimizer_result_hash": "sha256:opt-hash",
}


def _requirement(source_data_status: str = "published") -> dict:
    return {
        "requirement_id": "req-1",
        "run_id": REQ_RUN_ID,
        "source_version": 2,
        "service_date": "2026-07-16",
        "section_id": "section-1",
        "zone": 1,
        "required_volume_m3": 800.0,
        "window_start": "2026-07-16T06:00:00Z",
        "window_end": "2026-07-16T18:00:00Z",
        "quality": "estimated",
        "published_at": "2026-07-16T02:30:00Z",
        "as_of_date": "2026-07-16",
        "source_data_status": source_data_status,
        "planning_disposition": "scheduled",
        "delivery_node_id": "node-1",
        "gate_id": "G1",
        "maximum_delivery_m3s": 0.48,
        "approved_excess_m3": 10.0,
        "travel_delay_seconds": 3600,
        "minimum_delivery_fraction": 0.1,
        "maximum_delivery_fraction": 1.0,
        "path_reach_ids": ["reach-1", "reach-2"],
        "rotation_windows": [
            {"start": "2026-07-16T06:00:00Z", "end": "2026-07-16T18:00:00Z"}
        ],
    }


def _transitions(*, lifecycle: str = "approved_for_shadow") -> list[dict]:
    base = [
        {
            "transition_sequence": 1,
            "transition_type": "create",
            "from_state": None,
            "to_state": "draft",
            "actor_subject": "operator-7",
            "reason": None,
            "transition_document": None,
            "occurred_at": "2026-07-16T02:00:00Z",
        },
        {
            "transition_sequence": 2,
            "transition_type": "review",
            "from_state": "draft",
            "to_state": "under_review",
            "actor_subject": "operator-7",
            "reason": "ready for review",
            "transition_document": None,
            "occurred_at": "2026-07-16T02:45:00Z",
        },
    ]
    if lifecycle == "approved_for_shadow":
        base.append(
            {
                "transition_sequence": 3,
                "transition_type": "approve_for_shadow",
                "from_state": "under_review",
                "to_state": "approved_for_shadow",
                "actor_subject": "operator-7",
                "reason": "looks good",
                "transition_document": SHADOW_DOCUMENT,
                "occurred_at": "2026-07-16T03:00:00Z",
            }
        )
    elif lifecycle == "invalidated":
        base.append(
            {
                "transition_sequence": 3,
                "transition_type": "invalidate",
                "from_state": "under_review",
                "to_state": "invalidated",
                "actor_subject": "operator-7",
                "reason": "model snapshot revoked",
                "transition_document": {"invalidation_cause": "model_release_revoked"},
                "occurred_at": "2026-07-16T04:00:00Z",
            }
        )
    return base


def _detail_payload(
    *,
    lifecycle: str = "approved_for_shadow",
    prediction_status: str = "completed",
    optimizer_status: str = "feasible",
    member_status: str = "completed",
    source_data_status: str = "published",
) -> dict:
    return {
        "plan_id": PLAN_ID,
        "plan_version": PLAN_VERSION,
        "lifecycle_state": lifecycle,
        "input_content_hash": "sha256:input-hash",
        "draft_content_hash": "sha256:draft-hash",
        "requirement_run_id": REQ_RUN_ID,
        "requirement_version": 2,
        "model_snapshot_id": "model-snap-1",
        "model_release_id": "model-rel-1",
        "model_release_content_hash": "sha256:model-hash",
        "optimizer_status": optimizer_status,
        "prediction_status": prediction_status,
        "prediction_run_id": "pred-run-1"
        if prediction_status != "not_requested"
        else None,
        "prediction_member_statuses": [
            {"member": "lower", "status": member_status},
            {"member": "nominal", "status": member_status},
            {"member": "upper", "status": member_status},
        ],
        "horizon_start": "2026-07-16T00:00:00Z",
        "horizon_end": "2026-07-17T00:00:00Z",
        "model_step_seconds": 3600,
        "max_intermediate_trims": 2,
        "optimizer_result": {"objective": 1.5, "gates": {"G1": 0.4}},
        "requirements": [_requirement(source_data_status)],
        "events": [
            {
                "event_sequence": 1,
                "gate_id": "G1",
                "event_kind": "open",
                "planned_at": "2026-07-16T06:00:00Z",
                "target_position_m": 0.4,
                "source_flow_m3s": 0.48,
                "gate_event_sequence": 1,
                "trim_ordinal": None,
            }
        ],
        "transitions": _transitions(lifecycle=lifecycle),
        "created_by_subject": "operator-7",
        "created_at": "2026-07-16T02:00:00Z",
    }


def _ledger_payload(*, entry_status: str = "predicted_fulfilled") -> dict:
    return {
        "plan_id": PLAN_ID,
        "plan_version": PLAN_VERSION,
        "prediction_run_id": "pred-run-1",
        "prediction_status": "completed",
        "ledger_sha256": "sha256:ledger-hash",
        "entries": [
            {
                "requirement_id": "req-1",
                "section_id": "section-1",
                "checkpoint_index": 0,
                "checkpoint_at": "2026-07-17T00:00:00Z",
                "status": entry_status,
                "required_volume_m3": 800.0,
                "approved_excess_m3": 10.0,
                "delivered_m3": {
                    "lower_bound": 780.0,
                    "nominal": 800.0,
                    "upper_bound": 820.0,
                },
                "path_in_transit_m3": {
                    "lower_bound": 0.0,
                    "nominal": 0.0,
                    "upper_bound": 0.0,
                },
                "remaining_m3": {
                    "lower_bound": None,
                    "nominal": None,
                    "upper_bound": None,
                },
                "checkpoint_reasons": ["horizon_end"],
            }
        ],
        "handover": [
            {
                "gate_id": "G1",
                "requirement_ids": ["req-1"],
                "is_safe": True,
                "reasons": [],
            }
        ],
    }


# --- client stub + app builder for route tests ------------------------------
class _StubSchedulerClient:
    def __init__(
        self,
        *,
        projection: dict | None = None,
        ledger: dict | None = None,
        projection_error: Exception | None = None,
        ledger_error: Exception | None = None,
    ):
        self.projection = projection
        self.ledger = ledger
        self.projection_error = projection_error
        self.ledger_error = ledger_error
        self.calls: list[tuple] = []

    async def get_control_plan_projection(self, plan_id, plan_version, bearer_token):
        self.calls.append(("projection", str(plan_id), plan_version, bearer_token))
        if self.projection_error is not None:
            raise self.projection_error
        return self.projection

    async def get_control_plan_ledger(self, plan_id, plan_version, bearer_token):
        self.calls.append(("ledger", str(plan_id), plan_version, bearer_token))
        if self.ledger_error is not None:
            raise self.ledger_error
        return self.ledger


def _app(stub: _StubSchedulerClient) -> TestClient:
    app = FastAPI()
    app.include_router(control_plans.router)
    app.dependency_overrides[control_plans.get_scheduler_client] = lambda: stub
    return TestClient(app)


def _base(path_suffix: str = "") -> str:
    return f"/api/v1/control-plans/{PLAN_ID}/versions/{PLAN_VERSION}{path_suffix}"


# --- client layer (MockTransport) -------------------------------------------
def _transport(handler):
    captured: list[httpx.Request] = []

    def _wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    return httpx.MockTransport(_wrapped), captured


def _client(handler) -> tuple[SchedulerClient, list]:
    transport, captured = _transport(handler)
    return (
        SchedulerClient(base_url="http://scheduler.test", transport=transport),
        captured,
    )


@pytest.mark.asyncio
async def test_client_forwards_bearer_to_both_reads_at_exact_paths():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/ledger"):
            return httpx.Response(200, json=_ledger_payload(), request=request)
        return httpx.Response(200, json=_detail_payload(), request=request)

    client, captured = _client(handler)

    detail = await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)
    ledger = await client.get_control_plan_ledger(PLAN_ID, PLAN_VERSION, TOKEN)

    assert detail["plan_id"] == PLAN_ID
    assert ledger["ledger_sha256"] == "sha256:ledger-hash"
    assert [str(r.url) for r in captured] == [
        f"http://scheduler.test/api/v1/control-plans/{PLAN_ID}/versions/{PLAN_VERSION}",
        f"http://scheduler.test/api/v1/control-plans/{PLAN_ID}/versions/{PLAN_VERSION}/ledger",
    ]
    assert all(r.headers["Authorization"] == f"Bearer {TOKEN}" for r in captured)


@pytest.mark.asyncio
async def test_client_raises_not_found_with_detail_on_404():
    def handler(request):
        return httpx.Response(404, json={"detail": "plan not found"}, request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerControlPlanNotFoundError) as exc:
        await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)
    assert exc.value.detail == "plan not found"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
async def test_client_raises_auth_error_preserving_status(status):
    def handler(request):
        return httpx.Response(
            status, json={"detail": "token rejected"}, request=request
        )

    client, _ = _client(handler)
    with pytest.raises(SchedulerAuthError) as exc:
        await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)
    assert exc.value.status_code == status
    assert exc.value.detail == "token rejected"


@pytest.mark.asyncio
async def test_client_raises_unavailable_on_upstream_503_preserving_detail():
    def handler(request):
        return httpx.Response(
            503, json={"detail": "draft store is unavailable"}, request=request
        )

    client, _ = _client(handler)
    with pytest.raises(SchedulerUnavailableError) as exc:
        await client.get_control_plan_ledger(PLAN_ID, PLAN_VERSION, TOKEN)
    assert "draft store is unavailable" in str(exc.value)


@pytest.mark.asyncio
async def test_client_raises_unavailable_on_transport_failure():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerUnavailableError):
        await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)


@pytest.mark.asyncio
async def test_client_raises_contract_error_on_non_json_200():
    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>", request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerContractError):
        await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)


@pytest.mark.asyncio
async def test_client_raises_contract_error_on_non_object_200():
    def handler(request):
        return httpx.Response(200, json=[1, 2, 3], request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerContractError):
        await client.get_control_plan_ledger(PLAN_ID, PLAN_VERSION, TOKEN)


@pytest.mark.asyncio
async def test_client_raises_upstream_error_on_unexpected_status():
    def handler(request):
        return httpx.Response(500, json={"detail": "boom"}, request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerUpstreamError):
        await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)


@pytest.mark.asyncio
async def test_client_raises_contract_error_on_null_200_body():
    def handler(request):
        return httpx.Response(200, json=None, request=request)

    client, _ = _client(handler)
    with pytest.raises(SchedulerContractError):
        await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)


@pytest.mark.asyncio
async def test_client_never_logs_the_bearer_token_on_any_error_path():
    # Exercise both logging error paths (transport failure + upstream error status)
    # and assert the operator token never appears in any emitted structlog event.
    def failing_transport(request):
        raise httpx.ConnectError("connection refused", request=request)

    def erroring_status(request):
        return httpx.Response(503, json={"detail": "unavailable"}, request=request)

    for handler, expected in (
        (failing_transport, SchedulerUnavailableError),
        (erroring_status, SchedulerUnavailableError),
    ):
        client, _ = _client(handler)
        with structlog.testing.capture_logs() as logs:
            with pytest.raises(expected):
                await client.get_control_plan_projection(PLAN_ID, PLAN_VERSION, TOKEN)
        assert logs  # the path actually logged something
        assert TOKEN not in json.dumps(logs, default=str)


# --- route layer: lineage + state preservation ------------------------------
def test_bff_plan_projection_retains_exact_lineage():
    stub = _StubSchedulerClient(projection=_detail_payload())
    response = _app(stub).get(_base(), headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    # identity + content hashes
    assert body["plan_id"] == PLAN_ID
    assert body["plan_version"] == PLAN_VERSION
    assert body["input_content_hash"] == "sha256:input-hash"
    assert body["draft_content_hash"] == "sha256:draft-hash"
    # requirement + model lineage
    assert body["requirement_run_id"] == REQ_RUN_ID
    assert body["requirement_version"] == 2
    assert body["model_snapshot_id"] == "model-snap-1"
    assert body["model_release_id"] == "model-rel-1"
    assert body["model_release_content_hash"] == "sha256:model-hash"
    assert body["prediction_run_id"] == "pred-run-1"
    # per-requirement lineage
    req = body["requirements"][0]
    assert (req["requirement_id"], req["run_id"], req["source_version"]) == (
        "req-1",
        REQ_RUN_ID,
        2,
    )
    # the frozen shadow-approval document survives verbatim
    assert body["transitions"][2]["transition_document"] == SHADOW_DOCUMENT
    # the client received the forwarded operator bearer
    assert stub.calls == [("projection", PLAN_ID, PLAN_VERSION, TOKEN)]


def test_bff_preserves_unavailable_prediction_status():
    stub = _StubSchedulerClient(
        projection_error=SchedulerUnavailableError("scheduler is unavailable")
    )
    response = _app(stub).get(_base("/prediction-coverage"), headers=AUTH)

    assert response.status_code == 503
    body = response.json()
    assert set(body) == {"detail"}  # no fabricated coverage body
    assert "prediction_status" not in response.text
    assert "prediction_member_statuses" not in response.text


def test_bff_prediction_coverage_preserves_infeasible_members_without_completing():
    stub = _StubSchedulerClient(
        projection=_detail_payload(
            optimizer_status="infeasible",
            prediction_status="infeasible",
            member_status="infeasible",
        )
    )
    response = _app(stub).get(_base("/prediction-coverage"), headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["optimizer_status"] == "infeasible"
    assert body["prediction_status"] == "infeasible"
    assert [m["status"] for m in body["prediction_member_statuses"]] == [
        "infeasible",
        "infeasible",
        "infeasible",
    ]
    assert body["prediction_run_id"] == "pred-run-1"
    # coverage is a strict subset — no fabricated success/percentage vocabulary
    assert "is_complete" not in body
    assert "percentage" not in body


def test_bff_preserves_invalidated_lifecycle_in_history():
    stub = _StubSchedulerClient(projection=_detail_payload(lifecycle="invalidated"))
    response = _app(stub).get(_base("/lifecycle-history"), headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle_state"] == "invalidated"
    last = body["transitions"][-1]
    assert last["to_state"] == "invalidated"
    assert last["reason"] == "model snapshot revoked"
    assert last["transition_document"] == {
        "invalidation_cause": "model_release_revoked"
    }


def test_bff_preserves_invalidated_ledger_row_status():
    stub = _StubSchedulerClient(ledger=_ledger_payload(entry_status="invalidated"))
    response = _app(stub).get(_base("/ledger"), headers=AUTH)

    assert response.status_code == 200
    assert response.json()["entries"][0]["status"] == "invalidated"


def test_bff_preserves_null_ledger_bounds_exactly():
    stub = _StubSchedulerClient(ledger=_ledger_payload())
    response = _app(stub).get(_base("/ledger"), headers=AUTH)

    assert response.status_code == 200
    remaining = response.json()["entries"][0]["remaining_m3"]
    assert remaining == {"lower_bound": None, "nominal": None, "upper_bound": None}


def test_bff_preserves_empty_ledger_without_fabrication():
    empty = _ledger_payload()
    empty["entries"] = []
    empty["handover"] = []
    stub = _StubSchedulerClient(ledger=empty)
    response = _app(stub).get(_base("/ledger"), headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == []
    assert body["handover"] == []
    assert body["ledger_sha256"] == "sha256:ledger-hash"


def test_bff_preserves_stale_source_data_status_exactly():
    stub = _StubSchedulerClient(projection=_detail_payload(source_data_status="stale"))
    response = _app(stub).get(_base(), headers=AUTH)

    assert response.status_code == 200
    assert response.json()["requirements"][0]["source_data_status"] == "stale"


# --- route layer: auth + fail-closed error mapping --------------------------
@pytest.mark.parametrize(
    "suffix",
    ["", "/prediction-coverage", "/ledger", "/lifecycle-history"],
)
def test_all_routes_reject_missing_bearer(suffix):
    stub = _StubSchedulerClient(projection=_detail_payload(), ledger=_ledger_payload())
    response = _app(stub).get(_base(suffix))  # no Authorization header
    assert response.status_code == 403
    assert stub.calls == []  # scheduler never contacted without a bearer


def test_scheduler_auth_failure_reaches_caller_with_same_status():
    stub = _StubSchedulerClient(
        projection_error=SchedulerAuthError(401, "token expired")
    )
    response = _app(stub).get(_base(), headers=AUTH)
    assert response.status_code == 401
    assert response.json() == {"detail": "token expired"}


def test_not_found_maps_to_404_retaining_detail():
    stub = _StubSchedulerClient(
        projection_error=SchedulerControlPlanNotFoundError("plan not found")
    )
    response = _app(stub).get(_base(), headers=AUTH)
    assert response.status_code == 404
    assert response.json() == {"detail": "plan not found"}


def test_malformed_scheduler_contract_yields_502_without_partial_projection():
    broken = _detail_payload()
    del broken["draft_content_hash"]  # drop a required lineage field
    stub = _StubSchedulerClient(projection=broken)
    response = _app(stub).get(_base(), headers=AUTH)

    assert response.status_code == 502
    assert set(response.json()) == {"detail"}
    assert "draft_content_hash" not in response.text


def test_unknown_extra_field_fails_closed_502():
    drifted = _detail_payload()
    drifted["surprise_new_field"] = "unexpected"
    stub = _StubSchedulerClient(projection=drifted)
    response = _app(stub).get(_base(), headers=AUTH)
    assert response.status_code == 502


def test_upstream_error_maps_to_502():
    stub = _StubSchedulerClient(
        projection_error=SchedulerUpstreamError(
            "scheduler returned an unexpected status 500"
        )
    )
    response = _app(stub).get(_base(), headers=AUTH)
    assert response.status_code == 502


def test_numeric_string_integer_field_fails_closed_502():
    # `extra="forbid"` alone would let Pydantic coerce "3" -> 3; the strict scalar
    # aliases must reject it as drift instead of laundering it into valid lineage.
    drifted = _detail_payload()
    drifted["plan_version"] = "3"
    stub = _StubSchedulerClient(projection=drifted)
    response = _app(stub).get(_base(), headers=AUTH)
    assert response.status_code == 502


def test_boolean_integer_field_fails_closed_502():
    drifted = _detail_payload()
    drifted["requirement_version"] = True  # would lax-coerce to 1
    stub = _StubSchedulerClient(projection=drifted)
    response = _app(stub).get(_base(), headers=AUTH)
    assert response.status_code == 502


def test_boolean_for_float_field_fails_closed_502():
    drifted = _detail_payload()
    drifted["requirements"][0]["required_volume_m3"] = True
    stub = _StubSchedulerClient(projection=drifted)
    response = _app(stub).get(_base(), headers=AUTH)
    assert response.status_code == 502


def test_string_for_float_ledger_bound_fails_closed_502():
    drifted = _ledger_payload()
    drifted["entries"][0]["delivered_m3"]["nominal"] = "800.0"
    stub = _StubSchedulerClient(ledger=drifted)
    response = _app(stub).get(_base("/ledger"), headers=AUTH)
    assert response.status_code == 502


def test_mismatched_plan_id_fails_closed_502():
    # The scheduler returns a structurally valid document for a DIFFERENT plan
    # (e.g. an upstream cache/routing defect); the BFF must not serve it as 200.
    other_plan = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    stub = _StubSchedulerClient(projection=_detail_payload())  # carries PLAN_ID
    response = _app(stub).get(
        f"/api/v1/control-plans/{other_plan}/versions/{PLAN_VERSION}", headers=AUTH
    )
    assert response.status_code == 502
    assert PLAN_ID not in response.text  # no wrong-plan body leaked


def test_mismatched_plan_version_fails_closed_502():
    stub = _StubSchedulerClient(projection=_detail_payload())  # carries version 3
    response = _app(stub).get(
        f"/api/v1/control-plans/{PLAN_ID}/versions/5", headers=AUTH
    )
    assert response.status_code == 502


def test_ledger_mismatched_identity_fails_closed_502():
    stub = _StubSchedulerClient(ledger=_ledger_payload())  # carries version 3
    response = _app(stub).get(
        f"/api/v1/control-plans/{PLAN_ID}/versions/9/ledger", headers=AUTH
    )
    assert response.status_code == 502


def test_invalid_plan_version_rejected_before_scheduler_call():
    stub = _StubSchedulerClient(projection=_detail_payload())
    response = _app(stub).get(
        f"/api/v1/control-plans/{PLAN_ID}/versions/0", headers=AUTH
    )
    assert response.status_code == 422
    assert stub.calls == []


# --- router shape + wiring ---------------------------------------------------
def test_router_exposes_only_read_operations():
    methods = set()
    for route in control_plans.router.routes:
        methods |= {m for m in route.methods if m not in {"HEAD", "OPTIONS"}}
    assert methods == {"GET"}


def test_openapi_advertises_no_list_route():
    app = FastAPI()
    app.include_router(control_plans.router)
    paths = app.openapi()["paths"]
    template = "/api/v1/control-plans/{plan_id}/versions/{plan_version}"
    assert "/api/v1/control-plans" not in paths
    assert template in paths
    assert f"{template}/prediction-coverage" in paths
    assert f"{template}/ledger" in paths
    assert f"{template}/lifecycle-history" in paths


def test_main_registers_all_four_projection_routes():
    main = importlib.import_module("main")
    template_paths = {getattr(route, "path", None) for route in main.app.routes}
    assert {
        "/api/v1/control-plans/{plan_id}/versions/{plan_version}",
        "/api/v1/control-plans/{plan_id}/versions/{plan_version}/prediction-coverage",
        "/api/v1/control-plans/{plan_id}/versions/{plan_version}/ledger",
        "/api/v1/control-plans/{plan_id}/versions/{plan_version}/lifecycle-history",
    }.issubset(template_paths)
