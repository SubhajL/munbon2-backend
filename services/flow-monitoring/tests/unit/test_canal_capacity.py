"""
Unit tests for core.canal_capacity — real per-reach capacity from the canonical
network (F-04), replacing the hardcoded 15.0; Wave 2.1a adds the canal-segment
q_max bound (WAVE_2-4_PLAN §1.5 amendment #2: reach capacity = min of the
downstream gate rating and the weakest surveyed segment). Pure/stdlib:
    pytest --noconftest tests/unit/test_canal_capacity.py
"""
import json
from pathlib import Path

from core.canal_capacity import (
    build_capacity_index,
    downstream_node,
    min_segment_q_max,
    reach_capacity,
)

CANONICAL = Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"

# canal_id is "C_{upstream}_{downstream}" (see hydraulic_service._aggregate_canal_flows).
NET = {
    "gates": {
        "M(0,2)": {"q_max": 8.737},
        "M(0,3)": {"q_max": 5.0},
        "X": {},  # no q_max -> excluded from the index
    }
}


class TestDownstreamNode:
    def test_parses_downstream_gate_from_reach_id(self):
        assert downstream_node("C_M(0,2)_M(0,3)") == "M(0,3)"

    def test_parses_source_reach(self):
        assert downstream_node("C_S_M(0,0)") == "M(0,0)"

    def test_returns_none_for_non_reach_id(self):
        assert downstream_node("not-a-reach") is None


class TestCapacityIndex:
    def test_index_keeps_only_gates_with_qmax(self):
        assert build_capacity_index(NET) == {"M(0,2)": 8.737, "M(0,3)": 5.0}

    def test_index_excludes_nan_inf_and_nonpositive(self):
        # Real network data has gates with q_max = NaN (e.g. M(0,1)); a NaN capacity would
        # make every over-capacity comparison silently false, so it must be excluded.
        net = {
            "gates": {
                "A": {"q_max": float("nan")},
                "B": {"q_max": float("inf")},
                "C": {"q_max": 0},
                "D": {"q_max": -3.0},
                "E": {"q_max": 5.0},
            }
        }
        assert build_capacity_index(net) == {"E": 5.0}

    def test_nan_capacity_reach_falls_back_and_is_flagged(self):
        net = json.loads(CANONICAL.read_text())
        idx = build_capacity_index(net)
        # M(0,1) has q_max=NaN in the canonical network -> excluded -> reach flagged as default.
        cap, from_data = reach_capacity(idx, "C_M(0,0)_M(0,1)", default=15.0)
        assert from_data is False
        assert cap == 15.0


class TestReachCapacity:
    def test_reach_capacity_is_downstream_gate_qmax(self):
        idx = build_capacity_index(NET)
        cap, from_data = reach_capacity(idx, "C_M(0,2)_M(0,3)", default=15.0)
        assert (cap, from_data) == (5.0, True)

    def test_unknown_reach_falls_back_and_is_flagged(self):
        idx = build_capacity_index(NET)
        cap, from_data = reach_capacity(idx, "C_A_UNKNOWN", default=15.0)
        assert cap == 15.0
        assert from_data is False


class TestMinSegmentQMax:
    def test_minimum_of_valid_segment_ratings(self):
        segments = [{"q_max": 6.5}, {"q_max": 3.2}, {"q_max": 8.0}]
        assert min_segment_q_max(segments) == 3.2

    def test_unrated_segments_are_ignored(self):
        assert min_segment_q_max([{"q_max": None}, {"q_max": 4.0}]) == 4.0

    def test_all_unrated_is_none(self):
        assert min_segment_q_max([{"q_max": None}, {}]) is None
        assert min_segment_q_max([]) is None

    def test_invalid_ratings_are_ignored(self):
        segments = [
            {"q_max": float("nan")},
            {"q_max": -1.0},
            {"q_max": 0},
            {"q_max": True},
            {"q_max": 2.5},
        ]
        assert min_segment_q_max(segments) == 2.5


class TestReachCapacityWithSegments:
    # Segment lists are keyed by NORMALIZED (upstream, downstream), as produced by
    # conveyance_loss.sections_by_edge_from_geometry.
    IDX = {"M(0,3)": 5.0}

    def test_weakest_segment_bounds_below_the_gate_rating(self):
        sections = {("M(0,2)", "M(0,3)"): [{"q_max": 6.0}, {"q_max": 3.0}]}
        cap, from_data = reach_capacity(
            self.IDX, "C_M(0,2)_M(0,3)", default=15.0, sections_by_edge=sections
        )
        assert (cap, from_data) == (3.0, True)

    def test_gate_rating_bounds_below_stronger_segments(self):
        sections = {("M(0,2)", "M(0,3)"): [{"q_max": 9.0}]}
        cap, from_data = reach_capacity(
            self.IDX, "C_M(0,2)_M(0,3)", default=15.0, sections_by_edge=sections
        )
        assert (cap, from_data) == (5.0, True)

    def test_segments_alone_provide_capacity_when_gate_is_unrated(self):
        sections = {("M(0,0)", "M(0,1)"): [{"q_max": 11.2}]}
        cap, from_data = reach_capacity(
            {}, "C_M(0,0)_M(0,1)", default=15.0, sections_by_edge=sections
        )
        assert (cap, from_data) == (11.2, True)

    def test_spaced_node_spellings_join_normalized_segment_keys(self):
        sections = {("M(0,3;1,0)", "M(0,3;1,1)"): [{"q_max": 2.0}]}
        cap, from_data = reach_capacity(
            {}, "C_M (0,3; 1,0)_M (0,3; 1,1)", default=15.0, sections_by_edge=sections
        )
        assert (cap, from_data) == (2.0, True)

    def test_neither_source_falls_back_flagged(self):
        cap, from_data = reach_capacity(
            {}, "C_M(0,2)_M(0,3)", default=15.0, sections_by_edge={}
        )
        assert (cap, from_data) == (15.0, False)


class TestAgainstCanonicalNetwork:
    def test_real_reach_uses_downstream_capacity_not_hardcoded_15(self):
        net = json.loads(CANONICAL.read_text())
        idx = build_capacity_index(net)
        # M(0,3) has a real q_max in the canonical network; the reach into it uses it.
        expected = net["gates"]["M(0,3)"]["q_max"]
        cap, from_data = reach_capacity(idx, "C_M(0,2)_M(0,3)", default=15.0)
        assert from_data is True
        assert cap == expected
        assert cap != 15.0  # no longer the hardcoded value
