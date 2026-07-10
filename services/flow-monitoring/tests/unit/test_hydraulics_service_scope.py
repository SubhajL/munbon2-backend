"""
Wave 1.3 regression tests: the hydraulics service is app-scoped and runs on the same
canonical configs as /control. Before this item the router was dead-on-arrival — a
container-absolute geometry path, two solver-constructor arity mismatches, a fresh
never-connected DatabaseManager per request, and a None-deref when the legacy
simulation seam fails.

Needs numpy + the full requirements (like test_strict_null_consumers); DB objects are
constructed but never connected. Run isolated from the service root:
    PYTHONPATH=src pytest --noconftest -o addopts="" tests/unit/test_hydraulics_service_scope.py
"""
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from core.node_id import normalize_node_id  # noqa: E402
from db.connections import DatabaseManager  # noqa: E402
from services.hydraulic_service import HydraulicService  # noqa: E402

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NETWORK = SERVICE_ROOT / "src" / "config" / "network.json"
GEOMETRY = SERVICE_ROOT / "src" / "config" / "canal_geometry.json"
HYDRAULICS_PY = SERVICE_ROOT / "src" / "api" / "hydraulics.py"


@pytest.fixture(scope="module")
def service():
    # Offline construction: the DatabaseManager is never connected; solver setup and
    # config loading must not require any I/O beyond the canonical config files.
    return HydraulicService(DatabaseManager())


class TestAppScopedConstruction:
    def test_constructs_offline_on_canonical_configs(self, service):
        assert service.hydraulic_solver is not None
        assert service.path_solver is not None
        # Never consumed by anything; construction dropped (travel time is Wave 3.2).
        assert service.temporal_scheduler is None

    def test_capacity_index_is_warm_and_populated(self, service):
        assert len(service._canal_capacity_index()) > 0

    def test_canonical_geometry_joins_all_37_sections(self, service):
        sections = service.hydraulic_solver.canal_sections
        assert len(sections) == 37
        assert "M(0,0)->M(0,1)" in sections  # normalized compact keys

    def test_head_loss_lookup_joins_spaced_network_ids(self, service):
        # The network file spells 44/59 ids with survey spacing while geometry keys
        # normalize compact — the head-loss lookup must join them, not silently
        # return 0.0 for every real reach.
        sections = service.hydraulic_solver.canal_sections
        edges = json.loads(NETWORK.read_text())["edges"]
        surveyed = [
            (u, v)
            for u, v in edges
            if f"{normalize_node_id(u)}->{normalize_node_id(v)}" in sections
        ]
        assert surveyed, "no network edge matched a surveyed section"
        losses = [
            service.hydraulic_solver.calculate_canal_head_loss(u, v, 2.0)
            for u, v in surveyed
        ]
        assert any(loss > 0 for loss in losses)


class TestFindDeliveryPaths:
    def test_path_from_source_with_downstream_gate_ids(self, service):
        paths = service.path_solver.find_delivery_paths({"M (0,3; 1,0)": 2.0})
        assert set(paths) == {"M (0,3; 1,0)"}
        info = paths["M (0,3; 1,0)"]
        assert info["nodes"][0] == "S"
        assert info["nodes"][-1] == "M (0,3; 1,0)"
        # Each reach's physical gate is its downstream valve.
        assert info["gates"] == info["nodes"][1:]
        assert info["total_flow"] == pytest.approx(2.0)

    def test_compact_alias_resolves_to_same_path(self, service):
        spaced = service.path_solver.find_delivery_paths({"M (0,3; 1,0)": 2.0})
        compact = service.path_solver.find_delivery_paths({"M(0,3;1,0)": 2.0})
        assert list(spaced.values()) == list(compact.values())

    def test_unknown_node_fails_closed(self, service):
        with pytest.raises(ValueError, match="unknown"):
            service.path_solver.find_delivery_paths({"M(7,7)": 1.0})

    def test_colliding_aliases_fail_closed(self, service):
        with pytest.raises(ValueError, match="collide"):
            service.path_solver.find_delivery_paths(
                {"M(0,3;1,0)": 1.0, "M (0,3; 1,0)": 2.0}
            )


class TestTravelTimeJoin:
    def test_travel_time_joins_spaced_ids_to_surveyed_section(self, service):
        # Same normalized-join requirement as head loss: a surveyed reach queried
        # with the network's survey-spaced spelling must use its real geometry,
        # not the no-geometry default estimate.
        controller = service.hydraulic_solver.controller
        edges = json.loads(NETWORK.read_text())["edges"]
        spaced = [
            (u, v)
            for u, v in edges
            if " " in v
            and f"{normalize_node_id(u)}->{normalize_node_id(v)}"
            in controller.canal_sections
        ]
        assert spaced, "no spaced surveyed reach found"
        u, v = spaced[0]
        key = f"{normalize_node_id(u)}->{normalize_node_id(v)}"
        length = controller.canal_sections[key].length_m
        travel_s = controller.calculate_travel_time(u, v, 2.0)
        # Geometry-based: finite, positive, and consistent with the section length
        # at physical open-channel velocities (~0.1–5 m/s) — the default estimate
        # uses km markers/1km guesses instead.
        assert travel_s > 0
        velocity = length / travel_s
        assert 0.05 < velocity < 5.0


class TestVerifySchedule:
    """The service-level verify_schedule regression deferred from PR #26 (F-01b)."""

    def test_below_floor_delivery_reports_gate_flow_infeasible(self, service):
        # 0.001 m3/s is far below any calibrated gate's Cs-floor discharge: the
        # corrected inverse must fail closed and verify_schedule must surface it as
        # a violation instead of pretending the schedule is deliverable.
        result = asyncio.run(
            service.verify_schedule([{"node_id": "M(0,2)", "flow_rate": 0.001}])
        )
        assert result["is_feasible"] is False
        kinds = {v["type"] for v in result["violations"]}
        assert "gate_flow_infeasible" in kinds

    def test_duplicate_deliveries_to_one_node_combine(self, service):
        # A dict overwrite would silently verify only the LAST delivery; the reach
        # must carry the combined flow.
        single = asyncio.run(
            service.verify_schedule([{"node_id": "M(0,1)", "flow_rate": 4.0}])
        )
        combined = asyncio.run(
            service.verify_schedule(
                [
                    {"node_id": "M(0,1)", "flow_rate": 2.0},
                    {"node_id": "M(0,1)", "flow_rate": 2.0},
                ]
            )
        )
        assert combined["total_demand"] == pytest.approx(4.0)
        assert (
            combined["required_gate_settings"] == single["required_gate_settings"]
        )

    def test_simulation_unavailable_is_fail_closed_not_a_crash(self, service):
        # The legacy solver-simulation seam returns None (its API never matched);
        # verify_schedule must treat that as not-verified, never AttributeError.
        result = asyncio.run(
            service.verify_schedule([{"node_id": "M(0,1)", "flow_rate": 3.0}])
        )
        assert result["is_feasible"] is False
        assert result["convergence"] is None
        assert any("simulation unavailable" in w for w in result["warnings"])


def _load_router_module():
    spec = importlib.util.spec_from_file_location(
        "flowmon_hydraulics_under_test", str(HYDRAULICS_PY)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestModelFacadesAre501(object):
    """Decision 2 (PROGRAM_REVIEW §2.0): the constant-returning model façades
    (manning 5.0 / saint-venant 5.2 / rating 4.8, dummy gauges, fake calibration)
    are deleted; their routes answer an honest 501, never fabricated hydraulics."""

    @pytest.fixture()
    def client(self, service):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        module = _load_router_module()
        module.hydraulic_service = service
        app = FastAPI()
        app.include_router(module.router, prefix="/api/v1/hydraulics")
        return TestClient(app)

    UUID_S = "12345678-1234-5678-1234-567812345678"

    def test_model_route_is_501(self, client):
        resp = client.get(
            f"/api/v1/hydraulics/model?location_id={self.UUID_S}&model_type=manning"
        )
        assert resp.status_code == 501

    def test_propagation_route_is_501(self, client):
        resp = client.post(
            "/api/v1/hydraulics/model/propagation",
            json={
                "start_location_id": self.UUID_S,
                "flow_rate": 3.0,
                "duration_hours": 2,
            },
        )
        assert resp.status_code == 501

    def test_ungauged_route_is_501(self, client):
        resp = client.get(f"/api/v1/hydraulics/model/ungauged/{self.UUID_S}")
        assert resp.status_code == 501

    def test_calibrate_route_is_501(self, client):
        resp = client.post(
            "/api/v1/hydraulics/model/calibrate",
            json={
                "location_id": self.UUID_S,
                "observed_data": [{"flow": 1.0}],
                "model_type": "manning",
            },
        )
        assert resp.status_code == 501

    def test_model_route_is_501_even_before_lifespan_init(self):
        # The 501 must not be masked by the 503 dependency: these routes answer 501
        # whether or not the lifespan built the service (no Depends on them).
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        module = _load_router_module()
        assert module.hydraulic_service is None
        app = FastAPI()
        app.include_router(module.router, prefix="/api/v1/hydraulics")
        resp = TestClient(app).get(
            f"/api/v1/hydraulics/model?location_id={self.UUID_S}&model_type=manning"
        )
        assert resp.status_code == 501

    def test_verify_schedule_stays_alive(self, client):
        resp = client.post(
            "/api/v1/hydraulics/verify-schedule",
            json={"schedule": {"deliveries": [{"node_id": "M(0,1)", "flow_rate": 3.0}]}},
        )
        assert resp.status_code == 200


class TestHonestCapacities:
    def test_system_capacity_is_the_head_reach_rating_not_30(self, service):
        # The canonical head gate M(0,0) is rated 11.2 m3/s; the old hardcoded 30.0
        # let physically impossible schedules pass the total-demand gate.
        assert asyncio.run(service._get_system_capacity()) == pytest.approx(11.2)

    def test_system_capacity_fails_closed_without_head_rating(self, service):
        service_copy = HydraulicService(DatabaseManager())
        service_copy._canal_cap_index_cache = {}  # simulate a network with no ratings
        with pytest.raises(ValueError):
            asyncio.run(service_copy._get_system_capacity())

    def test_gate_capacity_prefers_the_rated_q_max(self, service):
        assert service._get_gate_capacity("M(0,0)") == pytest.approx(11.2)

    def test_gate_capacity_falls_back_to_flow_law_when_unrated(self, service):
        # M(0,1) has no rated q_max in the calibration table: the capacity comes
        # from the corrected flow law at max opening — never the old flat 10.0.
        capacity = service._get_gate_capacity("M(0,1)")
        assert capacity > 0
        assert capacity != pytest.approx(10.0)

    def test_gate_capacity_fallback_on_default_calibration_is_logged(
        self, service, monkeypatch
    ):
        import services.hydraulic_service as hs

        warnings = []
        monkeypatch.setattr(
            hs.logger, "warning", lambda msg, *a, **k: warnings.append(msg % a if a else msg)
        )
        service._get_gate_capacity("M(0,1)")  # default_by_size calibration
        assert any("calibration" in w for w in warnings)

    def test_verify_schedule_utilization_uses_honest_capacity(self, service):
        result = asyncio.run(
            service.verify_schedule([{"node_id": "M(0,1)", "flow_rate": 3.0}])
        )
        assert result["system_utilization"] == pytest.approx(3.0 / 11.2)

    def test_over_capacity_demand_fails_the_total_demand_gate(self, service):
        # 15 m3/s cannot enter an 11.2 m3/s head no matter the gate settings; under
        # the old 30.0 this sailed through to per-gate checks.
        result = asyncio.run(
            service.verify_schedule([{"node_id": "M(0,1)", "flow_rate": 15.0}])
        )
        assert result["is_feasible"] is False
        assert result["reason"] == "Total demand exceeds system capacity"
        assert result["system_capacity"] == pytest.approx(11.2)
        # same field name as the full-verification response, not a divergent alias
        assert result["system_utilization"] == pytest.approx(15.0 / 11.2)


class TestDependencyIsAppScoped:
    def _load_router_module(self):
        return _load_router_module()

    def test_returns_503_before_lifespan_initializes(self):
        from fastapi import HTTPException

        module = self._load_router_module()
        assert module.hydraulic_service is None
        with pytest.raises(HTTPException) as exc:
            module.get_hydraulic_service()
        assert exc.value.status_code == 503

    def test_returns_the_registered_singleton(self, service):
        module = self._load_router_module()
        module.hydraulic_service = service
        assert module.get_hydraulic_service() is service
