"""
Unit tests for core.conveyance_loss — Tier-1 seepage + operational loss model (B5).
Pure/stdlib; run in isolation:
    pytest --noconftest tests/unit/test_conveyance_loss.py

Oracles are hand-computed from raw formulas (not from the functions under test):
    wetted_perimeter P = b + 2*y*sqrt(1 + m^2)     [trapezoid, y = operating depth]
    seepage          = rate * P * length_m
    uplift           = seepage + op_frac * throughflow
"""
import json
import math
from pathlib import Path

import pytest

from core.conveyance_loss import (
    SEEPAGE_RATE_BY_LINING,
    make_reach_loss,
    reach_loss_uplift,
    reach_seepage_m3s,
    sections_by_edge_from_geometry,
    seepage_rate_for_lining,
    wetted_perimeter,
)
from core.demand_aggregation import required_flow_per_reach

GEOMETRY_CFG = Path(__file__).resolve().parents[2] / "src" / "config" / "canal_geometry.json"

# A synthetic trapezoidal reach used across several tests (all values explained).
CS = {"bottom_width_m": 10.0, "depth_m": 2.0, "side_slope": 1.5}
Y = 0.7 * CS["depth_m"]  # operating depth = 0.7 * design depth = 1.4 m
P = CS["bottom_width_m"] + 2 * Y * math.sqrt(1 + CS["side_slope"] ** 2)  # ~15.0478 m


def _section(rate, length=1000.0, op=0.05, cs=CS):
    return {"length_m": length, "cross_section": cs, "seepage_rate_m_s": rate,
            "operational_loss_frac": op}


class TestSeepageRateForLining:
    def test_known_linings(self):
        assert seepage_rate_for_lining("concrete") == 3.0e-7
        assert seepage_rate_for_lining("earth") == 1.5e-6

    def test_unknown_and_missing_default_to_unknown_rate(self):
        assert seepage_rate_for_lining("steel") == SEEPAGE_RATE_BY_LINING["unknown"]
        assert seepage_rate_for_lining(None) == SEEPAGE_RATE_BY_LINING["unknown"]

    def test_earth_leaks_more_than_concrete(self):
        assert seepage_rate_for_lining("earth") > seepage_rate_for_lining("concrete")


class TestWettedPerimeter:
    def test_trapezoid_matches_hand_computed(self):
        assert wetted_perimeter(CS, Y) == pytest.approx(15.047771, abs=1e-5)

    def test_rectangular_channel_has_no_slope_term(self):
        # side_slope 0 -> P = bottom width + 2*depth (vertical walls).
        assert wetted_perimeter({"bottom_width_m": 8.0, "side_slope": 0.0}, 2.0) == pytest.approx(12.0)


class TestReachSeepage:
    def test_matches_rate_times_perimeter_times_length(self):
        expected = 3.0e-7 * P * 1000.0  # ~0.0045143 m3/s
        assert reach_seepage_m3s(_section(3.0e-7)) == pytest.approx(expected, rel=1e-9)

    def test_earth_reach_seeps_more_than_concrete_same_geometry(self):
        assert reach_seepage_m3s(_section(1.5e-6)) > reach_seepage_m3s(_section(3.0e-7))

    def test_scales_linearly_with_length(self):
        assert reach_seepage_m3s(_section(3.0e-7, length=2000)) == pytest.approx(
            2 * reach_seepage_m3s(_section(3.0e-7, length=1000)), rel=1e-9
        )


class TestReachLossUplift:
    def test_is_seepage_plus_operational_fraction_of_throughflow(self):
        section = _section(3.0e-7, op=0.05)
        seep = 3.0e-7 * P * 1000.0
        assert reach_loss_uplift(section, 8.0) == pytest.approx(seep + 0.05 * 8.0, rel=1e-9)

    def test_operational_term_scales_with_throughflow(self):
        section = _section(3.0e-7, op=0.05)
        assert reach_loss_uplift(section, 20.0) - reach_loss_uplift(section, 10.0) == pytest.approx(
            0.05 * 10.0, rel=1e-9
        )

    def test_zero_operational_fraction_leaves_seepage_only(self):
        assert reach_loss_uplift(_section(3.0e-7, op=0.0), 8.0) == pytest.approx(
            reach_seepage_m3s(_section(3.0e-7)), rel=1e-9
        )


class TestSectionsByEdgeFromGeometry:
    def test_parses_all_survey_sections_keyed_by_normalized_edge(self):
        geo = json.loads(GEOMETRY_CFG.read_text())
        sections = sections_by_edge_from_geometry(geo)
        assert len(sections) == 37
        # First LMC reach runs M(0,0) -> M(0,1), concrete lining, 300 m (serial chain).
        s = sections[("M(0,0)", "M(0,1)")]
        assert s["length_m"] == 300
        assert s["seepage_rate_m_s"] == 3.0e-7  # enriched from lining_type=concrete
        assert "cross_section" in s


class TestMakeReachLoss:
    def _sections(self):
        return {("M(0,0)", "M(0,1)"): _section(3.0e-7)}

    def test_covered_edge_returns_uplift(self):
        loss = make_reach_loss(self._sections())
        assert loss("M(0,0)", "M(0,1)", 8.0) == pytest.approx(
            reach_loss_uplift(_section(3.0e-7), 8.0), rel=1e-9
        )

    def test_matches_by_normalized_id_despite_spacing(self):
        loss = make_reach_loss(self._sections())
        assert loss("M(0,0)", "M (0,1)", 8.0) > 0  # spaced id still joins

    def test_uncovered_edge_returns_zero(self):
        loss = make_reach_loss(self._sections())
        assert loss("M(0,1)", "M(0,2)", 8.0) == 0.0

    def test_source_edge_returns_zero(self):
        # "S" is not a gate id and no reach has geometry -> no loss, no crash.
        assert make_reach_loss(self._sections())("S", "M(0,0)", 8.0) == 0.0


class TestAggregationWithLoss:
    # Serial chain S -> M(0,0) -> M(0,1) -> M(0,2); geometry on both M-reaches.
    EDGES = [("S", "M(0,0)"), ("M(0,0)", "M(0,1)"), ("M(0,1)", "M(0,2)")]

    def test_seepage_only_head_equals_demand_plus_path_seepage(self):
        # operational_loss_frac = 0 -> seepage is constant per reach, no compounding:
        # head = demand + seepage(M(0,0)->M(0,1)) + seepage(M(0,1)->M(0,2)).
        sections = {
            ("M(0,0)", "M(0,1)"): _section(3.0e-7, op=0.0),
            ("M(0,1)", "M(0,2)"): _section(3.0e-7, op=0.0),
        }
        flow = required_flow_per_reach(self.EDGES, {"M(0,2)": 10.0},
                                       reach_loss=make_reach_loss(sections))
        seep = 3.0e-7 * P * 1000.0
        assert flow[("S", "M(0,0)")] == pytest.approx(10.0 + 2 * seep, rel=1e-9)

    def test_losses_lift_head_above_the_lossless_head(self):
        sections = {("M(0,0)", "M(0,1)"): _section(3.0e-7), ("M(0,1)", "M(0,2)"): _section(3.0e-7)}
        demand = {"M(0,2)": 10.0}
        lossy = required_flow_per_reach(self.EDGES, demand, reach_loss=make_reach_loss(sections))
        lossless = required_flow_per_reach(self.EDGES, demand)
        assert lossy[("S", "M(0,0)")] > lossless[("S", "M(0,0)")]
