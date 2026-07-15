"""
Unit tests for core.network_flow_controller.NetworkFlowController — the spec-§10
consolidation module. This increment covers only the A1–A3 aggregation entry point
loaded against the real canonical network. Pure/stdlib; run in isolation:
    pytest --noconftest tests/unit/test_network_flow_controller.py
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.network_topology import NetworkTopologyError
from core.network_flow_controller import NetworkFlowController

# A fixed instant so freshness tests are deterministic (never wall-clock).
NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)

CANONICAL = Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"
GEOMETRY_CFG = (
    Path(__file__).resolve().parents[2] / "src" / "config" / "canal_geometry.json"
)


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
        bad.write_text(
            json.dumps(
                {
                    "metadata": {
                        "canonical": True,
                        "total_gates": 3,
                        "total_connections": 3,
                    },
                    "gates": {"M(0,0)": {}, "M(5,0)": {}, "M(5,1)": {}},
                    "edges": [
                        ["S", "M(0,0)"],
                        ["M(5,0)", "M(5,1)"],
                        ["M(5,1)", "M(5,0)"],
                    ],
                }
            )
        )
        with pytest.raises(NetworkTopologyError):
            NetworkFlowController(str(bad))

    def test_rejects_connected_but_non_tree_network(self, tmp_path):
        # A diamond is fully reachable from S but not a spanning tree (C has two parents);
        # aggregation would double-count it, so it must fail at construction, not per-request.
        diamond = tmp_path / "diamond.json"
        diamond.write_text(
            json.dumps(
                {
                    "metadata": {
                        "canonical": True,
                        "total_gates": 3,
                        "total_connections": 4,
                    },
                    "gates": {"M(0,1)": {}, "M(0,2)": {}, "M(9,9)": {}},
                    "edges": [
                        ["S", "M(0,1)"],
                        ["S", "M(0,2)"],
                        ["M(0,1)", "M(9,9)"],
                        ["M(0,2)", "M(9,9)"],
                    ],
                }
            )
        )
        with pytest.raises(NetworkTopologyError):
            NetworkFlowController(str(diamond))

    def test_rejects_network_with_normalized_node_collision(self, tmp_path):
        # "M(0,1)" and "M (0,1)" are the same physical gate; a network carrying both
        # would make any-spacing demand resolution ambiguous — the strict loader
        # refuses it before the controller is even built.
        from core.config_loader import ConfigError

        twin = tmp_path / "twin.json"
        twin.write_text(
            json.dumps(
                {
                    "metadata": {
                        "canonical": True,
                        "total_gates": 3,
                        "total_connections": 3,
                    },
                    "gates": {"M(0,0)": {}, "M(0,1)": {}, "M (0,1)": {}},
                    "edges": [
                        ["S", "M(0,0)"],
                        ["M(0,0)", "M(0,1)"],
                        ["M(0,0)", "M (0,1)"],
                    ],
                }
            )
        )
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

    def test_accepts_spaced_demand_alias_for_canonical_network_node(self):
        ctrl = NetworkFlowController(str(CANONICAL))
        flow = ctrl.required_flow_per_reach({"M (0,3; 1,0)": 2.0})
        assert flow[("M(0,3)", "M(0,3;1,0)")] == pytest.approx(2.0)

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
            q
            for (u, _), q in ctrl.required_flow_per_reach(
                demand, apply_losses=True
            ).items()
            if u == "S"
        )
        head_lossless = sum(
            q
            for (u, _), q in ctrl.required_flow_per_reach(
                demand, apply_losses=False
            ).items()
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
        tail = next(
            g
            for g in json.loads(CANONICAL.read_text())["gates"]
            if re.sub(r"\s+", "", g) == "M(0,12)"
        )
        # M(0,12) is the only demand node, and dry reaches take no loss (D1), so seepage
        # accrues ONLY on the S->M(0,12) mainstem supply path — numerator and the LMC-km
        # denominator now measure the same canal (the pre-D1 hybrid overstated this ~68).
        flow = ctrl.required_flow_per_reach({tail: 8.737}, apply_losses=True)
        seepage_l_s = (
            sum(q for (u, _), q in flow.items() if u == "S") - 8.737
        ) * 1000.0
        lmc_km = (
            sum(
                segment["length_m"]
                for (u, v), segments in ctrl.sections.items()
                if re.fullmatch(r"M\(0,\d+\)", u) and re.fullmatch(r"M\(0,\d+\)", v)
                for segment in segments
            )
            / 1000.0
        )
        per_km = seepage_l_s / lmc_km
        assert (
            20.0 < per_km < 120.0
        ), f"{per_km:.1f} L/s/km outside aged-concrete field range"


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
        tail = next(
            g
            for g in json.loads(CANONICAL.read_text())["gates"]
            if re.sub(r"\s+", "", g) == "M(0,12)"
        )
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
        gaps = {
            edge: round(gap, 3) for edge, gap in ctrl.reaches_with_chainage_gaps.items()
        }
        assert gaps == {
            ("M(0,0)", "M(0,1)"): 170.0,  # flume, no cross-section
            ("M(0,1;1,3)", "M(0,1;1,4)"): 80.0,  # RMC tail
            ("M(0,12;1,1;1,1)", "M(0,12;1,1;1,2)"): 30.0,  # 2R-38R tail
            ("M(0,12;1,2;1,1)", "M(0,12;1,2;1,2)"): 1200.0,  # 4L-38R unsurveyed
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
        edge = next(e for e in ctrl.edges if normalize_edge(*e) == ("M(0,0)", "M(0,1)"))
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
        assert (
            surveyed == 42
        )  # 59 edges - 17 missing (matches the /plan loss-coverage test)

    def test_coverage_summary_counts_geometry_and_calibration_method(self):
        summary = self._ctrl().coverage_summary()
        assert summary == {
            "total_reaches": 59,
            "geometry_surveyed": 42,
            "geometry_missing": 17,
            "chainage_gaps": 5,
            "calibration_method_counts": {"measured": 10, "inferred": 49},
        }


class TestOpeningsForDemand:
    # Wave 2.7 /control WIRING: demand -> per-reach flow -> per-gate openings. A reach is
    # commanded only when its levels are fresh, its capacity is fully surveyed, the bundle
    # is actuation-approved, AND the whole plan is commandable; otherwise it is opening-
    # unavailable (plan HIGH #11: never an assumed command). Approval is a property of the
    # loaded bundle (an instance attribute), not a caller argument — tests set it to
    # exercise the produce path that no real (planning_only) bundle can reach.
    def _ctrl(self):
        return NetworkFlowController(str(CANONICAL), geometry_path=str(GEOMETRY_CFG))

    @staticmethod
    def _approve(monkeypatch):
        # actuation_approved is a READ-ONLY property (no production mutation point); patch
        # the class to exercise the actuation branch no planning-only bundle can reach.
        monkeypatch.setattr(
            NetworkFlowController, "actuation_approved", property(lambda self: True)
        )

    def _readings(self, **levels):
        from core.network_flow_controller import LevelReading

        return {node: LevelReading(level, NOW) for node, level in levels.items()}

    def _all_fresh(self, ctrl, level=2.0):
        from core.network_flow_controller import LevelReading
        from core.network_topology import nodes_of

        return {node: LevelReading(level, NOW) for node in nodes_of(ctrl.edges)}

    # ---- _reach_targets: the pure level/capacity split (no approval, no all-or-nothing) ----
    def test_reach_targets_splits_commandable_from_capacity_unavailable(self):
        from core.network_flow_controller import REASON_CAPACITY_UNSURVEYED

        ctrl = self._ctrl()
        reach_flow = ctrl.required_flow_per_reach({"M(0,1)": 5.0})
        levels = ctrl._resolve_levels(
            self._readings(S=3.0, **{"M(0,0)": 2.5, "M(0,1)": 2.0}), NOW, 3600
        )
        targets, unavailable, idle = ctrl._reach_targets(reach_flow, levels)
        assert {t.reach for t in targets} == {
            ("S", "M(0,0)")
        }  # no geometry -> gate-bounded
        assert (
            next(t for t in targets if t.reach == ("S", "M(0,0)")).capacity_m3s is None
        )
        assert {u.reach: u.reason for u in unavailable} == {
            (
                "M(0,0)",
                "M(0,1)",
            ): REASON_CAPACITY_UNSURVEYED  # partial survey (170 m gap)
        }
        assert idle == 57

    def test_capacity_uses_the_normalized_segment_bound_not_raw_edge(self):
        # Bug guard: self.sections is keyed by NORMALIZED edges; the fully-surveyed reach
        # M(0,1;1,0)->M(0,1;1,1) carries survey spacing, so a raw-edge lookup would drop
        # its 1.235 m3/s canal limit and fall back to the gate's 1.375 rated q_max.
        from core.conveyance_loss import normalize_edge

        ctrl = self._ctrl()
        target = next(
            e for e in ctrl.edges if normalize_edge(*e) == ("M(0,1;1,0)", "M(0,1;1,1)")
        )
        assert ctrl._reach_capacity[target] == pytest.approx(
            1.235, abs=1e-2
        )  # precompute
        reach_flow = ctrl.required_flow_per_reach({"M(0,1;1,1)": 5.0})
        levels = ctrl._resolve_levels(self._all_fresh(ctrl), NOW, 3600)
        targets, _, _ = ctrl._reach_targets(reach_flow, levels)
        built = next(t for t in targets if t.reach == target)
        assert built.capacity_m3s == pytest.approx(
            1.235, abs=1e-2
        )  # flows into the target

    def test_surveyed_reach_without_a_valid_rating_is_capacity_unavailable(
        self, tmp_path
    ):
        # A reach that IS surveyed (in self.sections, no chainage gap) but whose segments
        # carry NO valid q_max -> min_segment_q_max() None -> must be flagged capacity-
        # uncertain (fail closed), never left gate-bounded (fail open). Synthetic geometry
        # (one section, no design discharge) exercises the branch real data doesn't yet hit.
        net = {
            "metadata": {"canonical": True, "total_gates": 2, "total_connections": 2},
            "gates": {"M(0,0)": {}, "M(0,1)": {}},
            "edges": [["S", "M(0,0)"], ["M(0,0)", "M(0,1)"]],
        }
        geo = {
            "metadata": {"source": "unit fixture"},
            "canal_sections": [
                {
                    "from_node": "M(0,0)",
                    "to_node": "M(0,1)",
                    "geometry": {
                        "length_m": 1000.0,
                        "cross_section": {
                            "type": "trapezoidal",
                            "depth_m": 2.5,
                            "bottom_width_m": 4.0,
                            "side_slope": 1.5,
                        },
                        "hydraulic_params": {"lining_type": "concrete"},
                    },
                }
            ],
            "summary": {"total_sections": 1},
        }
        net_f = tmp_path / "net.json"
        net_f.write_text(json.dumps(net))
        geo_f = tmp_path / "geo.json"
        geo_f.write_text(json.dumps(geo))
        ctrl = NetworkFlowController(str(net_f), geometry_path=str(geo_f))
        edge = ("M(0,0)", "M(0,1)")
        assert edge in ctrl.sections and edge not in ctrl.reaches_with_chainage_gaps
        assert ctrl._reach_capacity[edge] is None
        assert edge in ctrl._reach_capacity_uncertain

    def test_missing_downstream_level_makes_that_reach_unavailable(self):
        from core.network_flow_controller import REASON_LEVEL_MISSING

        ctrl = self._ctrl()
        reach_flow = ctrl.required_flow_per_reach({"M(0,1)": 5.0})
        levels = ctrl._resolve_levels(
            self._readings(S=3.0, **{"M(0,0)": 2.5}), NOW, 3600
        )
        _, unavailable, _ = ctrl._reach_targets(reach_flow, levels)
        reasons = {u.reach: u for u in unavailable}
        assert reasons[("M(0,0)", "M(0,1)")].reason == REASON_LEVEL_MISSING
        assert "M(0,1)" in reasons[("M(0,0)", "M(0,1)")].unavailable_nodes

    # ---- _classify_level: freshness / validity of a single reading ----
    def test_classify_level_freshness_and_validity(self):
        from datetime import datetime as _dt
        from core.network_flow_controller import (
            LevelReading,
            REASON_LEVEL_FUTURE,
            REASON_LEVEL_INVALID,
            REASON_LEVEL_STALE,
        )

        classify = NetworkFlowController._classify_level
        assert classify(LevelReading(2.0, NOW), NOW, 3600) == (2.0, None)
        # Exact-SLA boundary is fresh; one second older is stale.
        assert classify(
            LevelReading(2.0, NOW - timedelta(seconds=3600)), NOW, 3600
        ) == (2.0, None)
        assert classify(
            LevelReading(2.0, NOW - timedelta(seconds=3601)), NOW, 3600
        ) == (
            None,
            REASON_LEVEL_STALE,
        )
        # Any future stamp (even 1 s) is not a current measurement.
        assert classify(LevelReading(2.0, NOW + timedelta(seconds=1)), NOW, 3600) == (
            None,
            REASON_LEVEL_FUTURE,
        )
        # Naive timestamp and non-finite level are malformed -> per-reach invalid (no raise).
        assert classify(LevelReading(2.0, _dt(2026, 7, 13, 12, 0, 0)), NOW, 3600) == (
            None,
            REASON_LEVEL_INVALID,
        )
        assert classify(LevelReading(float("nan"), NOW), NOW, 3600) == (
            None,
            REASON_LEVEL_INVALID,
        )

    def test_one_bad_reading_does_not_abort_the_whole_request(self):
        from datetime import datetime as _dt
        from core.network_flow_controller import LevelReading, REASON_LEVEL_INVALID
        from core.node_id import normalize_node_id

        ctrl = self._ctrl()
        node_levels = {
            "S": LevelReading(3.0, NOW),
            "M(0,0)": LevelReading(2.5, _dt(2026, 7, 13, 12, 0, 0)),  # naive: bad datum
            "M(0,1)": LevelReading(2.0, NOW),
        }
        levels = ctrl._resolve_levels(node_levels, NOW, 3600)  # must NOT raise
        assert levels[normalize_node_id("M(0,0)")] == (None, REASON_LEVEL_INVALID)
        assert levels[normalize_node_id("M(0,1)")] == (2.0, None)  # unaffected

    # ---- openings_for_demand: approval + all-or-nothing orchestration ----
    def test_planning_only_bundle_commands_nothing(self):
        from core.network_flow_controller import (
            REASON_CAPACITY_UNSURVEYED,
            REASON_NOT_ACTUATION_APPROVED,
        )

        ctrl = self._ctrl()
        assert ctrl.actuation_approved is False
        result = ctrl.openings_for_demand(
            {"M(0,1)": 5.0},
            self._readings(S=3.0, **{"M(0,0)": 2.5, "M(0,1)": 2.0}),
            now=NOW,
            max_level_age_seconds=3600,
        )
        assert result.openings == []  # nothing commanded on planning-only calibration
        reasons = {u.reach: u.reason for u in result.unavailable}
        assert (
            reasons[("S", "M(0,0)")] == REASON_NOT_ACTUATION_APPROVED
        )  # commandable, blocked
        assert reasons[("M(0,0)", "M(0,1)")] == REASON_CAPACITY_UNSURVEYED

    def test_all_or_nothing_blocks_a_partially_commandable_plan(self, monkeypatch):
        from core.network_flow_controller import (
            REASON_CAPACITY_UNSURVEYED,
            REASON_PLAN_INCOMPLETE,
        )

        self._approve(monkeypatch)
        ctrl = self._ctrl()
        result = ctrl.openings_for_demand(
            {"M(0,1)": 5.0},
            self._readings(S=3.0, **{"M(0,0)": 2.5, "M(0,1)": 2.0}),
            now=NOW,
            max_level_age_seconds=3600,
        )
        # S->M(0,0) is commandable, but its peer M(0,0)->M(0,1) is capacity-unavailable, so
        # partial actuation is refused: NOTHING is commanded.
        assert result.openings == []
        reasons = {u.reach: u.reason for u in result.unavailable}
        assert reasons[("S", "M(0,0)")] == REASON_PLAN_INCOMPLETE
        assert reasons[("M(0,0)", "M(0,1)")] == REASON_CAPACITY_UNSURVEYED

    def test_fully_commandable_plan_matches_an_independent_branch_split(
        self, monkeypatch
    ):
        from core.branch_split import ReachTarget, branch_split_openings
        from core.network_flow_controller import LevelReading

        self._approve(monkeypatch)
        ctrl = self._ctrl()
        # Demand at the head gate M(0,0) activates ONLY S->M(0,0) (no geometry -> gate-
        # bounded), so the whole plan is commandable. A decreasing profile gives a driving
        # head so the single reach solves feasibly. Oracle: branch_split on the hand-
        # assembled target with the loader's calibration.
        levels = {
            "S": LevelReading(206.0, NOW),
            "M(0,0)": LevelReading(205.5, NOW),
        }
        result = ctrl.openings_for_demand(
            {"M(0,0)": 5.0}, levels, now=NOW, max_level_age_seconds=3600
        )
        assert {o.reach for o in result.openings} == {("S", "M(0,0)")}
        assert result.unavailable == []
        expected = branch_split_openings(
            [
                ReachTarget(
                    reach=("S", "M(0,0)"),
                    calibration=ctrl._calibration.build_flow_calibration("M(0,0)"),
                    upstream_level_m=206.0,
                    downstream_level_m=205.5,
                    target_flow_m3s=5.0,
                    capacity_m3s=None,
                )
            ]
        )
        assert result.openings == expected

    def test_post_solve_infeasibility_blocks_the_whole_plan(self, monkeypatch):
        # A reach that passes the level+capacity pre-check can still solve INFEASIBLE inside
        # branch_split (here: flat levels -> no driving head). That is the same partial-
        # actuation hazard discovered at solve time, so the whole plan must be blocked, not
        # emitted. (S->M(0,0) is the single commandable reach for a head-gate demand.)
        from core.network_flow_controller import LevelReading, REASON_PLAN_INCOMPLETE

        self._approve(monkeypatch)
        ctrl = self._ctrl()
        flat = {
            "S": LevelReading(2.0, NOW),
            "M(0,0)": LevelReading(2.0, NOW),
        }  # no head
        result = ctrl.openings_for_demand(
            {"M(0,0)": 5.0}, flat, now=NOW, max_level_age_seconds=3600
        )
        assert result.openings == []  # nothing commanded when a reach solves infeasible
        assert {u.reach: u.reason for u in result.unavailable} == {
            ("S", "M(0,0)"): REASON_PLAN_INCOMPLETE
        }

    def test_idle_reaches_need_no_levels_and_are_only_counted(self):
        result = self._ctrl().openings_for_demand(
            {}, {}, now=NOW, max_level_age_seconds=3600
        )
        assert result.openings == []
        assert result.unavailable == []
        assert result.idle_reaches == 59

    def test_naive_now_is_rejected(self):
        with pytest.raises(ValueError):
            self._ctrl().openings_for_demand(
                {}, {}, now=datetime(2026, 7, 13, 12, 0, 0), max_level_age_seconds=3600
            )

    def test_nonpositive_and_nonfinite_max_age_are_rejected(self):
        ctrl = self._ctrl()
        for bad in (0, -1.0, float("nan"), float("inf")):
            with pytest.raises(ValueError, match="max_level_age_seconds"):
                ctrl.openings_for_demand({}, {}, now=NOW, max_level_age_seconds=bad)

    def test_unknown_demand_node_still_fails_closed(self):
        with pytest.raises(ValueError):
            self._ctrl().openings_for_demand(
                {"Zone9": 5.0}, {}, now=NOW, max_level_age_seconds=3600
            )

    def test_level_for_unknown_node_fails_closed(self):
        from core.network_flow_controller import LevelReading

        with pytest.raises(ValueError, match="unknown node"):
            self._ctrl().openings_for_demand(
                {"M(0,1)": 5.0},
                {"M(9,9)": LevelReading(2.0, NOW)},
                now=NOW,
                max_level_age_seconds=3600,
            )

    def test_actuation_approved_is_false_and_cannot_be_switched_on(self):
        # actuation_approved is hard-coded False (no loadable bundle is actuation-grade) and
        # has NO runtime input a caller could flip — not the property itself, and not the
        # underlying calibration policy. Both bypass attempts must fail (Codex CRITICAL x2).
        ctrl = self._ctrl()
        assert ctrl.actuation_approved is False
        with pytest.raises(AttributeError):
            ctrl.actuation_approved = True
        ctrl._calibration.intended_use = "actuation"  # mutating the bundle marker...
        assert ctrl.actuation_approved is False  # ...still does not enable actuation
        result = ctrl.openings_for_demand(
            {"M(0,0)": 5.0},
            self._readings(S=3.0, **{"M(0,0)": 2.5}),
            now=NOW,
            max_level_age_seconds=3600,
        )
        assert result.openings == []  # no command path, even after the nested mutation
