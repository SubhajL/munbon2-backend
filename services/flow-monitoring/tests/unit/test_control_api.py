"""
Unit tests for the C9 control API (POST /api/v1/control/plan) — the HTTP surface that
exposes the NetworkFlowController aggregation engine. DB-free: `api/control.py` is loaded
standalone (it imports only schemas + core + fastapi, never the settings-pulling api pkg),
mounted on a MINIMAL FastAPI app, so it runs isolated:
    pytest --noconftest tests/unit/test_control_api.py
"""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.network_flow_controller import NetworkFlowController

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NETWORK = str(SERVICE_ROOT / "src" / "config" / "network.json")
GEOMETRY = str(SERVICE_ROOT / "src" / "config" / "canal_geometry.json")
CONTROL_PY = SERVICE_ROOT / "src" / "api" / "control.py"


def _load_control():
    """Load src/api/control.py in isolation (bypasses api/__init__ + its DB/settings imports)."""
    spec = importlib.util.spec_from_file_location("flowmon_control_under_test", str(CONTROL_PY))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _app(control, controller):
    control.flow_controller = controller
    app = FastAPI()
    app.include_router(control.router, prefix="/api/v1/control")
    return app


def _area_demand():
    gates = json.loads(Path(NETWORK).read_text())["gates"]
    return {
        g: float(m["area"])
        for g, m in gates.items()
        if isinstance(m.get("area"), (int, float)) and m["area"] > 0
    }


@pytest.fixture
def client():
    control = _load_control()  # fresh module per test -> no flow_controller leakage
    return TestClient(_app(control, NetworkFlowController(NETWORK, GEOMETRY)))


class TestPlanEndpoint:
    def test_returns_one_reach_per_edge_with_conservation(self, client):
        demand = _area_demand()
        resp = client.post("/api/v1/control/plan", json={"demands": demand})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["reaches"]) == 59
        assert body["apply_losses"] is False
        assert body["head_flow_m3s"] == pytest.approx(sum(demand.values()))

    def test_apply_losses_lifts_head_and_flags_missing_geometry(self, client):
        demand = _area_demand()
        lossless = client.post("/api/v1/control/plan", json={"demands": demand}).json()
        lossy = client.post(
            "/api/v1/control/plan", json={"demands": demand, "apply_losses": True}
        ).json()
        assert lossy["head_flow_m3s"] > lossless["head_flow_m3s"]
        assert len(lossy["reaches_missing_geometry"]) == 22

    def test_empty_demand_yields_all_zero_reaches(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {}})
        assert resp.status_code == 200
        assert all(r["required_flow_m3s"] == 0.0 for r in resp.json()["reaches"])

    def test_unknown_node_is_rejected_400(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {"Zone2": 5.0}})
        assert resp.status_code == 400

    def test_negative_demand_is_rejected_400(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {"M(0,2)": -1.0}})
        assert resp.status_code == 400

    def test_demand_on_source_is_rejected_400(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {"S": 1.0}})
        assert resp.status_code == 400


class TestFailClosed:
    def test_503_when_controller_not_initialized(self):
        control = _load_control()
        control.flow_controller = None
        app = FastAPI()
        app.include_router(control.router, prefix="/api/v1/control")
        resp = TestClient(app).post("/api/v1/control/plan", json={"demands": {"M(0,2)": 1.0}})
        assert resp.status_code == 503

    def test_get_system_demand_no_longer_fabricates_25(self):
        # The 25.0 stub must be gone and replaced with a fail-closed raise (verified on source
        # to avoid importing the DB/settings-coupled controller module).
        src = (SERVICE_ROOT / "src" / "controllers" / "dual_mode_gate_controller.py").read_text()
        assert 'return {"total_demand": 25.0}' not in src
        assert "no demand source wired" in src
