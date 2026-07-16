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
DEPLOY_YML = (
    SERVICE_ROOT.parents[1] / ".github" / "workflows" / "deploy-flow-monitoring.yml"
)

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
    def test_constructs_offline_with_all_58_gates(self):
        from controllers.dual_mode_gate_controller import DualModeGateController
        from db.connections import DatabaseManager

        controller = DualModeGateController(DatabaseManager(), NETWORK, GEOMETRY)
        assert len(controller.gate_properties) == 58

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
                "undershot",
                "overshot",
                "radial",
                "vertical",
            }
        finally:
            gates_module.gate_controller = None


class TestManualUpdateFlowLaw:
    @staticmethod
    def _controller_with_stubbed_seams(upstream, downstream):
        from controllers.dual_mode_gate_controller import DualModeGateController
        from db.connections import DatabaseManager

        controller = DualModeGateController(DatabaseManager(), NETWORK, GEOMETRY)

        async def levels(gate_id):
            return {"upstream_level": upstream, "downstream_level": downstream}

        async def no_store(**kwargs):
            return None

        async def no_conflicts():
            return None

        controller._get_gate_measurements = levels
        controller._store_gate_update = no_store
        controller._check_synchronization_conflicts = no_conflicts
        return controller

    def test_manual_update_computes_flow_via_the_canonical_law(self):
        # Wave 1.6: the old path called CalibratedGateFlow.calculate_gate_flow — a
        # method that never existed — so any manual update WITH measurements crashed.
        import asyncio
        import math

        from core.gate_flow import gate_flow_m3s

        probe = self._controller_with_stubbed_seams(0.0, 0.0)
        gate_id = next(iter(probe.gate_properties))
        cal = probe.gate_properties[gate_id]["flow_cal"]
        # non-circular datum check: the cached calibration's sill must be the
        # solver's real invert for this gate, not a default 0.0
        assert cal.sill_m == pytest.approx(
            probe.hydraulic_solver.gate_properties[gate_id].sill_elevation_m
        )
        assert cal.sill_m > 100.0  # Munbon inverts are ~216-221 m MSL, never ~0
        # levels relative to the gate's REAL sill: the calibration must be built with
        # sill_m, or absolute MSL levels turn Hs into ~220 m and the flow pins at the
        # q_max clamp for every opening (the B3 datum bug this suite now locks out).
        # Shallow head keeps the flow below both the Cs-floor band and the clamp.
        upstream, downstream = cal.sill_m + 0.5, cal.sill_m + 0.2
        controller = self._controller_with_stubbed_seams(upstream, downstream)

        ok = asyncio.run(
            controller.update_manual_gate_state(gate_id, 40.0, operator_id="op-1")
        )
        assert ok is True
        flow_40 = controller.gate_states[gate_id].flow_rate
        assert flow_40 is not None and flow_40 >= 0.0 and math.isfinite(flow_40)
        # independent oracle: exactly the canonical law at 40% of the gate's ACTUAL
        # travel (cal.max_opening_m) — 40% sits in the law's differentiating band
        # here, so a wrong percent denominator (the old height-based one) fails this.
        opening_m = 0.40 * cal.max_opening_m
        assert flow_40 == pytest.approx(
            gate_flow_m3s(cal, upstream, downstream, opening_m)
        )

    def test_manual_update_flow_depends_on_the_opening(self):
        # 2% and 20% open MUST pass different flow below the capacity clamp — the
        # sill-omission bug made every opening report the identical clamped value.
        import asyncio

        probe = self._controller_with_stubbed_seams(0.0, 0.0)
        gate_id = next(iter(probe.gate_properties))
        cal = probe.gate_properties[gate_id]["flow_cal"]
        # shallow head-over-sill so both openings sit ABOVE the Cs floor band
        # (inside the band the law is legitimately opening-independent, F-01b)
        upstream, downstream = cal.sill_m + 0.5, cal.sill_m + 0.2
        controller = self._controller_with_stubbed_seams(upstream, downstream)

        from core.gate_flow import gate_flow_m3s

        # guard the premise: 30%% and 50%% of travel must sit in the law's
        # differentiating band for these heads (between the Cs floor and cap) —
        # if a future calibration change flattens it, skip rather than lie red.
        law = {
            pct: gate_flow_m3s(
                cal, upstream, downstream, pct / 100.0 * cal.max_opening_m
            )
            for pct in (30.0, 50.0)
        }
        if law[30.0] == law[50.0]:
            pytest.skip("30/50%% no longer differentiate for this calibration data")

        flows = {}
        for pct in (30.0, 50.0):
            asyncio.run(
                controller.update_manual_gate_state(gate_id, pct, operator_id="op-1")
            )
            flows[pct] = controller.gate_states[gate_id].flow_rate
        assert flows[30.0] < flows[50.0]


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
