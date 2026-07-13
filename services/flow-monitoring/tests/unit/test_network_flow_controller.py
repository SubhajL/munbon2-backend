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
        # Schema-valid (Wave 1.1 strict loader passes) but graph-invalid: the B<->C
        # cycle hangs free of the source.
        bad = tmp_path / "fragmented.json"
        bad.write_text(json.dumps({
            "metadata": {"canonical": True, "total_gates": 3, "total_connections": 3},
            "gates": {"M(0,0)": {}, "M(5,0)": {}, "M(5,1)": {}},
            "edges": [["S", "M(0,0)"], ["M(5,0)", "M(5,1)"], ["M(5,1)", "M(5,0)"]],
        }))
        with pytest.raises(NetworkTopologyError):
            NetworkFlowController(str(bad))

    def test_rejects_connected_but_non_tree_network(self, tmp_path):
        # A diamond is fully reachable from S but not a spanning tree (C has two parents);
        # aggregation would double-count it, so it must fail at construction, not per-request.
        diamond = tmp_path / "diamond.json"
        diamond.write_text(json.dumps({
            "metadata": {"canonical": True, "total_gates": 3, "total_connections": 4},
            "gates": {"M(0,1)": {}, "M(0,2)": {}, "M(9,9)": {}},
            "edges": [
                ["S", "M(0,1)"], ["S", "M(0,2)"],
                ["M(0,1)", "M(9,9)"], ["M(0,2)", "M(9,9)"],
            ],
        }))
        with pytest.raises(NetworkTopologyError):
            NetworkFlowController(str(diamond))

    def test_rejects_network_with_normalized_node_collision(self, tmp_path):
        # "M(0,1)" and "M (0,1)" are the same physical gate; a network carrying both
        # would make any-spacing demand resolution ambiguous — the strict loader
        # refuses it before the controller is even built.
        from core.config_loader import ConfigError

        twin = tmp_path / "twin.json"
        twin.write_text(json.dumps({
            "metadata": {"canonical": True, "total_gates": 3, "total_connections": 3},
            "gates": {"M(0,0)": {}, "M(0,1)": {}, "M (0,1)": {}},
            "edges": [["S", "M(0,0)"], ["M(0,0)", "M(0,1)"], ["M(0,0)", "M (0,1)"]],
        }))
        with pytest.raises(ConfigError, match="collide"):
            NetworkFlowController(str(twin))

    def test_rejects_geometry_file_with_no_usable_sections(self, tmp_path):
        # Geometry given but empty -> losses would silently be zero; fail closed instead.
        empty = tmp_path / "geo.json"
        empty.write_text(json.dumps({"canal_sections": []}))
        with pytest.raises(ValueError):
            NetworkFlowController(str(CANONICAL), geometry_path=str(empty))


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

    def test_accepts_compact_demand_alias_for_spaced_network_node(self):
        # 44/59 network ids carry survey spacing ("M (0,3; 1,0)"); a C12-style producer
        # sends the compact canonical form — it must land on the same node (Wave 1.2).
        ctrl = NetworkFlowController(str(CANONICAL))
        flow = ctrl.required_flow_per_reach({"M(0,3;1,0)": 2.0})
        assert flow[("M(0,3)", "M (0,3; 1,0)")] == pytest.approx(2.0)

    def test_spaced_and_compact_demands_produce_identical_plans(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        spaced = ctrl.required_flow_per_reach({"M (0,3; 1,0)": 2.0})
        compact = ctrl.required_flow_per_reach({"M(0,3;1,0)": 2.0})
        assert spaced == compact

    def test_rejects_demand_keys_that_collide_after_normalization(self):
        # Two textual keys naming one physical gate cannot silently double-specify.
        ctrl = NetworkFlowController(str(CANONICAL))
        with pytest.raises(ValueError, match="collide"):
            ctrl.required_flow_per_reach({"M(0,3;1,0)": 1.0, "M (0,3; 1,0)": 2.0})

    def test_source_demand_still_rejected_through_normalization(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        with pytest.raises(ValueError, match="source"):
            ctrl.required_flow_per_reach({"S": 1.0})


class TestConveyanceLossWiring:
    def test_no_geometry_path_has_no_sections(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        assert ctrl.sections == {}

    def test_geometry_load_flags_reaches_without_survey_data(self):
        ctrl = NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))
        assert len(ctrl.sections) == 42
        # 17 = 59 edges - 42 surveyed serial reaches (2.1b): the source edge,
        # 13 junction heads and 3 offtakes have no chainage span to survey.
        assert len(ctrl.reaches_missing_geometry) == 17

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
        # M(0,12) is the only demand node, and dry reaches take no loss (D1), so seepage
        # accrues ONLY on the S->M(0,12) mainstem supply path — numerator and the LMC-km
        # denominator now measure the same canal (the pre-D1 hybrid overstated this ~68).
        flow = ctrl.required_flow_per_reach({tail: 8.737}, apply_losses=True)
        seepage_l_s = (sum(q for (u, _), q in flow.items() if u == "S") - 8.737) * 1000.0
        lmc_km = sum(
            segment["length_m"]
            for (u, v), segments in ctrl.sections.items()
            if re.fullmatch(r"M\(0,\d+\)", u) and re.fullmatch(r"M\(0,\d+\)", v)
            for segment in segments
        ) / 1000.0
        per_km = seepage_l_s / lmc_km
        assert 20.0 < per_km < 120.0, f"{per_km:.1f} L/s/km outside aged-concrete field range"


class TestDryReachSemantics:
    # D1 (PROGRAM_REVIEW_2026-07-09 §2.0): a plan charges seepage only on reaches in
    # service for that plan. Pre-D1, an empty plan demanded ~2.46 m3/s at the head.
    def _ctrl(self):
        return NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))

    def _head(self, flow):
        return sum(q for (u, _), q in flow.items() if u == "S")

    def test_zero_demand_with_losses_has_zero_head_flow(self):
        flow = self._ctrl().required_flow_per_reach({}, apply_losses=True)
        assert self._head(flow) == 0.0
        assert all(q == 0.0 for q in flow.values())

    def test_single_tail_demand_charges_only_its_supply_path(self):
        ctrl = self._ctrl()
        tail = next(g for g in json.loads(CANONICAL.read_text())["gates"]
                    if re.sub(r"\s+", "", g) == "M(0,12)")
        flow = ctrl.required_flow_per_reach({tail: 1.0}, apply_losses=True)
        parent = {c: p for p, c in ctrl.edges}
        path, node = set(), tail
        while node in parent:
            path.add((parent[node], node))
            node = parent[node]
        flowing = {edge for edge, q in flow.items() if q > 0.0}
        assert flowing == path  # nothing off the supply path is charged

    def test_partial_reaches_surface_their_boundary_chainage_gaps(self):
        # QCHECK 2.1b HIGH: the five partially surveyed reaches have their gaps
        # at the reach head/tail, invisible to between-segment measurement — the
        # geometry's `reaches` spans make them measurable. These values match
        # geometry_coverage.json's per-edge gap_m (same generator, same lock).
        ctrl = self._ctrl()
        gaps = {edge: round(gap, 3) for edge, gap in ctrl.reaches_with_chainage_gaps.items()}
        assert gaps == {
            ("M(0,0)", "M(0,1)"): 170.0,                        # flume, no cross-section
            ("M(0,1;1,3)", "M(0,1;1,4)"): 80.0,                 # RMC tail
            ("M(0,12;1,1;1,1)", "M(0,12;1,1;1,2)"): 30.0,       # 2R-38R tail
            ("M(0,12;1,2;1,1)", "M(0,12;1,2;1,2)"): 1200.0,     # 4L-38R unsurveyed
            ("M(0,12;1,2;1,0;1,0)", "M(0,12;1,2;1,0;1,1)"): 410.0,  # 5R-4L tail
        }

    def test_charge_dry_reaches_restores_whole_network_seepage(self):
        from core.conveyance_loss import reach_seepage_m3s

        ctrl = self._ctrl()
        flow = ctrl.required_flow_per_reach(
            {}, apply_losses=True, charge_dry_reaches=True
        )
        expected = sum(reach_seepage_m3s(s) for s in ctrl.sections.values())
        assert self._head(flow) == pytest.approx(expected)
        assert self._head(flow) > 2.0  # the legacy all-network figure (~2.46 m3/s)

    def test_always_wet_reach_stays_charged_in_an_empty_plan(self):
        from core.conveyance_loss import normalize_edge, reach_seepage_m3s

        ctrl = self._ctrl()
        edge = next(e for e in ctrl.edges
                    if normalize_edge(*e) == ("M(0,0)", "M(0,1)"))
        flow = ctrl.required_flow_per_reach(
            {}, apply_losses=True, always_wet=[list(edge)]
        )
        assert self._head(flow) == pytest.approx(
            reach_seepage_m3s(ctrl.sections[normalize_edge(*edge)])
        )

    def test_unknown_always_wet_reach_is_rejected(self):
        with pytest.raises(ValueError, match="always_wet"):
            self._ctrl().required_flow_per_reach(
                {}, apply_losses=True, always_wet=[["M(0,0)", "M(9,9)"]]
            )

    def test_always_wet_reach_without_geometry_is_rejected(self):
        # "Keep this reach charged" is unfulfillable without surveyed geometry — the loss
        # would silently be 0; the source edge S->M(0,0) is a real edge with no section.
        with pytest.raises(ValueError, match="no surveyed geometry"):
            self._ctrl().required_flow_per_reach(
                {}, apply_losses=True, always_wet=[["S", "M(0,0)"]]
            )

    def test_loss_knobs_without_apply_losses_are_rejected(self):
        ctrl = self._ctrl()
        with pytest.raises(ValueError, match="apply_losses"):
            ctrl.required_flow_per_reach({}, charge_dry_reaches=True)
        with pytest.raises(ValueError, match="apply_losses"):
            ctrl.required_flow_per_reach({}, always_wet=[["M(0,0)", "M(0,1)"]])


class TestReachCoverage:
    # Wave 2.8a observability: each reach reports the calibration confidence/method of
    # its terminating (downstream) gate and whether it has surveyed geometry — generic
    # feasibility fields, independent of the request. The data-lineage half (demand
    # version, workbook version, mapping) is 2.8b and gated on later waves.
    def _ctrl(self):
        return NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))

    def test_reach_coverage_has_one_entry_per_edge(self):
        ctrl = self._ctrl()
        assert set(ctrl.reach_coverage) == set(ctrl.edges)
        assert len(ctrl.reach_coverage) == 59

    def test_reach_confidence_and_method_come_from_the_downstream_gate(self):
        # Oracle: an INDEPENDENT calibration loader keyed on the reach's downstream node —
        # never the controller's own output. Every reach terminates at a real gate, so
        # the confidence/method must match that gate's calibration exactly.
        from utils.gate_calibration_loader import GateCalibrationLoader

        ctrl = self._ctrl()
        oracle = GateCalibrationLoader()
        for (upstream, downstream), cov in ctrl.reach_coverage.items():
            expected = oracle.get_calibration(downstream)
            assert cov.calibration_method == expected.calibration_method
            assert cov.confidence == pytest.approx(expected.confidence)

    def test_has_geometry_flags_the_surveyed_reaches(self):
        ctrl = self._ctrl()
        for edge, cov in ctrl.reach_coverage.items():
            assert cov.has_geometry == (edge not in ctrl.reaches_missing_geometry)
        surveyed = sum(1 for cov in ctrl.reach_coverage.values() if cov.has_geometry)
        assert surveyed == 42  # 59 edges - 17 missing (matches the /plan loss-coverage test)

    def test_coverage_summary_counts_geometry_and_calibration_method(self):
        summary = self._ctrl().coverage_summary()
        assert summary == {
            "total_reaches": 59,
            "geometry_surveyed": 42,
            "geometry_missing": 17,
            "chainage_gaps": 5,
            "calibration_method_counts": {"measured": 10, "inferred": 49},
        }
