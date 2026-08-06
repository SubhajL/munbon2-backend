from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from api.routes import planning_depths
from clients.scheduler_principal_client import (
    SchedulerPrincipalAuthError,
    SchedulerPrincipalClient,
    SchedulerPrincipalContractError,
    SchedulerPrincipalUnavailableError,
)
from db.planning_depth_repository import PlanningDepthConflictError, RosterSnapshot
from fastapi import FastAPI
from fastapi.testclient import TestClient
from schemas.planning_depth import (
    EffectivePrincipalProjection,
    PlanningDepthActiveSubmission,
    PlanningDepthSubmissionReceipt,
)
from services.planning_depth_submission import (
    RosterSection,
    expand_planning_depth_values,
)

SUBMISSION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CLIENT_SUBMISSION_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SUBMITTED_AT = datetime(2026, 7, 24, 1, 0, tzinfo=timezone.utc)
REQUEST_SHA256 = "a" * 64


def _roster():
    sections = []
    for index, section_number in enumerate(range(3, 44)):
        zone_number = min(index // 7 + 1, 6)
        sections.append(
            RosterSection(
                section_id=f"01-{zone_number:02d}-01-{section_number:02d}",
                zone_id=f"01-{zone_number:02d}",
                area_rai=Decimal("5204") if section_number == 43 else Decimal("1000"),
            )
        )
    return sections


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
        "schema_version": 1,
        "client_submission_id": str(CLIENT_SUBMISSION_ID),
        "project_key": "mun-bon",
        "week_key": "2026-W30",
        "week_date": "2026-07-20",
        "expected_active_submission_id": None,
        "levels": _levels(),
    }
    payload.update(overrides)
    return payload


def _receipt(*, replayed=False):
    return PlanningDepthSubmissionReceipt(
        schema_version=1,
        submission_id=SUBMISSION_ID,
        client_submission_id=CLIENT_SUBMISSION_ID,
        project_key="mun-bon",
        week_key="2026-W30",
        week_date=date(2026, 7, 20),
        submitted_at=SUBMITTED_AT,
        submitted_by="operator-1",
        supersedes_submission_id=None,
        request_sha256=REQUEST_SHA256,
        replayed=replayed,
    )


def _active():
    request = planning_depths.PlanningDepthSubmissionRequest.model_validate(_payload())
    return PlanningDepthActiveSubmission(
        **_receipt().model_dump(exclude={"replayed"}),
        levels=expand_planning_depth_values(request.levels, _roster()),
    )


class _FakePrincipalClient:
    def __init__(self, principal=None, raises=None):
        self.principal = principal or EffectivePrincipalProjection(
            subject="operator-1",
            effective_roles=["field_team", "operator"],
        )
        self.raises = raises
        self.tokens = []

    async def load_effective_principal(self, bearer_token):
        self.tokens.append(bearer_token)
        if self.raises is not None:
            raise self.raises
        return self.principal


class _FakeRedis:
    def __init__(self, result=(1, 300), raises=None):
        self.result = result
        self.raises = raises
        self.calls = []

    async def eval(self, script, key_count, key, window_seconds):
        self.calls.append((script, key_count, key, window_seconds))
        if self.raises is not None:
            raise self.raises
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
):
    principal_client = principal_client or _FakePrincipalClient()
    database_manager = database_manager or _FakeDatabaseManager()
    app = FastAPI()
    app.include_router(planning_depths.router)
    app.dependency_overrides[
        planning_depths.get_scheduler_principal_client
    ] = lambda: principal_client
    app.dependency_overrides[
        planning_depths.get_database_manager
    ] = lambda: database_manager
    monkeypatch.setattr(
        planning_depths.settings,
        "planning_depth_writes_enabled",
        "true",
    )

    async def load_roster(connection):
        return RosterSnapshot(
            sections=tuple(_roster()),
            dataset_version_id=7,
            source_hash="1" * 64,
        )

    async def create_submission(connection, request, principal, roster):
        if isinstance(create_result, Exception):
            raise create_result
        return create_result or _receipt()

    async def get_active(connection, project_key, week_key):
        if isinstance(active_result, Exception):
            raise active_result
        if active_result == "default":
            return _active()
        return active_result

    monkeypatch.setattr(
        planning_depths, "load_planning_depth_roster_snapshot", load_roster
    )
    monkeypatch.setattr(
        planning_depths,
        "create_planning_depth_submission",
        create_submission,
    )
    monkeypatch.setattr(
        planning_depths,
        "get_active_planning_depth_submission",
        get_active,
    )
    return TestClient(app), principal_client, database_manager


def _post(client, token="opaque-bearer"):
    return client.post(
        "/api/v1/water-planning/planning-depth-submissions",
        headers={"Authorization": f"Bearer {token}"},
        json=_payload(),
    )


def test_v1_route_passes_the_loaded_snapshot_object_into_create(monkeypatch):
    # Same-object guarantee for the v1 write path (mirror of the v2 test): a
    # v1-only reload/reconstruction regression would otherwise go uncaught.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    sentinel = RosterSnapshot(
        sections=tuple(_roster()), dataset_version_id=7, source_hash="1" * 64
    )
    captured = {}
    app = FastAPI()
    app.include_router(planning_depths.router)
    app.dependency_overrides[
        planning_depths.get_scheduler_principal_client
    ] = lambda: _FakePrincipalClient()
    app.dependency_overrides[
        planning_depths.get_database_manager
    ] = lambda: _FakeDatabaseManager()
    monkeypatch.setattr(
        planning_depths.settings, "planning_depth_writes_enabled", "true"
    )

    async def load_roster(connection):
        return sentinel

    async def create_submission(connection, request, principal, roster):
        captured["roster"] = roster
        return _receipt()

    async def get_active(connection, project_key, week_key):
        return _active()

    monkeypatch.setattr(
        planning_depths, "load_planning_depth_roster_snapshot", load_roster
    )
    monkeypatch.setattr(
        planning_depths, "create_planning_depth_submission", create_submission
    )
    monkeypatch.setattr(
        planning_depths, "get_active_planning_depth_submission", get_active
    )

    response = _post(TestClient(app))

    assert response.status_code in (200, 201)
    assert captured["roster"] is sentinel


class TestSchedulerPrincipalClient:
    @pytest.mark.asyncio
    async def test_forwards_bearer_unchanged_only_to_principal_endpoint(self):
        captured = []

        def handler(request):
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "subject": "operator-1",
                    "effective_roles": ["field_team", "operator"],
                },
            )

        client = SchedulerPrincipalClient(
            base_url="http://scheduler.test",
            transport=httpx.MockTransport(handler),
        )

        principal = await client.load_effective_principal("opaque-bearer")

        assert principal.model_dump() == {
            "subject": "operator-1",
            "effective_roles": ["field_team", "operator"],
        }
        assert len(captured) == 1
        assert captured[0].url.path == "/api/v1/auth/principal"
        assert captured[0].headers["authorization"] == "Bearer opaque-bearer"

    @pytest.mark.asyncio
    async def test_schema_drift_fails_closed(self):
        client = SchedulerPrincipalClient(
            base_url="http://scheduler.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "subject": "operator-1",
                        "effective_roles": ["operator", "field_team"],
                    },
                )
            ),
        )

        with pytest.raises(SchedulerPrincipalContractError):
            await client.load_effective_principal("opaque-bearer")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status_code", "error_type"),
        [
            (401, SchedulerPrincipalAuthError),
            (403, SchedulerPrincipalAuthError),
            (503, SchedulerPrincipalUnavailableError),
            (500, SchedulerPrincipalContractError),
        ],
    )
    async def test_upstream_status_taxonomy(self, status_code, error_type):
        client = SchedulerPrincipalClient(
            base_url="http://scheduler.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    status_code,
                    json={"detail": "safe upstream detail"},
                )
            ),
        )

        with pytest.raises(error_type):
            await client.load_effective_principal("opaque-bearer")


class TestPlanningDepthSubmissionRoutes:
    def test_missing_bearer_is_unauthorized_without_scheduler_or_database_call(
        self, monkeypatch
    ):
        client, principal_client, manager = _build_client(monkeypatch)

        response = client.post(
            "/api/v1/water-planning/planning-depth-submissions",
            json=_payload(),
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Not authenticated"}
        assert response.headers["cache-control"] == "no-store"
        assert principal_client.tokens == []
        assert manager.connection_entries == 0

    def test_field_team_only_principal_is_forbidden(self, monkeypatch):
        principal = EffectivePrincipalProjection(
            subject="field-team-1",
            effective_roles=["field_team"],
        )
        client, principal_client, manager = _build_client(
            monkeypatch,
            principal_client=_FakePrincipalClient(principal),
        )

        response = _post(client)

        assert response.status_code == 403
        assert response.json() == {"detail": "Insufficient permissions"}
        assert response.headers["cache-control"] == "no-store"
        assert principal_client.tokens == ["opaque-bearer"]
        assert manager.connection_entries == 0

    @pytest.mark.parametrize(
        ("error", "expected_status"),
        [
            (SchedulerPrincipalAuthError(401, "Token has been revoked"), 401),
            (SchedulerPrincipalUnavailableError("scheduler unavailable"), 503),
            (SchedulerPrincipalContractError("scheduler drift"), 502),
        ],
    )
    def test_scheduler_failure_taxonomy(self, monkeypatch, error, expected_status):
        client, _, manager = _build_client(
            monkeypatch,
            principal_client=_FakePrincipalClient(raises=error),
        )

        response = _post(client)

        assert response.status_code == expected_status
        assert response.headers["cache-control"] == "no-store"
        assert manager.connection_entries == 0

    def test_structurally_invalid_body_does_not_consume_limiter(self, monkeypatch):
        manager = _FakeDatabaseManager()
        client, _, _ = _build_client(monkeypatch, database_manager=manager)
        invalid = _payload()
        invalid["levels"][0]["planning_depth_mm"] = "1.5"

        response = client.post(
            "/api/v1/water-planning/planning-depth-submissions",
            headers={"Authorization": "Bearer opaque-bearer"},
            json=invalid,
        )

        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"
        assert manager.redis.calls == []

    def test_write_flag_requires_the_exact_string_true(self, monkeypatch):
        manager = _FakeDatabaseManager()
        client, principal_client, _ = _build_client(
            monkeypatch,
            database_manager=manager,
        )
        monkeypatch.setattr(
            planning_depths.settings,
            "planning_depth_writes_enabled",
            "TRUE",
        )

        response = _post(client)

        assert response.status_code == 503
        assert response.json() == {"detail": "planning_depth_writes_disabled"}
        assert response.headers["cache-control"] == "no-store"
        assert principal_client.tokens == ["opaque-bearer"]
        assert manager.connection_entries == 0
        assert manager.redis.calls == []

    def test_roster_connection_outage_fails_closed_before_limiter(self, monkeypatch):
        manager = _FakeDatabaseManager(
            connection_raises=ConnectionError("postgres down")
        )
        client, _, _ = _build_client(monkeypatch, database_manager=manager)

        response = _post(client)

        assert response.status_code == 503
        assert response.json() == {"detail": "canonical_roster_unavailable"}
        assert response.headers["cache-control"] == "no-store"
        assert manager.connection_entries == 1
        assert manager.redis.calls == []

    def test_redis_limiter_outage_fails_closed_without_creating_submission(
        self, monkeypatch
    ):
        manager = _FakeDatabaseManager(
            redis=_FakeRedis(raises=ConnectionError("redis down"))
        )
        create_calls = []
        client, _, _ = _build_client(monkeypatch, database_manager=manager)

        async def unexpected_create(*args):
            create_calls.append(args)

        monkeypatch.setattr(
            planning_depths,
            "create_planning_depth_submission",
            unexpected_create,
        )

        response = _post(client)

        assert response.status_code == 503
        assert response.json() == {"detail": "planning_depth_write_limiter_unavailable"}
        assert response.headers["cache-control"] == "no-store"
        assert create_calls == []

    def test_rate_limit_returns_retry_after_without_creating_submission(
        self, monkeypatch
    ):
        manager = _FakeDatabaseManager(redis=_FakeRedis(result=(11, 42)))
        create_calls = []
        client, _, _ = _build_client(monkeypatch, database_manager=manager)

        async def unexpected_create(*args):
            create_calls.append(args)

        monkeypatch.setattr(
            planning_depths,
            "create_planning_depth_submission",
            unexpected_create,
        )

        response = _post(client)

        assert response.status_code == 429
        assert response.headers["retry-after"] == "42"
        assert response.headers["cache-control"] == "no-store"
        assert create_calls == []

    @pytest.mark.parametrize(
        ("receipt", "expected_status"),
        [(_receipt(), 201), (_receipt(replayed=True), 200)],
    )
    def test_post_returns_created_or_replayed(
        self, monkeypatch, receipt, expected_status
    ):
        client, principal_client, _ = _build_client(
            monkeypatch,
            create_result=receipt,
        )

        response = _post(client, token="unchanged-token")

        assert response.status_code == expected_status
        assert response.json()["submission_id"] == str(SUBMISSION_ID)
        assert response.json()["replayed"] is receipt.replayed
        assert response.headers["cache-control"] == "no-store"
        assert principal_client.tokens == ["unchanged-token"]

    def test_conflict_is_409(self, monkeypatch):
        client, _, _ = _build_client(
            monkeypatch,
            create_result=PlanningDepthConflictError("stale_active_submission"),
        )

        response = _post(client)

        assert response.status_code == 409
        assert response.json() == {"detail": "stale_active_submission"}
        assert response.headers["cache-control"] == "no-store"

    def test_submission_database_outage_is_service_unavailable(self, monkeypatch):
        client, _, _ = _build_client(
            monkeypatch,
            create_result=ConnectionError("postgres write failed"),
        )

        response = _post(client)

        assert response.status_code == 503
        assert response.json() == {"detail": "planning_depth_database_unavailable"}
        assert response.headers["cache-control"] == "no-store"

    def test_active_get_returns_authoritative_expanded_values(self, monkeypatch):
        client, _, _ = _build_client(monkeypatch)

        response = client.get(
            "/api/v1/water-planning/planning-depth-submissions/active",
            params={"project_key": "mun-bon", "week_key": "2026-W30"},
            headers={"Authorization": "Bearer opaque-bearer"},
        )

        assert response.status_code == 200
        assert len(response.json()["levels"]) == 41
        assert response.json()["levels"][0] == {
            "section_id": "01-01-01-03",
            "zone_id": "01-01",
            "planning_depth_mm": 1.5,
            "source_kind": "zone_default",
            "source_area_id": "01-01",
        }
        assert response.headers["cache-control"] == "no-store"

    def test_missing_active_submission_is_not_found(self, monkeypatch):
        client, _, _ = _build_client(monkeypatch, active_result=None)

        response = client.get(
            "/api/v1/water-planning/planning-depth-submissions/active",
            params={"project_key": "mun-bon", "week_key": "2026-W30"},
            headers={"Authorization": "Bearer opaque-bearer"},
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "planning_depth_submission_not_found"}
        assert response.headers["cache-control"] == "no-store"

    def test_active_database_outage_is_service_unavailable(self, monkeypatch):
        client, _, _ = _build_client(
            monkeypatch,
            active_result=ConnectionError("postgres read failed"),
        )

        response = client.get(
            "/api/v1/water-planning/planning-depth-submissions/active",
            params={"project_key": "mun-bon", "week_key": "2026-W30"},
            headers={"Authorization": "Bearer opaque-bearer"},
        )

        assert response.status_code == 503
        assert response.json() == {"detail": "planning_depth_database_unavailable"}
        assert response.headers["cache-control"] == "no-store"
