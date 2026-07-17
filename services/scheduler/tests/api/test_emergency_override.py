from typing import Dict
from fastapi.testclient import TestClient
from core.deps import get_current_user
from core.database import get_db
from core.deps import get_db as deps_get_db
from main import app
import main as _main


async def _db_stub():
    # Ensure dependency resolution does not attempt real DB connection
    if False:
        yield  # pragma: no cover
    yield None


def test_emergency_override_requires_roles_403():
    # Override current user to lack required roles and DB dependency
    app.dependency_overrides[get_current_user] = lambda: {"username": "test", "roles": ["viewer"]}
    app.dependency_overrides[get_db] = _db_stub
    try:
        payload: Dict = {
            "gate_id": "GATE-001",
            "target_opening": 90.0,
            "override_safety_checks": False,
            "reason": "test"
        }
        # Monkeypatch DB engine.begin used in app lifespan to avoid real DB connection

        class _Conn:
            async def run_sync(self, fn):
                return None

        class _Begin:
            async def __aenter__(self):
                return _Conn()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class _FakeEngine:
            def begin(self):
                return _Begin()
        _original_engine = _main.engine
        _main.engine = _FakeEngine()

        with TestClient(app) as client:
            resp = client.post("/api/v1/adaptation/emergency-override", json=payload)
        assert resp.status_code == 403
        assert resp.json()["detail"].lower().find("insufficient") >= 0
    finally:
        # Restore the real engine — a leaked _FakeEngine would poison every
        # later test that opens TestClient(app).
        _main.engine = _original_engine
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(deps_get_db, None)
