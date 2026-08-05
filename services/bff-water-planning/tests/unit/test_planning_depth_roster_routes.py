import json
from contextlib import asynccontextmanager
from pathlib import Path

from api.routes import planning_depth_roster
from fastapi import FastAPI
from fastapi.testclient import TestClient
from schemas.planning_depth import EffectivePrincipalProjection
from schemas.planning_depth_roster import PlanningDepthRosterProjection

CONTRACT_ROOT = (
    Path(__file__).resolve().parents[4] / "contracts" / "planning-depth-roster" / "v1"
)


def _projection():
    return PlanningDepthRosterProjection.model_validate(
        json.loads(
            (CONTRACT_ROOT / "roster.active-v5.example.json").read_text(
                encoding="utf-8"
            )
        )
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


class _FakeDatabaseManager:
    def __init__(self, connection_raises=None):
        self.connection_raises = connection_raises
        self.connection_entries = 0

    @asynccontextmanager
    async def get_connection(self):
        self.connection_entries += 1
        if self.connection_raises is not None:
            raise self.connection_raises
        yield object()


def _build_client(monkeypatch, *, principal_client=None, database_manager=None):
    principal_client = principal_client or _FakePrincipalClient()
    database_manager = database_manager or _FakeDatabaseManager()
    app = FastAPI()
    app.include_router(planning_depth_roster.router)
    app.dependency_overrides[
        planning_depth_roster.get_scheduler_principal_client
    ] = lambda: principal_client
    app.dependency_overrides[
        planning_depth_roster.get_database_manager
    ] = lambda: database_manager

    async def load_roster(connection):
        return _projection()

    monkeypatch.setattr(
        planning_depth_roster,
        "load_authoritative_planning_depth_roster",
        load_roster,
        raising=False,
    )
    return TestClient(app), principal_client, database_manager


def _get(client, token="opaque-bearer"):
    return client.get(
        "/api/v1/water-planning/planning-depth-roster/v1",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_roster_get_requires_bearer_before_scheduler_or_database_call(monkeypatch):
    client, principal_client, manager = _build_client(monkeypatch)

    response = client.get("/api/v1/water-planning/planning-depth-roster/v1")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["cache-control"] == "no-store"
    assert principal_client.tokens == []
    assert manager.connection_entries == 0


def test_roster_get_requires_operator_role(monkeypatch):
    principal_client = _FakePrincipalClient(
        EffectivePrincipalProjection(
            subject="field-team-1",
            effective_roles=["field_team"],
        )
    )
    client, _, manager = _build_client(
        monkeypatch,
        principal_client=principal_client,
    )

    response = _get(client)

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}
    assert response.headers["cache-control"] == "no-store"
    assert principal_client.tokens == ["opaque-bearer"]
    assert manager.connection_entries == 0


def test_roster_get_returns_active_dataset_provenance_and_sections(monkeypatch):
    client, principal_client, manager = _build_client(monkeypatch)

    response = _get(client, token="unchanged-token")

    assert response.status_code == 200
    assert response.json() == _projection().model_dump(mode="json")
    assert response.headers["cache-control"] == "no-store"
    assert principal_client.tokens == ["unchanged-token"]
    assert manager.connection_entries == 1


def test_roster_get_fails_closed_when_projection_is_unavailable(monkeypatch):
    manager = _FakeDatabaseManager(connection_raises=ConnectionError("postgres down"))
    client, _, _ = _build_client(monkeypatch, database_manager=manager)

    response = _get(client)

    assert response.status_code == 503
    assert response.json() == {"detail": "canonical_roster_unavailable"}
    assert response.headers["cache-control"] == "no-store"
