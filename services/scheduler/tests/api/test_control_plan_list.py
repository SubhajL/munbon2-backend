"""Control-plans LIST route: RBAC, bounded projection, cursor 422 (PR 4.4a-3)."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.request_id import RequestIDMiddleware
from api.v1.endpoints import control_plans
from core.deps import get_current_user, get_db
from tests.control_plan_test_support import (
    TRUSTED_APPROVAL_DOCUMENT,
    FakeControlPlanProjectionRepository,
    projection_record,
)

_OPERATOR = {"sub": "operator-1", "roles": ["operator"], "iss": "munbon-auth"}
_FIELD_TEAM = {"sub": "ft-1", "roles": ["field_team"]}

_IDS = [UUID(f"{n:08x}-0000-4000-8000-000000000000") for n in range(1, 6)]


def _records():
    base = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)
    return [
        projection_record(plan_id, created_at=base.replace(minute=i))
        for i, plan_id in enumerate(_IDS)
    ]


def _build_app(records=None, user=None):
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.include_router(control_plans.router, prefix="/api/v1/control-plans")
    repo = FakeControlPlanProjectionRepository(
        records if records is not None else _records()
    )

    async def override_db():
        yield None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[
        control_plans.get_control_plan_projection_repository
    ] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: (
        user if user is not None else _OPERATOR
    )
    return app, repo


class TestListRbac:
    def test_list_route_requires_operator_role(self):
        # An operator can list ...
        app, _ = _build_app(user=_OPERATOR)
        assert TestClient(app).get("/api/v1/control-plans").status_code == 200

        # ... a present-but-insufficient field_team token is 403 ...
        app, _ = _build_app(user=_FIELD_TEAM)
        assert TestClient(app).get("/api/v1/control-plans").status_code == 403

        # ... and no bearer at all is 403 (HTTPBearer).
        app, _ = _build_app()
        del app.dependency_overrides[get_current_user]
        assert TestClient(app).get("/api/v1/control-plans").status_code == 403


class TestListProjection:
    def test_list_returns_bounded_summaries_ordered_desc(self):
        app, _ = _build_app()
        response = TestClient(app).get("/api/v1/control-plans?limit=25")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["projection_schema_version"] == 2
        assert body["next_cursor"] is None
        # created_at DESC, plan_id DESC.
        created = [item["created_at"] for item in body["items"]]
        assert created == sorted(created, reverse=True)
        assert len(body["items"]) == len(_IDS)

    def test_list_summary_omits_all_large_documents(self):
        app, _ = _build_app(
            records=[
                projection_record(
                    _IDS[0],
                    created_at=datetime(2026, 7, 18, 8, tzinfo=timezone.utc),
                    lifecycle="approved_for_shadow",
                    approval_document=TRUSTED_APPROVAL_DOCUMENT,
                )
            ]
        )
        item = TestClient(app).get("/api/v1/control-plans").json()["items"][0]
        # The header projection carries the derived fields ...
        assert item["lifecycle_state"] == "approved_for_shadow"
        assert item["approval_trust"] is True
        assert item["input_content_hash"] and item["model_snapshot_id"]
        # ... and NONE of the large documents / heavy collections.
        for forbidden in (
            "optimizer_result",
            "requirements",
            "events",
            "transitions",
            "ledger",
            "entries",
            "trajectory",
            "prediction_response_document_text",
            "model_snapshot_document_text",
        ):
            assert forbidden not in item

    def test_list_projects_shadow_active_without_contract_failure(self):
        app, _ = _build_app(
            records=[
                projection_record(
                    _IDS[0],
                    created_at=datetime(2026, 7, 18, 8, tzinfo=timezone.utc),
                    lifecycle="shadow_active",
                    approval_document=TRUSTED_APPROVAL_DOCUMENT,
                )
            ]
        )
        response = TestClient(app).get("/api/v1/control-plans")
        assert response.status_code == 200, response.text
        assert response.json()["items"][0]["lifecycle_state"] == "shadow_active"

    def test_list_paginates_through_next_cursor(self):
        app, _ = _build_app()
        client = TestClient(app)
        first = client.get("/api/v1/control-plans?limit=2").json()
        assert len(first["items"]) == 2
        assert first["next_cursor"] is not None

        second = client.get(
            f"/api/v1/control-plans?limit=2&cursor={first['next_cursor']}"
        ).json()
        first_ids = {item["plan_id"] for item in first["items"]}
        second_ids = {item["plan_id"] for item in second["items"]}
        assert first_ids.isdisjoint(second_ids)  # no duplicate across the boundary


class TestListValidation:
    def test_cursor_reused_across_a_different_filter_set_is_422(self):
        app, _ = _build_app()
        client = TestClient(app)
        page = client.get(
            "/api/v1/control-plans?limit=2&lifecycle_state=draft"
        ).json()
        assert page["next_cursor"] is not None
        # Same cursor, a different filter → 422 (CursorError), not a wrong page.
        response = client.get(
            "/api/v1/control-plans"
            f"?limit=2&lifecycle_state=under_review&cursor={page['next_cursor']}"
        )
        assert response.status_code == 422

    def test_malformed_cursor_is_422(self):
        app, _ = _build_app()
        response = TestClient(app).get(
            "/api/v1/control-plans?cursor=%21%21not-a-cursor"
        )
        assert response.status_code == 422

    def test_invalid_lifecycle_state_filter_is_422(self):
        app, _ = _build_app()
        response = TestClient(app).get(
            "/api/v1/control-plans?lifecycle_state=not_a_state"
        )
        assert response.status_code == 422

    def test_limit_out_of_range_is_422(self):
        app, _ = _build_app()
        assert (
            TestClient(app).get("/api/v1/control-plans?limit=51").status_code
            == 422
        )
        assert (
            TestClient(app).get("/api/v1/control-plans?limit=0").status_code == 422
        )

    def test_list_route_is_registered_at_the_collection_path(self):
        # GET /api/v1/control-plans (no path params) resolves to the list route,
        # distinct from the detail route with {plan_id}/{plan_version}.
        app, _ = _build_app()
        paths = {getattr(route, "path", None) for route in app.routes}
        assert "/api/v1/control-plans" in paths
