"""
Unit tests for core.demand_aggregation — graph-descendants demand aggregation (A1–A3),
replacing the hardcoded 3-zone path table. Pure/stdlib; run in isolation:
    pytest --noconftest tests/unit/test_demand_aggregation.py

Reference tree rooted at S:  S -> A -> {B, C};  C -> D  (C is an INTERIOR delivery
node — it has its own demand AND a downstream child D, exercising the A4 rationale).
"""
import json
from pathlib import Path

import pytest

from core.network_topology import NetworkTopologyError, nodes_of, reachable_from
from core.demand_aggregation import required_flow_per_reach

TREE = [("S", "A"), ("A", "B"), ("A", "C"), ("C", "D")]
# demand on both leaves (B, D) and an interior node (C) and a mid node (A); none on root.
DEMAND = {"A": 1.0, "B": 2.0, "C": 0.5, "D": 3.0}
TOTAL = 6.5  # 1.0 + 2.0 + 0.5 + 3.0

CANONICAL = Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"


def _canonical_edges_and_gates():
    data = json.loads(CANONICAL.read_text())
    return [tuple(e) for e in data["edges"]], data["gates"]


class TestRequiredFlowPerReach:
    def test_returns_one_flow_per_edge(self):
        flow = required_flow_per_reach(TREE, DEMAND)
        assert set(flow) == set(TREE)

    def test_reach_carries_downstream_subtree_demand(self):
        # (A,C) proves the A4 case: interior node C's OWN 0.5 + child D's 3.0 = 3.5.
        flow = required_flow_per_reach(TREE, DEMAND)
        assert flow[("A", "B")] == pytest.approx(2.0)  # leaf: own demand only
        assert flow[("A", "C")] == pytest.approx(3.5)  # interior own 0.5 + D 3.0 (A4)
        assert flow[("C", "D")] == pytest.approx(3.0)
        assert flow[("S", "A")] == pytest.approx(TOTAL)

    def test_absent_node_contributes_zero(self):
        # only D demands water: B's reach is dry, and D's 3.0 flows up through A and S.
        flow = required_flow_per_reach(TREE, {"D": 3.0})
        assert flow[("A", "B")] == 0.0
        assert flow[("C", "D")] == pytest.approx(3.0)
        assert flow[("S", "A")] == pytest.approx(3.0)

    def test_empty_demand_yields_all_zero_reaches(self):
        flow = required_flow_per_reach(TREE, {})
        assert set(flow) == set(TREE)
        assert all(q == 0.0 for q in flow.values())

    def test_branch_split_upstream_equals_sum_of_branches_plus_own(self):
        # shared upstream reach carries A's own demand + both downstream branch subtrees.
        flow = required_flow_per_reach(TREE, DEMAND)
        assert flow[("S", "A")] == pytest.approx(
            DEMAND["A"] + flow[("A", "B")] + flow[("A", "C")]
        )

    def test_conservation_head_flow_equals_total_demand(self):
        # No loss: everything leaving the source equals the sum of all node demand.
        flow = required_flow_per_reach(TREE, DEMAND)
        head = sum(q for (u, _), q in flow.items() if u == "S")
        assert head == pytest.approx(TOTAL)

    def test_matches_independent_descendants_oracle(self):
        # Cross-check against an independent traversal: the sweep accumulates via
        # topological order + children; here we sum demand over the subtree computed by
        # reachable_from (BFS), which returns v together with all its descendants.
        flow = required_flow_per_reach(TREE, DEMAND)
        for (u, v), q in flow.items():
            expected = sum(DEMAND.get(n, 0.0) for n in reachable_from(TREE, v))
            assert q == pytest.approx(expected)


class TestReachLossSeam:
    def test_constant_loss_lifts_head_flow_by_loss_per_reach(self):
        # B5 seam: a constant loss c on each reach makes the head carry
        # total_demand + (#reaches * c) -- head > sum of demands (conveyance uplift).
        c = 0.1
        flow = required_flow_per_reach(TREE, DEMAND, reach_loss=lambda u, v, thru: c)
        head = sum(q for (u, _), q in flow.items() if u == "S")
        assert head == pytest.approx(TOTAL + len(TREE) * c)
        assert head > TOTAL

    def test_none_loss_is_lossless(self):
        assert required_flow_per_reach(
            TREE, DEMAND, reach_loss=None
        ) == required_flow_per_reach(TREE, DEMAND)


class TestValidation:
    def test_unknown_node_id_is_rejected(self):
        # synthetic ids like "Zone2" (audit A2) must fail closed, not silently zero out.
        with pytest.raises(ValueError):
            required_flow_per_reach(TREE, {"Zone2": 5.0})

    def test_negative_demand_is_rejected(self):
        with pytest.raises(ValueError):
            required_flow_per_reach(TREE, {"B": -1.0})

    def test_nan_demand_is_rejected(self):
        # nan < 0 is False, so nan must be caught explicitly or it yields nan flows.
        with pytest.raises(ValueError):
            required_flow_per_reach(TREE, {"B": float("nan")})

    def test_infinite_demand_is_rejected(self):
        with pytest.raises(ValueError):
            required_flow_per_reach(TREE, {"B": float("inf")})

    def test_non_numeric_demand_is_rejected_cleanly(self):
        # a string must fail closed with ValueError, not leak a raw TypeError from `< 0`/isfinite.
        with pytest.raises(ValueError):
            required_flow_per_reach(TREE, {"B": "abc"})

    def test_demand_on_source_root_is_rejected(self):
        # the source has no upstream reach to carry demand -> reject rather than lose it.
        with pytest.raises(ValueError):
            required_flow_per_reach(TREE, {"S": 1.0})

    def test_non_tree_topology_is_rejected(self):
        # diamond: connected but C has two parents -> not a spanning tree -> fail closed.
        diamond = [("S", "A"), ("S", "B"), ("A", "C"), ("B", "C")]
        with pytest.raises(NetworkTopologyError):
            required_flow_per_reach(diamond, {"C": 1.0})


class TestCanonicalNetwork:
    def test_every_gate_with_area_is_served_by_its_reach(self):
        # A1: give each irrigated gate a demand; its terminating reach must carry >= it,
        # and the head must carry the full sum (conservation on the real 58-gate tree).
        edges, gates = _canonical_edges_and_gates()
        demand = {
            g: float(m["area"])
            for g, m in gates.items()
            if isinstance(m.get("area"), (int, float)) and m["area"] > 0
        }
        assert len(demand) == 33  # sanity: matches the audited count of delivery nodes
        flow = required_flow_per_reach(edges, demand)

        parent = {v: u for u, v in edges}
        for gate, d in demand.items():
            assert flow[(parent[gate], gate)] >= d - 1e-9

        head = sum(q for (u, _), q in flow.items() if u == "S")
        assert head == pytest.approx(sum(demand.values()))

    def test_rejects_demand_for_a_non_network_node(self):
        edges, _ = _canonical_edges_and_gates()
        assert "Zone2" not in nodes_of(edges)
        with pytest.raises(ValueError):
            required_flow_per_reach(edges, {"Zone2": 10.0})

    def test_lateral_demand_flows_through_every_serial_reach(self):
        # F-11b regression guard: on the corrected serial-chain topology, demand at the tail
        # of the RMC must flow through EVERY reach from its head down to it.
        # On the old star topology the head reach would
        # carry 0 and the intra-lateral reaches would not exist -> this fails.
        import re

        edges, gates = _canonical_edges_and_gates()

        def norm(x):
            return re.sub(r"\s+", "", x)

        chain = sorted(
            (g for g in gates if re.fullmatch(r"M\(0,0;2,\d+\)", norm(g))),
            key=lambda g: int(re.fullmatch(r"M\(0,0;2,(\d+)\)", norm(g)).group(1)),
        )
        head = next(g for g in gates if norm(g) == "M(0,0)")
        assert len(chain) >= 3

        flow = required_flow_per_reach(
            edges, {chain[-1]: 5.0}
        )  # water only at the tail
        assert flow[(head, chain[0])] == pytest.approx(5.0)
        for upstream, downstream in zip(chain, chain[1:]):
            assert flow[(upstream, downstream)] == pytest.approx(5.0)
