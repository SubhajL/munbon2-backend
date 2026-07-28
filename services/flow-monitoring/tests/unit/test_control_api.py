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
CALIBRATIONS = str(SERVICE_ROOT / "src" / "config" / "gate_calibrations.json")
ZONE_TOPOLOGY = str(SERVICE_ROOT / "src" / "config" / "zone_topology.json")
CONTROL_PY = SERVICE_ROOT / "src" / "api" / "control.py"


def _load_control():
    """Load src/api/control.py in isolation (bypasses api/__init__ + its DB/settings imports)."""
    spec = importlib.util.spec_from_file_location(
        "flowmon_control_under_test", str(CONTROL_PY)
    )
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


@pytest.fixture
def design_client():
    from services.design_profile_service import DesignProfileService

    control = _load_control()
    control.design_profile_service = DesignProfileService(
        NETWORK,
        GEOMETRY,
        CALIBRATIONS,
        ZONE_TOPOLOGY,
    )
    return TestClient(_app(control, NetworkFlowController(NETWORK, GEOMETRY)))


class TestPlanEndpoint:
    def test_returns_one_reach_per_edge_with_conservation(self, client):
        demand = _area_demand()
        resp = client.post("/api/v1/control/plan", json={"demands": demand})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["reaches"]) == 58
        assert body["apply_losses"] is False
        assert body["head_flow_m3s"] == pytest.approx(sum(demand.values()))

    def test_apply_losses_lifts_head_and_flags_missing_geometry(self, client):
        demand = _area_demand()
        lossless = client.post("/api/v1/control/plan", json={"demands": demand}).json()
        lossy = client.post(
            "/api/v1/control/plan", json={"demands": demand, "apply_losses": True}
        ).json()
        assert lossy["head_flow_m3s"] > lossless["head_flow_m3s"]
        # 17 = 58 edges - 41 surveyed serial reaches:
        # the source edge + 13 junction heads + 3 offtakes (Waste Way, FTOs).
        assert len(lossy["reaches_missing_geometry"]) == 17

    def test_apply_losses_surfaces_partial_reach_chainage_gaps(self, client):
        # QCHECK 2.1b HIGH: partially surveyed reaches take zero loss on their
        # unsurveyed chainage — the plan must SAY so, or the operator reads an
        # understated head-gate release as full loss coverage.
        lossy = client.post(
            "/api/v1/control/plan", json={"demands": {}, "apply_losses": True}
        ).json()
        gaps = {
            (g["upstream"], g["downstream"]): g["gap_m"]
            for g in lossy["reaches_with_chainage_gaps"]
        }
        assert gaps == {("M(0,0)", "M(0,2)"): pytest.approx(170.0)}
        # Geometry coverage is a static network property (Wave 2.8a): the SAME gaps
        # surface without apply_losses — the itemized list must never contradict the
        # coverage roll-up in the same payload.
        lossless = client.post("/api/v1/control/plan", json={"demands": {}}).json()
        lossless_gaps = {
            (g["upstream"], g["downstream"]): g["gap_m"]
            for g in lossless["reaches_with_chainage_gaps"]
        }
        assert lossless_gaps == gaps

    def test_geometry_lists_never_contradict_the_coverage_summary(self, client):
        # QCHECK CONFIRMED: the always-on coverage roll-up must agree with the itemized
        # geometry lists in the SAME payload, in both loss modes — a consumer reconciling
        # len(list) == coverage.count must never see 17-missing/5-gaps in the summary but
        # empty lists (the pre-fix default path).
        for apply_losses in (False, True):
            body = client.post(
                "/api/v1/control/plan",
                json={"demands": {}, "apply_losses": apply_losses},
            ).json()
            cov = body["coverage"]
            assert (
                len(body["reaches_missing_geometry"]) == cov["geometry_missing"] == 17
            )
            assert len(body["reaches_with_chainage_gaps"]) == cov["chainage_gaps"] == 1

    def test_empty_demand_yields_all_zero_reaches(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {}})
        assert resp.status_code == 200
        assert all(r["required_flow_m3s"] == 0.0 for r in resp.json()["reaches"])

    def test_each_reach_carries_2_8a_confidence_and_coverage(self, client):
        # Wave 2.8a: every reach exposes the confidence/method of its terminating gate
        # and whether it has surveyed geometry — surfaced regardless of apply_losses.
        # Oracle: an independent calibration loader keyed on the downstream node.
        from utils.gate_calibration_loader import GateCalibrationLoader

        oracle = GateCalibrationLoader()
        body = client.post("/api/v1/control/plan", json={"demands": {}}).json()
        assert len(body["reaches"]) == 58
        by_reach = {(r["upstream"], r["downstream"]): r for r in body["reaches"]}
        for reach in body["reaches"]:
            expected = oracle.get_calibration(reach["downstream"])
            assert reach["calibration_method"] == expected.calibration_method
            assert reach["confidence"] == pytest.approx(expected.confidence)
        # Exact has_geometry on independently-known reaches (not just isinstance bool):
        # the source edge has no surveyed cross-section; the RMC tail reach does (it is a
        # partial survey that still carries geometry).
        assert by_reach[("S", "M(0,0)")]["has_geometry"] is False
        assert by_reach[("M(0,0;2,3)", "M(0,0;2,4)")]["has_geometry"] is True

    def test_plan_reports_network_coverage_summary(self, client):
        body = client.post("/api/v1/control/plan", json={"demands": {}}).json()
        assert body["coverage"] == {
            "total_reaches": 58,
            "geometry_surveyed": 41,
            "geometry_missing": 17,
            "chainage_gaps": 1,
            "calibration_method_counts": {"measured": 10, "inferred": 48},
        }

    def test_unknown_node_is_rejected_400(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {"Zone2": 5.0}})
        assert resp.status_code == 400

    def test_accepts_compact_demand_alias_for_spaced_network_node(self, client):
        # Wave 1.2 boundary normalization: the C12-style compact id must land on the
        # survey-spaced network node 'M (0,3; 1,0)'.
        resp = client.post(
            "/api/v1/control/plan", json={"demands": {"M(0,3;1,0)": 2.0}}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["head_flow_m3s"] == pytest.approx(2.0)
        into = [r for r in body["reaches"] if r["downstream"] == "M(0,3;1,0)"]
        assert into and into[0]["required_flow_m3s"] == pytest.approx(2.0)

    def test_response_reach_ids_are_canonical_compact(self, client):
        # Some upstream sources carry survey spacing; the response contract is the exact
        # normalized edge set — not merely "no spaces".
        from core.node_id import normalize_node_id

        resp = client.post(
            "/api/v1/control/plan", json={"demands": {"M (0,3; 1,0)": 2.0}}
        )
        assert resp.status_code == 200
        expected = {
            (normalize_node_id(u), normalize_node_id(v))
            for u, v in json.loads(Path(NETWORK).read_text())["edges"]
        }
        got = {(r["upstream"], r["downstream"]) for r in resp.json()["reaches"]}
        assert got == expected
        assert all(" " not in node for edge in got for node in edge)

    def test_missing_geometry_ids_are_canonical_compact(self, client):
        from core.node_id import normalize_node_id

        resp = client.post(
            "/api/v1/control/plan", json={"demands": {}, "apply_losses": True}
        )
        assert resp.status_code == 200
        missing = {tuple(edge) for edge in resp.json()["reaches_missing_geometry"]}
        expected = {
            (normalize_node_id(u), normalize_node_id(v))
            for u, v in NetworkFlowController(
                NETWORK, GEOMETRY
            ).reaches_missing_geometry
        }
        assert missing == expected
        assert len(missing) == 17
        assert all(" " not in node for edge in missing for node in edge)

    def test_colliding_demand_aliases_are_rejected_400(self, client):
        resp = client.post(
            "/api/v1/control/plan",
            json={"demands": {"M(0,3;1,0)": 1.0, "M (0,3; 1,0)": 2.0}},
        )
        assert resp.status_code == 400
        assert "collide" in resp.json()["detail"]

    def test_zero_demand_with_losses_has_zero_head_flow(self, client):
        # D1: dry reaches take no seepage — an empty plan demands nothing at the head
        # (pre-D1 this returned ~2.46 m3/s of phantom whole-network seepage).
        resp = client.post(
            "/api/v1/control/plan", json={"demands": {}, "apply_losses": True}
        )
        assert resp.status_code == 200
        assert resp.json()["head_flow_m3s"] == 0.0

    def test_charge_dry_reaches_restores_legacy_whole_network_mode(self, client):
        resp = client.post(
            "/api/v1/control/plan",
            json={"demands": {}, "apply_losses": True, "charge_dry_reaches": True},
        )
        assert resp.status_code == 200
        assert resp.json()["head_flow_m3s"] > 2.0  # all-surveyed-reach seepage (~2.46)
        assert resp.json()["charge_dry_reaches"] is True

    def test_always_wet_keeps_named_trunk_charged(self, client):
        resp = client.post(
            "/api/v1/control/plan",
            json={
                "demands": {},
                "apply_losses": True,
                "always_wet": [["M(0,0)", "M(0,2)"]],
            },
        )
        assert resp.status_code == 200
        assert 0.0 < resp.json()["head_flow_m3s"] < 1.0  # one reach's seepage only

    def test_unknown_always_wet_reach_is_rejected_400(self, client):
        resp = client.post(
            "/api/v1/control/plan",
            json={
                "demands": {},
                "apply_losses": True,
                "always_wet": [["M(0,0)", "M(9,9)"]],
            },
        )
        assert resp.status_code == 400

    def test_always_wet_reach_without_geometry_is_rejected_400(self, client):
        resp = client.post(
            "/api/v1/control/plan",
            json={"demands": {}, "apply_losses": True, "always_wet": [["S", "M(0,0)"]]},
        )
        assert resp.status_code == 400
        assert "no surveyed geometry" in resp.json()["detail"]

    def test_loss_knobs_without_apply_losses_are_rejected_400(self, client):
        resp = client.post(
            "/api/v1/control/plan", json={"demands": {}, "charge_dry_reaches": True}
        )
        assert resp.status_code == 400

    def test_negative_demand_is_rejected_400(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {"M(0,2)": -1.0}})
        assert resp.status_code == 400

    def test_boolean_demand_value_is_rejected_422(self, client):
        # A JSON boolean coerces to 1.0 under the float map, phantom demand; reject it.
        resp = client.post("/api/v1/control/plan", json={"demands": {"M(0,2)": True}})
        assert resp.status_code == 422

    def test_demand_on_source_is_rejected_400(self, client):
        resp = client.post("/api/v1/control/plan", json={"demands": {"S": 1.0}})
        assert resp.status_code == 400

    def test_non_finite_demand_is_rejected_not_500(self, client):
        # 1e400 is valid JSON that parses to +inf; it must be rejected as a client error (422),
        # never reach the engine and crash serialization with a 500.
        resp = client.post(
            "/api/v1/control/plan",
            content='{"demands": {"M(0,2)": 1e400}}',
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400  # handler _validate path, not a schema-level 422
        assert "not finite" in resp.json()["detail"]


class TestDesignProfileEndpoint:
    def test_returns_all_zones_with_non_actuating_truth_labels(self, design_client):
        response = design_client.post(
            "/api/v1/control/hydraulic-forecast/design", json={}
        )
        assert response.status_code == 200
        body = response.json()
        assert {
            "mode": body["mode"],
            "open_loop": body["open_loop"],
            "actual_state_known": body["actual_state_known"],
            "commandable": body["commandable"],
        } == {
            "mode": "design_profile",
            "open_loop": True,
            "actual_state_known": False,
            "commandable": False,
        }
        assert [zone["zone"] for zone in body["zones"]] == [1, 2, 3, 4, 5, 6]
        assert [
            zone["zone"] for zone in body["zones"] if zone["status"] == "unavailable"
        ] == []

    def test_subset_is_canonicalized_to_zone_order(self, design_client):
        response = design_client.post(
            "/api/v1/control/hydraulic-forecast/design",
            json={"zones": [6, 1], "flow_fraction": 0.5},
        )
        assert response.status_code == 200
        assert [zone["zone"] for zone in response.json()["zones"]] == [1, 6]

    @pytest.mark.parametrize("zones", [[], [True], [0], [7], [1, 1]])
    def test_rejects_invalid_zone_selection(self, design_client, zones):
        response = design_client.post(
            "/api/v1/control/hydraulic-forecast/design",
            json={"zones": zones},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("flow_fraction", [True, -0.1])
    def test_rejects_invalid_flow_fraction(self, design_client, flow_fraction):
        response = design_client.post(
            "/api/v1/control/hydraulic-forecast/design",
            json={"flow_fraction": flow_fraction},
        )
        assert response.status_code == 422

    def test_returns_503_when_design_service_is_not_initialized(self):
        control = _load_control()
        control.design_profile_service = None
        app = FastAPI()
        app.include_router(control.router, prefix="/api/v1/control")
        response = TestClient(app).post(
            "/api/v1/control/hydraulic-forecast/design",
            json={"zones": [6]},
        )
        assert response.status_code == 503


class TestErrorMapping:
    def test_topology_error_maps_to_503_not_400(self):
        # NetworkTopologyError subclasses ValueError; a server/config topology error must
        # surface as 503, not be mis-reported as a 400 client error.
        from core.network_topology import NetworkTopologyError

        control = _load_control()

        class _BadController:
            reaches_missing_geometry = set()

            def required_flow_per_reach(self, demands, **kwargs):
                raise NetworkTopologyError("network is not a spanning tree")

        control.flow_controller = _BadController()
        app = FastAPI()
        app.include_router(control.router, prefix="/api/v1/control")
        resp = TestClient(app).post(
            "/api/v1/control/plan", json={"demands": {"M(0,2)": 1.0}}
        )
        assert resp.status_code == 503


class TestFailClosed:
    def test_503_when_controller_not_initialized(self):
        control = _load_control()
        control.flow_controller = None
        app = FastAPI()
        app.include_router(control.router, prefix="/api/v1/control")
        resp = TestClient(app).post(
            "/api/v1/control/plan", json={"demands": {"M(0,2)": 1.0}}
        )
        assert resp.status_code == 503

    def test_get_system_demand_no_longer_fabricates_25(self):
        # The 25.0 stub must be gone and replaced with a fail-closed raise (verified on source
        # to avoid importing the DB/settings-coupled controller module).
        src = (
            SERVICE_ROOT / "src" / "controllers" / "dual_mode_gate_controller.py"
        ).read_text()
        assert 'return {"total_demand": 25.0}' not in src
        assert "no demand source wired" in src

    def test_manual_instructions_surface_unavailable_demand(self):
        # Retiring the 25.0 stub must NOT make generate_manual_instructions silently return []
        # (its live route would report "no instructions" instead of "demand unavailable").
        import asyncio

        # lazy import so this file's other tests don't depend on the DB/settings import chain
        from controllers.dual_mode_gate_controller import DualModeGateController

        controller = DualModeGateController.__new__(
            DualModeGateController
        )  # skip heavy __init__
        controller.gate_states = {}
        with pytest.raises(RuntimeError, match="no demand source"):
            asyncio.run(controller.generate_manual_instructions())


def _fresh_levels():
    from datetime import datetime, timezone

    now_iso = datetime.now(
        timezone.utc
    ).isoformat()  # always fresh vs the handler's now
    return {
        node: {"water_level_m": level, "observed_at": now_iso}
        for node, level in (("S", 3.0), ("M(0,0)", 2.5), ("M(0,2)", 2.0))
    }


class TestOpeningsEndpoint:
    # Wave 2.7 /control wiring: POST /openings turns a demand + freshness-stamped real
    # levels into per-gate openings, but fails closed (never an assumed command) when a
    # reach's boundary level is missing/stale/future, its canal capacity is not fully
    # surveyed, OR the calibration bundle is not approved for actuation. The default bundle
    # is planning_only (defaulted sills; the strict loader ENFORCES planning_only), so with
    # real data NOTHING is commanded — every demand-carrying reach is opening-unavailable.
    def test_planning_only_bundle_commands_nothing(self, client):
        resp = client.post(
            "/api/v1/control/openings",
            json={
                "demands": {"M(0,2)": 5.0},
                "levels": _fresh_levels(),
                "max_level_age_seconds": 3600,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["openings"] == []  # nothing commanded on planning-only calibration
        unavailable = {(u["upstream"], u["downstream"]): u for u in body["unavailable"]}
        # S->M(0,0) has fresh levels + a known (gate) bound, yet is still not commanded.
        assert (
            unavailable[("S", "M(0,0)")]["reason"]
            == "calibration_not_actuation_approved"
        )
        # M(0,0)->M(0,2) is a partial survey -> capacity blocks it before actuation.
        assert unavailable[("M(0,0)", "M(0,2)")]["reason"] == "capacity_unsurveyed"
        assert body["summary"]["feasible"] is False
        assert body["summary"]["commanded_reaches"] == 0
        assert body["summary"]["idle_reaches"] == 56

    def test_missing_level_is_reported_before_the_actuation_gate(self, client):
        levels = _fresh_levels()
        del levels["M(0,2)"]  # downstream boundary of M(0,0)->M(0,2) absent
        body = client.post(
            "/api/v1/control/openings",
            json={
                "demands": {"M(0,2)": 5.0},
                "levels": levels,
                "max_level_age_seconds": 3600,
            },
        ).json()
        unavailable = {(u["upstream"], u["downstream"]): u for u in body["unavailable"]}
        assert unavailable[("M(0,0)", "M(0,2)")]["reason"] == "level_missing"
        assert body["summary"]["feasible"] is False

    def test_stale_level_is_reported(self, client):
        from datetime import datetime, timedelta, timezone

        levels = _fresh_levels()
        levels["M(0,0)"]["observed_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).isoformat()
        body = client.post(
            "/api/v1/control/openings",
            json={
                "demands": {"M(0,2)": 5.0},
                "levels": levels,
                "max_level_age_seconds": 3600,
            },
        ).json()
        reasons = {
            (u["upstream"], u["downstream"]): u["reason"] for u in body["unavailable"]
        }
        # M(0,0) is a boundary of both active reaches; the stale level blocks both first.
        assert reasons[("S", "M(0,0)")] == "level_stale"
        assert reasons[("M(0,0)", "M(0,2)")] == "level_stale"

    def test_summary_reports_counts_without_double_counted_flow_totals(self, client):
        # The summary reports feasibility + counts, NOT a per-reach flow sum: the same 5
        # m3/s flows through both serial reaches, so a network requested/deficit total would
        # double-count it (10.0) and diverge from /plan's head_flow. Those fields are absent.
        body = client.post(
            "/api/v1/control/openings",
            json={
                "demands": {"M(0,2)": 5.0},
                "levels": _fresh_levels(),
                "max_level_age_seconds": 3600,
            },
        ).json()
        summary = body["summary"]
        assert summary["feasible"] is False
        assert summary["commanded_reaches"] == 0
        assert summary["unavailable_reaches"] == len(body["unavailable"]) == 2
        assert summary["idle_reaches"] == 56
        assert "requested_m3s" not in summary and "deficit_m3s" not in summary

    def test_boolean_demand_value_is_rejected_422(self, client):
        # A JSON boolean demand would coerce to 1.0 m3/s of phantom demand; reject it.
        resp = client.post(
            "/api/v1/control/openings",
            json={
                "demands": {"M(0,2)": True},
                "levels": _fresh_levels(),
                "max_level_age_seconds": 3600,
            },
        )
        assert resp.status_code == 422

    def test_boolean_water_level_is_rejected_422(self, client):
        # A JSON boolean would coerce to 1.0 under a float field; reject at the boundary.
        resp = client.post(
            "/api/v1/control/openings",
            json={
                "demands": {},
                "levels": {
                    "M(0,0)": {
                        "water_level_m": True,
                        "observed_at": "2026-07-13T12:00:00Z",
                    }
                },
                "max_level_age_seconds": 3600,
            },
        )
        assert resp.status_code == 422

    def test_non_finite_sla_is_400_not_500(self, client):
        # NaN passes the (constraint-free) schema and is rejected in the handler with a
        # clean 400, never a NaN-echoing 422 that fails serialization with a 500.
        resp = client.post(
            "/api/v1/control/openings",
            content='{"demands": {}, "levels": {}, "max_level_age_seconds": NaN}',
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert "max_level_age_seconds" in resp.json()["detail"]

    def test_missing_freshness_sla_is_rejected_422(self, client):
        resp = client.post(
            "/api/v1/control/openings",
            json={"demands": {}, "levels": {}},  # no max_level_age_seconds
        )
        assert resp.status_code == 422

    def test_unknown_level_key_is_rejected_400(self, client):
        levels = _fresh_levels()
        levels["M(9,9)"] = {
            "water_level_m": 2.0,
            "observed_at": _fresh_levels()["S"]["observed_at"],
        }
        resp = client.post(
            "/api/v1/control/openings",
            json={
                "demands": {"M(0,2)": 5.0},
                "levels": levels,
                "max_level_age_seconds": 3600,
            },
        )
        assert resp.status_code == 400
        assert "unknown node" in resp.json()["detail"]

    def test_503_when_controller_not_initialized(self):
        control = _load_control()
        control.flow_controller = None
        app = FastAPI()
        app.include_router(control.router, prefix="/api/v1/control")
        resp = TestClient(app).post(
            "/api/v1/control/openings",
            json={"demands": {}, "levels": {}, "max_level_age_seconds": 3600},
        )
        assert resp.status_code == 503
