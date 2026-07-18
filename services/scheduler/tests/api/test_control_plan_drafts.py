"""Control-plans API: auth, replay semantics, exact GET, error mapping."""

import json
from datetime import date, datetime, timezone
from functools import partial
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from api.v1.endpoints import control_plans
from core.deps import get_current_user, get_db
from services.clients.control_client_errors import (
    UpstreamContractViolation,
    UpstreamUnavailableError,
)
from services.control_plan_service import ControlPlanDraftService

from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)


def _build_app(flow=None, repository=None):
    app = FastAPI()
    app.include_router(control_plans.router, prefix="/api/v1/control-plans")
    app.state.optimize_limited_adjustment_plan = partial(
        optimize_limited_adjustment_plan,
        model_step_seconds=3600,
        max_intermediate_trims=1,
        solver_timeout_seconds=60,
    )
    repository = repository if repository is not None else FakeRepository()
    flow = flow if flow is not None else FakeControlFlowClient(
        snapshot_mirror()
    )

    async def run_blocking(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def override_service():
        yield ControlPlanDraftService(
            ros_client=FakeRosGisClient([requirement_item()]),
            flow_client=flow,
            repository=repository,
            optimizer=app.state.optimize_limited_adjustment_plan,
            run_blocking=run_blocking,
            model_step_seconds=3600,
            max_intermediate_trims=1,
            solver_timeout_seconds=60,
        )

    async def override_db():
        yield None

    app.dependency_overrides[
        control_plans.get_control_plan_service
    ] = override_service
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: {"sub": "operator-1"}
    return app, repository


class TestAuth:
    def test_routes_require_a_bearer_token(self):
        app, _ = _build_app()
        del app.dependency_overrides[get_current_user]
        client = TestClient(app)
        response = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert response.status_code == 403  # HTTPBearer: no credentials
        response = client.get(
            f"/api/v1/control-plans/{uuid4()}/versions/1"
        )
        assert response.status_code == 403

    def test_token_without_subject_is_401(self):
        app, _ = _build_app()
        app.dependency_overrides[get_current_user] = lambda: {}
        client = TestClient(app)
        response = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert response.status_code == 401


class TestDraftRoundtrip:
    def test_post_creates_then_replays_then_gets_exact_version(self):
        app, _ = _build_app()
        client = TestClient(app)

        created = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert created.status_code == 201, created.text
        assert created.headers["Idempotent-Replay"] == "false"
        body = created.json()
        assert body["lifecycle_state"] == "draft"
        assert body["optimizer_status"] == "feasible"
        assert body["prediction_status"] == "completed"
        assert body["created_by_subject"] == "operator-1"
        assert body["transitions"][0]["transition_type"] == "draft_created"
        assert body["requirements"][0]["planning_disposition"] == "scheduled"
        assert body["events"], "feasible draft must expose gate events"

        replayed = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert replayed.status_code == 200
        assert replayed.headers["Idempotent-Replay"] == "true"
        assert replayed.json()["plan_id"] == body["plan_id"]

        fetched = client.get(
            f"/api/v1/control-plans/{body['plan_id']}/versions/1"
        )
        assert fetched.status_code == 200
        assert fetched.json() == body

    def test_unknown_plan_version_is_404(self):
        app, _ = _build_app()
        client = TestClient(app)
        response = client.get(
            f"/api/v1/control-plans/{uuid4()}/versions/1"
        )
        assert response.status_code == 404

    def test_unknown_request_field_is_422(self):
        app, _ = _build_app()
        client = TestClient(app)
        response = client.post(
            "/api/v1/control-plans/drafts",
            json={**draft_payload(), "surprise": 1},
        )
        assert response.status_code == 422

    def test_upstream_unavailable_maps_to_503(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(),
            snapshot_error=UpstreamUnavailableError("flow is down"),
        )
        app, repository = _build_app(flow=flow)
        client = TestClient(app)
        response = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert response.status_code == 503
        assert repository.by_input_hash == {}

    def test_binding_gap_maps_to_422(self):
        app, _ = _build_app()
        client = TestClient(app)
        payload = draft_payload()
        payload["section_bindings"] = []
        response = client.post(
            "/api/v1/control-plans/drafts", json=payload
        )
        assert response.status_code == 422
        assert "binding" in response.json()["detail"]

    def test_prediction_contract_violation_maps_to_502(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(),
            prediction_error=UpstreamContractViolation("malformed members"),
        )
        app, repository = _build_app(flow=flow)
        client = TestClient(app)
        response = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert response.status_code == 502
        assert repository.by_input_hash == {}

    def test_incomplete_branch_allocation_maps_to_422(self):
        app, _ = _build_app()
        client = TestClient(app)
        payload = draft_payload()
        payload["branch_allocations"] = []
        response = client.post(
            "/api/v1/control-plans/drafts", json=payload
        )
        assert response.status_code == 422
