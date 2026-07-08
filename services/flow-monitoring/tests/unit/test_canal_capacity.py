"""
Unit tests for core.canal_capacity — real per-reach capacity from the canonical
network (F-04), replacing the hardcoded 15.0. Pure/stdlib:
    pytest --noconftest tests/unit/test_canal_capacity.py
"""
import json
from pathlib import Path

from core.canal_capacity import (
    build_capacity_index,
    downstream_node,
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
