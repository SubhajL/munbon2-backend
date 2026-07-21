"""Control-plans API: auth, RBAC, replay semantics, exact GET, error mapping."""

import json
from functools import partial
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from api.middleware.request_id import RequestIDMiddleware
from api.v1.endpoints import control_plans
from api.v1.operator_controls import (
    get_auth_step_up_client,
    get_scada_operator_client,
)
from core import deps
from core.deps import get_current_user, get_db, get_redis
from services.clients.control_client_errors import (
    UpstreamContractViolation,
    UpstreamUnavailableError,
)
from services.clients.auth_step_up_client import StepUpUnavailableError
from services.control_plan_service import ControlPlanDraftService
from services.control_plan_lifecycle_service import (
    ControlPlanLifecycleService,
)

from tests.control_plan_test_support import (
    FakeControlFlowClient,
    FakeReadProjectionRepository,
    FakeRepository,
    FakeRosGisClient,
    draft_payload,
    requirement_item,
    snapshot_mirror,
)

# Role-bearing principals as get_current_user would return them (the raw JWT
# payload shape). A supervisor satisfies require_operator via the hierarchy.
_OPERATOR = {"sub": "operator-1", "roles": ["operator"], "iss": "munbon-auth"}
_SUPERVISOR = {
    "sub": "supervisor-1",
    "roles": ["supervisor"],
    "jti": "jti-approve",
    "iss": "munbon-auth",
}
_APPROVAL_BODY = {"reason": "coverage verified", "evidence_refs": ["ticket-77"]}


class _StepUpClient:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def verify_step_up(self, access_token, code):
        self.calls.append((access_token, code))
        if self.error is not None:
            raise self.error


class _ScadaClient:
    def __init__(self, snapshot, error=None):
        self.snapshot = snapshot
        self.error = error
        self.calls = []

    async def is_healthy(self):
        self.calls.append("health")
        if self.error is not None:
            raise self.error
        return True

    async def get_device_capabilities(self, access_token):
        self.calls.append(("capabilities", access_token))
        if self.error is not None:
            raise self.error
        return self.snapshot


class _ReplayStore:
    def __init__(self):
        self.keys = set()

    async def set_if_absent(self, key, value, *, expire):
        if key in self.keys:
            return False
        self.keys.add(key)
        return True


def _build_app(
    flow=None,
    repository=None,
    user=None,
    *,
    step_up_client=None,
    scada_client=None,
):
    app = FastAPI()
    replay_store = _ReplayStore()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(control_plans.router, prefix="/api/v1/control-plans")
    app.state.optimize_limited_adjustment_plan = partial(
        optimize_limited_adjustment_plan,
        model_step_seconds=3600,
        max_intermediate_trims=1,
        solver_timeout_seconds=60,
    )
    app.state.device_capability_snapshot = None
    repository = repository if repository is not None else FakeRepository()
    flow = flow if flow is not None else FakeControlFlowClient(snapshot_mirror())

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

    app.dependency_overrides[control_plans.get_control_plan_service] = override_service
    app.dependency_overrides[control_plans.get_lifecycle_service] = override_lifecycle
    # The bounded ledger/coverage/history reads go through the projection
    # repository; back it with the SAME in-memory records the draft POST stores.
    app.dependency_overrides[
        control_plans.get_control_plan_projection_repository
    ] = lambda: FakeReadProjectionRepository(repository)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: replay_store
    app.dependency_overrides[get_auth_step_up_client] = lambda: (
        step_up_client or _StepUpClient()
    )
    app.dependency_overrides[get_scada_operator_client] = lambda: scada_client
    app.dependency_overrides[get_current_user] = lambda: (
        user
        if user is not None
        # Default principal is admin-roled so non-RBAC roundtrip tests exercise
        # the handler; RBAC-specific tests inject explicit principals via _as_user.
        else {"sub": "operator-1", "roles": ["admin"]}
    )
    return app, repository


def _positive_headers(action, identity, version):
    return {
        "Authorization": "Bearer operator-access-token",
        "X-Operator-Confirmation": f"{action.upper()} {identity} v{version}",
        "X-Operator-Step-Up-Code": "123456",
    }


def _as_user(app, user):
    app.dependency_overrides[get_current_user] = lambda: user


class TestAuth:
    def test_routes_require_a_bearer_token(self):
        app, _ = _build_app()
        del app.dependency_overrides[get_current_user]
        client = TestClient(app)
        response = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert response.status_code == 403  # HTTPBearer: no credentials
        response = client.get(f"/api/v1/control-plans/{uuid4()}/versions/1")
        assert response.status_code == 403

    def test_token_without_subject_is_401(self):
        app, _ = _build_app()
        # Carries a role (so RBAC passes) but no subject: the handler's defensive
        # _actor_subject check must still reject it as 401.
        app.dependency_overrides[get_current_user] = lambda: {"roles": ["admin"]}
        client = TestClient(app)
        response = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert response.status_code == 401


class TestDraftRoundtrip:
    def test_post_creates_then_replays_then_gets_exact_version(self):
        app, _ = _build_app()
        client = TestClient(app)

        created = client.post("/api/v1/control-plans/drafts", json=draft_payload())
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

        replayed = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert replayed.status_code == 200
        assert replayed.headers["Idempotent-Replay"] == "true"
        assert replayed.json()["plan_id"] == body["plan_id"]

        fetched = client.get(f"/api/v1/control-plans/{body['plan_id']}/versions/1")
        assert fetched.status_code == 200
        assert fetched.json() == body

    def test_unknown_plan_version_is_404(self):
        app, _ = _build_app()
        client = TestClient(app)
        response = client.get(f"/api/v1/control-plans/{uuid4()}/versions/1")
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
        response = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert response.status_code == 503
        assert repository.by_input_hash == {}

    def test_binding_gap_maps_to_422(self):
        app, _ = _build_app()
        client = TestClient(app)
        payload = draft_payload()
        payload["section_bindings"] = []
        response = client.post("/api/v1/control-plans/drafts", json=payload)
        assert response.status_code == 422
        assert "binding" in response.json()["detail"]

    def test_prediction_contract_violation_maps_to_502(self):
        flow = FakeControlFlowClient(
            snapshot_mirror(),
            prediction_error=UpstreamContractViolation("malformed members"),
        )
        app, repository = _build_app(flow=flow)
        client = TestClient(app)
        response = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert response.status_code == 502
        assert repository.by_input_hash == {}

    def test_incomplete_branch_allocation_maps_to_422(self):
        app, _ = _build_app()
        client = TestClient(app)
        payload = draft_payload()
        payload["branch_allocations"] = []
        response = client.post("/api/v1/control-plans/drafts", json=payload)
        assert response.status_code == 422


class TestLedgerEndpoint:
    def test_ledger_returns_entries_bounds_and_lineage(self):
        app, _ = _build_app()
        client = TestClient(app)
        created = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert created.status_code == 201, created.text
        plan_id = created.json()["plan_id"]

        ledger = client.get(f"/api/v1/control-plans/{plan_id}/versions/1/ledger")
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
        response = client.get(f"/api/v1/control-plans/{uuid4()}/versions/1/ledger")
        assert response.status_code == 403

    def test_ledger_unknown_plan_is_404(self):
        app, _ = _build_app()
        client = TestClient(app)
        response = client.get(f"/api/v1/control-plans/{uuid4()}/versions/1/ledger")
        assert response.status_code == 404


class TestLifecycleEndpoints:
    def _create(self, client):
        created = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert created.status_code == 201, created.text
        return created.json()["plan_id"]

    def test_review_then_approve_advances_derived_state(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        app, _ = _build_app(user=_SUPERVISOR)
        client = TestClient(app)
        plan_id = self._create(client)
        base = f"/api/v1/control-plans/{plan_id}/versions/1"

        review = client.post(f"{base}/review", json={})
        assert review.status_code == 200, review.text
        assert review.json()["lifecycle_state"] == "under_review"

        approve = client.post(
            f"{base}/approve-for-shadow",
            json=_APPROVAL_BODY,
            headers=_positive_headers("approve-shadow", plan_id, 1),
        )
        assert approve.status_code == 200, approve.text
        body = approve.json()
        assert body["lifecycle_state"] == "approved_for_shadow"
        document = next(
            t["transition_document"]
            for t in body["transitions"]
            if t["transition_type"] == "shadow_approved"
        )
        assert document["schema_version"] == 2
        assert document["lineage_freeze"]["machine_authority_granted"] is False
        assert document["authorization_evidence"]["claim_policy_mode"] == ("strict")

    def test_approve_without_review_is_409(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        app, _ = _build_app(user=_SUPERVISOR)
        client = TestClient(app)
        plan_id = self._create(client)
        response = client.post(
            f"/api/v1/control-plans/{plan_id}/versions/1/approve-for-shadow",
            json=_APPROVAL_BODY,
            headers=_positive_headers("approve-shadow", plan_id, 1),
        )
        assert response.status_code == 409

    def test_cancel_requires_reason(self):
        app, _ = _build_app(user=_SUPERVISOR)
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

    def test_coverage_rejection_maps_to_409(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        flow = FakeControlFlowClient(snapshot_mirror(), infeasible_members={"lower"})
        app, _ = _build_app(flow=flow, user=_SUPERVISOR)
        client = TestClient(app)
        plan_id = self._create(client)
        base = f"/api/v1/control-plans/{plan_id}/versions/1"
        assert client.post(f"{base}/review", json={}).status_code == 200
        approve = client.post(
            f"{base}/approve-for-shadow",
            json=_APPROVAL_BODY,
            headers=_positive_headers("approve-shadow", plan_id, 1),
        )
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
        r = client.post(f"/api/v1/control-plans/{uuid4()}/versions/1/review", json={})
        assert r.status_code == 404


class TestHoldAndResumeGuards:
    class _OpenLoop:
        def __init__(self):
            self.calls = []

        async def hold_control_plan(self, db, plan_id, plan_version, actor, reason):
            self.calls.append(("hold", plan_id, plan_version, actor, reason))

        async def resume_control_plan(self, db, plan_id, plan_version, actor, reason):
            self.calls.append(("resume", plan_id, plan_version, actor, reason))

    def test_hold_is_confirmation_only_and_remains_available(self):
        app, _ = _build_app(user=_SUPERVISOR)
        service = self._OpenLoop()
        app.dependency_overrides[control_plans.get_open_loop_service] = lambda: service
        client = TestClient(app)
        plan_id = uuid4()
        url = f"/api/v1/control-plans/{plan_id}/versions/2/hold"

        missing = client.post(url, json={"reason": "safety stop"})
        held = client.post(
            url,
            json={"reason": "safety stop"},
            headers={"X-Operator-Confirmation": f"HOLD {plan_id} v2"},
        )

        assert missing.status_code == 400
        assert held.status_code == 200
        assert service.calls == [
            ("hold", plan_id, 2, _SUPERVISOR["sub"], "safety stop")
        ]

    def test_resume_requires_totp_and_matching_live_scada(self):
        snapshot = SimpleNamespace(
            capability_release_id="release-1",
            capability_hash="c" * 64,
            capabilities={"G1": object()},
        )
        step_up = _StepUpClient()
        scada = _ScadaClient(snapshot)
        app, _ = _build_app(
            user=_SUPERVISOR,
            step_up_client=step_up,
            scada_client=scada,
        )
        app.state.device_capability_snapshot = snapshot
        service = self._OpenLoop()
        app.dependency_overrides[control_plans.get_open_loop_service] = lambda: service
        client = TestClient(app)
        plan_id = uuid4()
        url = f"/api/v1/control-plans/{plan_id}/versions/2/resume"

        resumed = client.post(
            url,
            json={"reason": "checks restored"},
            headers=_positive_headers("resume", plan_id, 2),
        )

        assert resumed.status_code == 200
        assert step_up.calls == [("operator-access-token", "123456")]
        assert scada.calls == [
            "health",
            ("capabilities", "operator-access-token"),
        ]
        assert service.calls == [
            ("resume", plan_id, 2, _SUPERVISOR["sub"], "checks restored")
        ]


class TestRbacMatrix:
    """The RBAC matrix is enforced per action (strict mode = production posture:
    a present-but-insufficient role is 403; role-less is 403)."""

    def _draft(self, client):
        created = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert created.status_code == 201, created.text
        return created.json()["plan_id"]

    def test_control_plan_role_matrix_enforced_per_action(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        app, _ = _build_app(user=_SUPERVISOR)
        client = TestClient(app)
        # An operator can create the draft (require_operator) ...
        _as_user(app, _OPERATOR)
        plan_id = self._draft(client)
        base = f"/api/v1/control-plans/{plan_id}/versions/1"

        # ... but an operator cannot drive any supervisor-gated action.
        _as_user(app, _OPERATOR)
        assert client.post(f"{base}/review", json={}).status_code == 403
        assert (
            client.post(f"{base}/approve-for-shadow", json=_APPROVAL_BODY).status_code
            == 403
        )
        assert (
            client.post(f"{base}/invalidate", json={"reason": "x"}).status_code == 403
        )
        assert (
            client.post(
                f"{base}/supersede",
                json={
                    "successor_plan_id": str(uuid4()),
                    "successor_plan_version": 1,
                    "reason": "roll",
                },
            ).status_code
            == 403
        )

        # A field_team token (present but too low) cannot even read a draft.
        _as_user(app, {"sub": "ft-1", "roles": ["field_team"]})
        assert client.get(base).status_code == 403

        # A supervisor can review.
        _as_user(app, _SUPERVISOR)
        assert client.post(f"{base}/review", json={}).status_code == 200

    def test_operator_can_cancel_but_not_invalidate(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        app, _ = _build_app(user=_OPERATOR)
        client = TestClient(app)
        plan_id = self._draft(client)
        base = f"/api/v1/control-plans/{plan_id}/versions/1"
        # invalidate is supervisor-gated: an operator is 403.
        assert (
            client.post(f"{base}/invalidate", json={"reason": "x"}).status_code == 403
        )
        # cancel is operator-gated (per the RBAC matrix): an operator succeeds.
        assert (
            client.post(f"{base}/cancel", json={"reason": "withdraw"}).status_code
            == 200
        )


class TestApproveForShadowStrictPolicy:
    def _reviewed_plan(self, client):
        created = client.post("/api/v1/control-plans/drafts", json=draft_payload())
        assert created.status_code == 201, created.text
        plan_id = created.json()["plan_id"]
        base = f"/api/v1/control-plans/{plan_id}/versions/1"
        assert client.post(f"{base}/review", json={}).status_code == 200
        return base

    def test_scheduler_enforces_exact_confirmation_and_totp(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        step_up = _StepUpClient()
        app, _ = _build_app(user=_SUPERVISOR, step_up_client=step_up)
        client = TestClient(app)
        base = self._reviewed_plan(client)
        plan_id = base.split("/")[-3]

        missing = client.post(f"{base}/approve-for-shadow", json=_APPROVAL_BODY)
        approved = client.post(
            f"{base}/approve-for-shadow",
            json=_APPROVAL_BODY,
            headers=_positive_headers("approve-shadow", plan_id, 1),
        )

        assert missing.status_code == 400
        assert approved.status_code == 200
        assert step_up.calls == [("operator-access-token", "123456")]

    def test_scheduler_fails_closed_when_totp_is_unavailable(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        step_up = _StepUpClient(StepUpUnavailableError("auth down"))
        app, _ = _build_app(user=_SUPERVISOR, step_up_client=step_up)
        client = TestClient(app)
        base = self._reviewed_plan(client)
        plan_id = base.split("/")[-3]

        response = client.post(
            f"{base}/approve-for-shadow",
            json=_APPROVAL_BODY,
            headers=_positive_headers("approve-shadow", plan_id, 1),
        )

        assert response.status_code == 503

    def test_approve_for_shadow_requires_strict_policy(self, monkeypatch):
        app, _ = _build_app(user=_SUPERVISOR)
        client = TestClient(app)
        base = self._reviewed_plan(client)

        # Compat: the strict-policy guard makes approval UNAVAILABLE (503) so a
        # compat token can never mint a trusted approval.
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "compat")
        compat = client.post(f"{base}/approve-for-shadow", json=_APPROVAL_BODY)
        assert compat.status_code == 503

        # Strict: the guard opens and the approval proceeds.
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        plan_id = base.split("/")[-3]
        strict = client.post(
            f"{base}/approve-for-shadow",
            json=_APPROVAL_BODY,
            headers=_positive_headers("approve-shadow", plan_id, 1),
        )
        assert strict.status_code == 200, strict.text
        assert strict.json()["lifecycle_state"] == "approved_for_shadow"

    def test_approve_for_shadow_requires_reason_and_evidence_refs(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        app, _ = _build_app(user=_SUPERVISOR)
        client = TestClient(app)
        base = self._reviewed_plan(client)

        missing_reason = client.post(
            f"{base}/approve-for-shadow", json={"evidence_refs": ["t-1"]}
        )
        assert missing_reason.status_code == 422
        empty_refs = client.post(
            f"{base}/approve-for-shadow",
            json={"reason": "ok", "evidence_refs": []},
        )
        assert empty_refs.status_code == 422
        blank_ref = client.post(
            f"{base}/approve-for-shadow",
            json={"reason": "ok", "evidence_refs": ["  "]},
        )
        assert blank_ref.status_code == 422

    def test_approve_for_shadow_caps_reason_and_evidence_ref_length(self, monkeypatch):
        # The bounded list projection later loads this shadow-approval document per
        # row, so its inputs are length-capped AT THE SOURCE: an over-long reason
        # (>2000) or evidence ref (>200) is a 422, never a giant persisted document.
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        app, _ = _build_app(user=_SUPERVISOR)
        client = TestClient(app)
        base = self._reviewed_plan(client)

        oversized_ref = client.post(
            f"{base}/approve-for-shadow",
            json={"reason": "ok", "evidence_refs": ["x" * 201]},
        )
        assert oversized_ref.status_code == 422
        oversized_reason = client.post(
            f"{base}/approve-for-shadow",
            json={"reason": "y" * 2001, "evidence_refs": ["t-1"]},
        )
        assert oversized_reason.status_code == 422
        # A ref at exactly the 200-char cap is accepted (boundary) — none of the
        # rejected attempts advanced the plan, so this approval still succeeds.
        at_cap = client.post(
            f"{base}/approve-for-shadow",
            json={"reason": "ok", "evidence_refs": ["z" * 200]},
            headers=_positive_headers("approve-shadow", base.split("/")[-3], 1),
        )
        assert at_cap.status_code == 200, at_cap.text

    def test_approval_persists_authorization_evidence(self, monkeypatch):
        monkeypatch.setattr(deps.settings, "jwt_claim_policy_mode", "strict")
        app, repository = _build_app(user=_SUPERVISOR)
        client = TestClient(app)
        base = self._reviewed_plan(client)
        plan_id = base.split("/")[-3]

        approve = client.post(
            f"{base}/approve-for-shadow",
            json=_APPROVAL_BODY,
            headers=_positive_headers("approve-shadow", plan_id, 1),
        )
        assert approve.status_code == 200, approve.text

        record = repository.by_key[(UUID(plan_id), 1)]
        approval = next(
            t for t in record.transitions if t.transition_type == "shadow_approved"
        )
        document = json.loads(approval.transition_document_text)
        assert document["schema_version"] == 2
        evidence = document["authorization_evidence"]
        assert evidence["subject"] == _SUPERVISOR["sub"]
        assert evidence["claim_policy_mode"] == "strict"
        assert evidence["authorization_policy_version"] == "control-plan-rbac-v1"
        assert evidence["evidence_refs"] == _APPROVAL_BODY["evidence_refs"]
        # A safe correlation id was captured, and the raw jti never leaked.
        assert isinstance(evidence["request_id"], str) and evidence["request_id"]
        assert _SUPERVISOR["jti"] not in json.dumps(document)
