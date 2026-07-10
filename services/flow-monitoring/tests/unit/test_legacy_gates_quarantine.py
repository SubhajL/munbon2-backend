"""
Wave 1.5 (Decision 2, review defect #7): the legacy dual-stack gates surface is
quarantined — /api/v1/gates/* is OFF unless GATES_API_ENABLED=true, and when on it
runs on the CANONICAL configs, never the fragmented munbon_network_final.json
(2/57 nodes reachable) that main.py and the EC2 deploy workflow used to ship.

Run isolated from the service root:
    PYTHONPATH=src pytest --noconftest -o addopts="" tests/unit/test_legacy_gates_quarantine.py
"""
import importlib.util
import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NETWORK = str(SERVICE_ROOT / "src" / "config" / "network.json")
GEOMETRY = str(SERVICE_ROOT / "src" / "config" / "canal_geometry.json")
GATES_PY = SERVICE_ROOT / "src" / "api" / "gates.py"
DEPLOY_YML = SERVICE_ROOT.parents[1] / ".github" / "workflows" / "deploy-flow-monitoring.yml"

REQUIRED_ENV = {
    "INFLUXDB_URL": "http://x:8086",
    "INFLUXDB_TOKEN": "t",
    "INFLUXDB_ORG": "o",
    "INFLUXDB_BUCKET": "b",
    "TIMESCALE_URL": "postgresql://u:p@x:5432/sensor_data",
    "POSTGRES_URL": "postgresql://u:p@x:5432/postgres",
    "REDIS_URL": "redis://x:6379/0",
}


def _load_gates_module():
    spec = importlib.util.spec_from_file_location(
        "flowmon_gates_under_test", str(GATES_PY)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFeatureFlag:
    def test_gates_api_is_disabled_by_default(self, monkeypatch):
        for key, value in REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("GATES_API_ENABLED", raising=False)
        from config.settings import Settings

        assert Settings().gates_api_enabled is False

    def test_flag_enables_via_env(self, monkeypatch):
        for key, value in REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("GATES_API_ENABLED", "true")
        from config.settings import Settings

        assert Settings().gates_api_enabled is True


class TestGateControllerDependency:
    def test_uninitialized_is_503(self):
        from fastapi import HTTPException

        module = _load_gates_module()
        assert module.gate_controller is None
        with pytest.raises(HTTPException) as exc:
            module.get_gate_controller()
        assert exc.value.status_code == 503

    def test_disabled_reason_wins_with_a_clear_message(self):
        from fastapi import HTTPException

        module = _load_gates_module()
        module.disabled_reason = "legacy gates API disabled per decision 2"
        with pytest.raises(HTTPException) as exc:
            module.get_gate_controller()
        assert exc.value.status_code == 503
        assert "decision 2" in exc.value.detail

    def test_registered_controller_is_returned(self):
        module = _load_gates_module()
        sentinel = object()
        module.gate_controller = sentinel
        assert module.get_gate_controller() is sentinel


class TestControllerOnCanonicalConfigs:
    def test_constructs_offline_with_all_59_gates(self):
        from controllers.dual_mode_gate_controller import DualModeGateController
        from db.connections import DatabaseManager

        controller = DualModeGateController(DatabaseManager(), NETWORK, GEOMETRY)
        assert len(controller.gate_properties) == 59

    def test_flag_on_state_endpoint_serves_a_gate(self):
        # The enabled surface must actually answer: the solver's gate types
        # (sluice_gate/...) must map into the API schema enum, or every
        # /gates/state call 500s (Codex HIGH). Measurements are stubbed — the
        # DB seam is not under test here.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from controllers.dual_mode_gate_controller import DualModeGateController
        from db.connections import DatabaseManager
        from api import gates as gates_module

        controller = DualModeGateController(DatabaseManager(), NETWORK, GEOMETRY)

        async def no_measurements(gate_id):
            return {}

        controller._get_gate_measurements = no_measurements
        gates_module.gate_controller = controller
        gates_module.disabled_reason = None
        app = FastAPI()
        app.include_router(gates_module.router, prefix="/api/v1/gates")
        try:
            gate_id = next(iter(controller.gate_properties))
            resp = TestClient(app).get(f"/api/v1/gates/state/{gate_id}")
            assert resp.status_code == 200
            assert resp.json()["gate_type"] in {
                "undershot", "overshot", "radial", "vertical"
            }
        finally:
            gates_module.gate_controller = None


class TestGateConfigRouterQuarantined:
    def test_gates_config_surface_fails_closed_with_the_gates_flag(self):
        # /api/v1/gates/config/* is mounted as a SEPARATE router; it must share the
        # legacy-gates quarantine, not slip past it.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api import gate_config as gate_config_module
        from api import gates as gates_module

        gates_module.gate_controller = None
        gates_module.disabled_reason = "legacy gates API disabled per decision 2"
        app = FastAPI()
        app.include_router(gate_config_module.router, prefix="/api/v1")
        try:
            resp = TestClient(app).get("/api/v1/gates/config/all")
            assert resp.status_code == 503
            assert "decision 2" in resp.json()["detail"]
        finally:
            gates_module.disabled_reason = None


class TestDeployWorkflowShipsCanonicalConfigs:
    """Review defect #7's second half: the EC2 deploy shipped the fragmented
    topology. Locked here the same way the CI suite manifest is locked."""

    def test_ships_canonical_configs(self):
        text = DEPLOY_YML.read_text(encoding="utf-8")
        assert "src/config/network.json" in text
        assert "src/config/canal_geometry.json" in text

    def test_does_not_ship_the_fragmented_topology(self):
        text = DEPLOY_YML.read_text(encoding="utf-8")
        assert "munbon_network_final.json" not in text
        assert "canal_geometry_template.json" not in text

    def test_keeps_a_deployment_smoke(self):
        text = DEPLOY_YML.read_text(encoding="utf-8")
        assert "curl -f http://localhost:3011/health" in text
        # end-to-end evidence the canonical control plane booted, not just the app
        assert "/api/v1/control/plan" in text
