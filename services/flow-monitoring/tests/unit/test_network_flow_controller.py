"""
Unit tests for core.network_flow_controller.NetworkFlowController — the spec-§10
consolidation module. This increment covers only the A1–A3 aggregation entry point
loaded against the real canonical network. Pure/stdlib; run in isolation:
    pytest --noconftest tests/unit/test_network_flow_controller.py
"""
import json
import re
from pathlib import Path

import pytest

from core.network_topology import NetworkTopologyError
from core.network_flow_controller import NetworkFlowController

CANONICAL = Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"
GEOMETRY_CFG = Path(__file__).resolve().parents[2] / "src" / "config" / "canal_geometry.json"


def _area_demand():
    gates = json.loads(CANONICAL.read_text())["gates"]
    return {
        g: float(m["area"])
        for g, m in gates.items()
        if isinstance(m.get("area"), (int, float)) and m["area"] > 0
    }


class TestConstruction:
    def test_loads_and_guards_canonical_network(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        assert len(ctrl.edges) == 59
        assert ("S", "M(0,0)") in ctrl.edges

    def test_rejects_fragmented_network(self, tmp_path):
        # A network whose nodes are not all reachable from S must fail at construction.
        bad = tmp_path / "fragmented.json"
        bad.write_text(json.dumps({
            "gates": {"M(0,0)": {}, "M(9,9)": {}},
            "edges": [["S", "M(0,0)"], ["X", "M(9,9)"]],
        }))
        with pytest.raises(NetworkTopologyError):
            NetworkFlowController(str(bad))


class TestRequiredFlowPerReach:
    def test_aggregates_real_network_demand_with_conservation(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        gates = json.loads(CANONICAL.read_text())["gates"]
        demand = {
            g: float(m["area"])
            for g, m in gates.items()
            if isinstance(m.get("area"), (int, float)) and m["area"] > 0
        }
        flow = ctrl.required_flow_per_reach(demand)

        assert set(flow) == set(ctrl.edges)
        head = sum(q for (u, _), q in flow.items() if u == "S")
        assert head == pytest.approx(sum(demand.values()))

    def test_rejects_demand_for_unknown_node(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        with pytest.raises(ValueError):
            ctrl.required_flow_per_reach({"Zone2": 10.0})


class TestConveyanceLossWiring:
    def test_no_geometry_path_has_no_sections(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        assert ctrl.sections == {}

    def test_geometry_load_flags_reaches_without_survey_data(self):
        ctrl = NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))
        assert len(ctrl.sections) == 37
        assert len(ctrl.reaches_missing_geometry) == 22  # 59 edges - 37 surveyed

    def test_apply_losses_lifts_head_flow_above_lossless(self):
        ctrl = NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))
        demand = _area_demand()
        head_lossy = sum(
            q for (u, _), q in ctrl.required_flow_per_reach(demand, apply_losses=True).items()
            if u == "S"
        )
        head_lossless = sum(
            q for (u, _), q in ctrl.required_flow_per_reach(demand, apply_losses=False).items()
            if u == "S"
        )
        assert head_lossy > head_lossless

    def test_apply_losses_false_is_the_lossless_a1_a3_result(self):
        ctrl = NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))
        demand = _area_demand()
        assert ctrl.required_flow_per_reach(demand, apply_losses=False) == (
            ctrl.required_flow_per_reach(demand)
        )

    def test_lmc_seepage_per_km_is_in_the_aged_concrete_field_range(self):
        # Physical-plausibility guard on the calibrated seepage_rate: delivering design flow
        # to the LMC tail loses seepage at a per-km rate within the verified aged-concrete
        # field range (new concrete ~10 L/s/km; aged Menemen main ~108 L/s/km). Rejects both
        # the too-low new-concrete standard (~2 L/s/km) and an implausibly high rate.
        ctrl = NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))
        tail = next(g for g in json.loads(CANONICAL.read_text())["gates"]
                    if re.sub(r"\s+", "", g) == "M(0,12)")
        # M(0,12) is the only demand node -> flow (and seepage) only on the LMC mainstem path.
        flow = ctrl.required_flow_per_reach({tail: 8.737}, apply_losses=True)
        seepage_l_s = (sum(q for (u, _), q in flow.items() if u == "S") - 8.737) * 1000.0
        lmc_km = sum(
            s["length_m"] for (u, v), s in ctrl.sections.items()
            if re.fullmatch(r"M\(0,\d+\)", u) and re.fullmatch(r"M\(0,\d+\)", v)
        ) / 1000.0
        per_km = seepage_l_s / lmc_km
        assert 20.0 < per_km < 120.0, f"{per_km:.1f} L/s/km outside aged-concrete field range"
