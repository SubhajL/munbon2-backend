from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from api.routes import planning_depths_v2
from db.planning_depth_repository import PlanningDepthConflictError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from schemas.planning_depth import EffectivePrincipalProjection
from schemas.planning_depth_v2 import (
    PlanningDepthActiveSubmissionV2,
    PlanningDepthSubmissionReceiptV2,
    PlanningDepthSubmissionRequestV2,
)
from services.planning_depth_submission import (
    RosterSection,
    expand_planning_depth_values,
)

SUBMISSION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CLIENT_SUBMISSION_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SUBMITTED_AT = datetime(2025, 11, 1, 1, 0, tzinfo=timezone.utc)
REQUEST_SHA256 = "a" * 64


def _roster():
    return [
        RosterSection(
            section_id=f"01-{min(index // 7 + 1, 6):02d}-01-{section_number:02d}",
            zone_id=f"01-{min(index // 7 + 1, 6):02d}",
            area_rai=Decimal("5204") if section_number == 43 else Decimal("1000"),
        )
        for index, section_number in enumerate(range(3, 44))
    ]


def _levels():
    return [
        {
            "area_type": "zone",
            "area_id": f"01-{zone_number:02d}",
            "planning_depth_mm": zone_number + 0.5,
        }
        for zone_number in range(1, 7)
    ]


def _payload(**overrides):
    payload = {
        "schema_version": 2,
        "client_submission_id": str(CLIENT_SUBMISSION_ID),
        "project_key": "mun-bon",
        "calendar_system": "rid-irrigation-v1",
        "week_key": "2026-R01",
        "week_date": "2025-11-01",
        "expected_active_submission_id": None,
        "levels": _levels(),
    }
    payload.update(overrides)
    return payload


def _receipt(*, replayed=False):
    return PlanningDepthSubmissionReceiptV2(
        schema_version=2,
        submission_id=SUBMISSION_ID,
        client_submission_id=CLIENT_SUBMISSION_ID,
        project_key="mun-bon",
        calendar_system="rid-irrigation-v1",
        week_key="2026-R01",
        week_date=date(2025, 11, 1),
        submitted_at=SUBMITTED_AT,
        submitted_by="operator-1",
        supersedes_submission_id=None,
        request_sha256=REQUEST_SHA256,
        replayed=replayed,
    )


def _active():
    request = PlanningDepthSubmissionRequestV2.model_validate(_payload())
    return PlanningDepthActiveSubmissionV2(
        **_receipt().model_dump(exclude={"replayed"}),
        levels=expand_planning_depth_values(request.levels, _roster()),
    )


class _FakePrincipalClient:
    def __init__(self, principal=None):
        self.principal = principal or EffectivePrincipalProjection(
            subject="operator-1",
            effective_roles=["field_team", "operator"],
        )
        self.tokens = []

    async def load_effective_principal(self, bearer_token):
        self.tokens.append(bearer_token)
        return self.principal


class _FakeRedis:
    def __init__(self, result=(1, 300)):
        self.result = result
        self.calls = []

    async def eval(self, script, key_count, key, window_seconds):
        self.calls.append((script, key_count, key, window_seconds))
        return self.result


class _FakeDatabaseManager:
    def __init__(self, redis=None, connection_raises=None):
        self.redis = redis or _FakeRedis()
        self.connection_raises = connection_raises
        self.connection_entries = 0

    @asynccontextmanager
    async def get_connection(self):
        self.connection_entries += 1
        if self.connection_raises is not None:
            raise self.connection_raises
        yield object()

    def get_redis_client(self):
        return self.redis


def _build_client(
    monkeypatch,
    *,
    principal_client=None,
    database_manager=None,
    create_result=None,
    active_result="default",
    active_calls=None,
):
    principal_client = principal_client or _FakePrincipalClient()
    database_manager = database_manager or _FakeDatabaseManager()
    app = FastAPI()
    app.include_router(planning_depths_v2.router)
    app.dependency_overrides[
        planning_depths_v2.get_scheduler_principal_client
    ] = lambda: principal_client
    app.dependency_overrides[
        planning_depths_v2.get_database_manager
    ] = lambda: database_manager
    monkeypatch.setattr(
        planning_depths_v2.settings,
        "planning_depth_writes_enabled",
        "true",
    )

    async def load_roster(connection):
        return _roster()

    async def create_submission(connection, request, principal, roster):
        if isinstance(create_result, Exception):
            raise create_result
        return create_result or _receipt()

    async def get_active(connection, project_key, calendar_system, week_key):
        if active_calls is not None:
            active_calls.append((project_key, calendar_system, week_key))
        if isinstance(active_result, Exception):
            raise active_result
        if active_result == "default":
            return _active()
        return active_result

    monkeypatch.setattr(planning_depths_v2, "load_planning_depth_roster", load_roster)
    monkeypatch.setattr(
        planning_depths_v2,
        "create_planning_depth_submission_v2",
        create_submission,
    )
    monkeypatch.setattr(
        planning_depths_v2,
        "get_active_planning_depth_submission_v2",
        get_active,
    )
    return TestClient(app), principal_client, database_manager


def _post(client, payload=None):
    return client.post(
        "/api/v2/water-planning/planning-depth-submissions",
        headers={"Authorization": "Bearer opaque-bearer"},
        json=payload or _payload(),
    )


class TestPlanningDepthV2Routes:
    def test_missing_bearer_is_unauthorized_without_database_call(self, monkeypatch):
        client, principal_client, manager = _build_client(monkeypatch)

        response = client.post(
            "/api/v2/water-planning/planning-depth-submissions",
            json=_payload(),
        )

        assert (
            response.status_code,
            response.json(),
            response.headers["cache-control"],
            principal_client.tokens,
            manager.connection_entries,
        ) == (401, {"detail": "Not authenticated"}, "no-store", [], 0)

    def test_field_team_only_principal_is_forbidden(self, monkeypatch):
        principal = EffectivePrincipalProjection(
            subject="field-team-1",
            effective_roles=["field_team"],
        )
        client, _, manager = _build_client(
            monkeypatch,
            principal_client=_FakePrincipalClient(principal),
        )

        response = _post(client)

        assert (response.status_code, response.json(), manager.connection_entries) == (
            403,
            {"detail": "Insufficient permissions"},
            0,
        )
        assert response.headers["cache-control"] == "no-store"

    def test_invalid_identity_is_unprocessable_without_consuming_limiter(
        self, monkeypatch
    ):
        manager = _FakeDatabaseManager()
        client, _, _ = _build_client(monkeypatch, database_manager=manager)

        response = _post(client, _payload(calendar_system="legacy-calendar-v1"))

        assert (response.status_code, response.headers["cache-control"]) == (
            422,
            "no-store",
        )
        assert manager.redis.calls == []

    def test_write_flag_requires_exact_true(self, monkeypatch):
        manager = _FakeDatabaseManager()
        client, _, _ = _build_client(monkeypatch, database_manager=manager)
        monkeypatch.setattr(
            planning_depths_v2.settings,
            "planning_depth_writes_enabled",
            "TRUE",
        )

        response = _post(client)

        assert (response.status_code, response.json(), manager.connection_entries) == (
            503,
            {"detail": "planning_depth_writes_disabled"},
            0,
        )
        assert response.headers["cache-control"] == "no-store"

    def test_rate_limit_returns_retry_after_without_database_write(self, monkeypatch):
        manager = _FakeDatabaseManager(redis=_FakeRedis(result=(11, 42)))
        client, _, _ = _build_client(monkeypatch, database_manager=manager)

        response = _post(client)

        assert (
            response.status_code,
            response.json(),
            response.headers["retry-after"],
            response.headers["cache-control"],
            manager.connection_entries,
        ) == (
            429,
            {"detail": "planning_depth_write_rate_limited"},
            "42",
            "no-store",
            1,
        )

    @pytest.mark.parametrize(
        ("receipt", "expected_status"),
        [(_receipt(), 201), (_receipt(replayed=True), 200)],
    )
    def test_post_returns_explicit_rid_identity(
        self, monkeypatch, receipt, expected_status
    ):
        client, _, _ = _build_client(monkeypatch, create_result=receipt)

        response = _post(client)

        assert (
            response.status_code,
            response.json()["schema_version"],
            response.json()["calendar_system"],
            response.json()["week_key"],
            response.json()["replayed"],
            response.headers["cache-control"],
        ) == (
            expected_status,
            2,
            "rid-irrigation-v1",
            "2026-R01",
            receipt.replayed,
            "no-store",
        )

    def test_conflict_is_409(self, monkeypatch):
        client, _, _ = _build_client(
            monkeypatch,
            create_result=PlanningDepthConflictError("stale_active_submission"),
        )

        response = _post(client)

        assert (response.status_code, response.json()) == (
            409,
            {"detail": "stale_active_submission"},
        )
        assert response.headers["cache-control"] == "no-store"

    def test_database_outage_is_service_unavailable(self, monkeypatch):
        manager = _FakeDatabaseManager(
            connection_raises=ConnectionError("postgres down")
        )
        client, _, _ = _build_client(monkeypatch, database_manager=manager)

        response = _post(client)

        assert (response.status_code, response.json()) == (
            503,
            {"detail": "canonical_roster_unavailable"},
        )
        assert response.headers["cache-control"] == "no-store"

    def test_active_get_passes_explicit_calendar_scope(self, monkeypatch):
        active_calls = []
        client, _, _ = _build_client(monkeypatch, active_calls=active_calls)

        response = client.get(
            "/api/v2/water-planning/planning-depth-submissions/active",
            params={
                "project_key": "mun-bon",
                "calendar_system": "rid-irrigation-v1",
                "week_key": "2026-R01",
            },
            headers={"Authorization": "Bearer opaque-bearer"},
        )

        assert (
            response.status_code,
            response.json()["calendar_system"],
            len(response.json()["levels"]),
            active_calls,
            response.headers["cache-control"],
        ) == (
            200,
            "rid-irrigation-v1",
            41,
            [("mun-bon", "rid-irrigation-v1", "2026-R01")],
            "no-store",
        )

    def test_active_get_rejects_wrong_calendar_query(self, monkeypatch):
        client, _, _ = _build_client(monkeypatch)

        response = client.get(
            "/api/v2/water-planning/planning-depth-submissions/active",
            params={
                "project_key": "mun-bon",
                "calendar_system": "legacy-calendar-v1",
                "week_key": "2026-R01",
            },
            headers={"Authorization": "Bearer opaque-bearer"},
        )

        assert (response.status_code, response.headers["cache-control"]) == (
            422,
            "no-store",
        )

    @pytest.mark.parametrize("week_key", ["1900-R01", "2402-R01"])
    def test_active_get_rejects_unsupported_rid_year_without_database_call(
        self, monkeypatch, week_key
    ):
        active_calls = []
        client, _, manager = _build_client(monkeypatch, active_calls=active_calls)

        response = client.get(
            "/api/v2/water-planning/planning-depth-submissions/active",
            params={
                "project_key": "mun-bon",
                "calendar_system": "rid-irrigation-v1",
                "week_key": week_key,
            },
            headers={"Authorization": "Bearer opaque-bearer"},
        )

        assert (
            response.status_code,
            response.headers["cache-control"],
            active_calls,
            manager.connection_entries,
        ) == (422, "no-store", [], 0)

    def test_missing_active_submission_is_not_found(self, monkeypatch):
        client, _, _ = _build_client(monkeypatch, active_result=None)

        response = client.get(
            "/api/v2/water-planning/planning-depth-submissions/active",
            params={
                "project_key": "mun-bon",
                "calendar_system": "rid-irrigation-v1",
                "week_key": "2026-R01",
            },
            headers={"Authorization": "Bearer opaque-bearer"},
        )

        assert (response.status_code, response.json()) == (
            404,
            {"detail": "planning_depth_submission_not_found"},
        )
        assert response.headers["cache-control"] == "no-store"
