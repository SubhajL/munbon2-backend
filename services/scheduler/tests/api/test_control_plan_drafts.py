"""Control-plans API: auth, replay semantics, exact GET, error mapping."""

from functools import partial
from uuid import uuid4

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
from services.control_plan_lifecycle_service import (
    ControlPlanLifecycleService,
)

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

    def override_lifecycle():
        return ControlPlanLifecycleService(repository=repository)

    app.dependency_overrides[
        control_plans.get_control_plan_service
    ] = override_service
    app.dependency_overrides[
        control_plans.get_lifecycle_service
    ] = override_lifecycle
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


class TestLedgerEndpoint:
    def test_ledger_returns_entries_bounds_and_lineage(self):
        app, _ = _build_app()
        client = TestClient(app)
        created = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert created.status_code == 201, created.text
        plan_id = created.json()["plan_id"]

        ledger = client.get(
            f"/api/v1/control-plans/{plan_id}/versions/1/ledger"
        )
        assert ledger.status_code == 200, ledger.text
        body = ledger.json()
        assert body["plan_id"] == plan_id
        assert body["prediction_status"] == "completed"
        assert len(body["ledger_sha256"]) == 64
        assert body["entries"], "feasible draft must expose ledger entries"
        first = body["entries"][0]
        allowed = {
            "not_started",
            "predicted_in_progress",
            "predicted_fulfilled",
            "predicted_excess_risk",
            "invalidated",
            "manual_review",
        }
        assert all(e["status"] in allowed for e in body["entries"])
        assert "lower_bound" in first["delivered_m3"]
        assert body["handover"], "scheduled requirement must get a verdict"

    def test_ledger_requires_auth(self):
        app, _ = _build_app()
        del app.dependency_overrides[get_current_user]
        client = TestClient(app)
        response = client.get(
            f"/api/v1/control-plans/{uuid4()}/versions/1/ledger"
        )
        assert response.status_code == 403

    def test_ledger_unknown_plan_is_404(self):
        app, _ = _build_app()
        client = TestClient(app)
        response = client.get(
            f"/api/v1/control-plans/{uuid4()}/versions/1/ledger"
        )
        assert response.status_code == 404


class TestLifecycleEndpoints:
    def _create(self, client):
        created = client.post(
            "/api/v1/control-plans/drafts", json=draft_payload()
        )
        assert created.status_code == 201, created.text
        return created.json()["plan_id"]

    def test_review_then_approve_advances_derived_state(self):
        app, _ = _build_app()
        client = TestClient(app)
        plan_id = self._create(client)
        base = f"/api/v1/control-plans/{plan_id}/versions/1"

        review = client.post(f"{base}/review", json={})
        assert review.status_code == 200, review.text
        assert review.json()["lifecycle_state"] == "under_review"

        approve = client.post(f"{base}/approve-for-shadow", json={})
        assert approve.status_code == 200, approve.text
        body = approve.json()
        assert body["lifecycle_state"] == "approved_for_shadow"
        freeze = next(
            t["transition_document"]
            for t in body["transitions"]
            if t["transition_type"] == "shadow_approved"
        )
        assert freeze["machine_authority_granted"] is False

    def test_approve_without_review_is_409(self):
        app, _ = _build_app()
        client = TestClient(app)
        plan_id = self._create(client)
        response = client.post(
            f"/api/v1/control-plans/{plan_id}/versions/1/approve-for-shadow",
            json={},
        )
        assert response.status_code == 409

    def test_cancel_requires_reason(self):
        app, _ = _build_app()
        client = TestClient(app)
        plan_id = self._create(client)
        missing = client.post(
            f"/api/v1/control-plans/{plan_id}/versions/1/cancel", json={}
        )
        assert missing.status_code == 422
        ok = client.post(
            f"/api/v1/control-plans/{plan_id}/versions/1/cancel",
            json={"reason": "operator abort"},
        )
        assert ok.status_code == 200
        assert ok.json()["lifecycle_state"] == "cancelled"

    def test_coverage_rejection_maps_to_409(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(), infeasible_members={"lower"}
        )
        app, _ = _build_app(flow=flow)
        client = TestClient(app)
        plan_id = self._create(client)
        base = f"/api/v1/control-plans/{plan_id}/versions/1"
        assert client.post(f"{base}/review", json={}).status_code == 200
        approve = client.post(f"{base}/approve-for-shadow", json={})
        assert approve.status_code == 409

    def test_lifecycle_routes_require_auth(self):
        app, _ = _build_app()
        plan_id = self._create(TestClient(app))
        del app.dependency_overrides[get_current_user]
        client = TestClient(app)
        for action in ("review", "approve-for-shadow"):
            r = client.post(
                f"/api/v1/control-plans/{plan_id}/versions/1/{action}", json={}
            )
            assert r.status_code == 403

    def test_unknown_plan_is_404(self):
        app, _ = _build_app()
        client = TestClient(app)
        r = client.post(
            f"/api/v1/control-plans/{uuid4()}/versions/1/review", json={}
        )
        assert r.status_code == 404
