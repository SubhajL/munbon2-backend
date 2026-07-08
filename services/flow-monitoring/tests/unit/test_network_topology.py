"""
Unit tests for core.network_topology — the canonical topology loader + connectivity
guard (F-11). Pure/stdlib; run in isolation:
    pytest --noconftest tests/unit/test_network_topology.py
"""
import json
from pathlib import Path

import pytest

from core.network_topology import (
    NetworkTopologyError,
    assert_connected,
    children_of,
    is_spanning_tree,
    load_validated_network,
    nodes_of,
    reachable_from,
    topological_order,
)

# A tiny valid tree rooted at S:  S -> A -> {B, C};  C -> D
GOOD = [("S", "A"), ("A", "B"), ("A", "C"), ("C", "D")]
# Same but the C->D edge is dropped, so D is orphaned (fragmented).
FRAGMENTED = [("S", "A"), ("A", "B"), ("A", "C"), ("X", "D")]

CANONICAL = Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"


class TestReachability:
    def test_nodes_of_collects_both_endpoints(self):
        assert nodes_of(GOOD) == {"S", "A", "B", "C", "D"}

    def test_reachable_from_root_covers_whole_tree(self):
        assert reachable_from(GOOD, "S") == {"S", "A", "B", "C", "D"}

    def test_reachable_stops_at_disconnected_component(self):
        # X and D are not reachable from S in the fragmented graph.
        assert reachable_from(FRAGMENTED, "S") == {"S", "A", "B", "C"}


class TestSpanningTree:
    def test_valid_tree_is_spanning_tree(self):
        assert is_spanning_tree(GOOD, "S") is True

    def test_multi_parent_is_not_tree(self):
        # |E| = |V|-1 (3 edges, 4 nodes) so the edge-count guard passes; B has two parents
        # (A and C) -> this actually exercises the multi-parent branch, not the count guard.
        multi_parent = [("S", "A"), ("A", "B"), ("C", "B")]
        assert is_spanning_tree(multi_parent, "S") is False


class TestAssertConnectedGuard:
    def test_accepts_fully_connected_tree(self):
        assert_connected(GOOD, "S")  # must not raise

    def test_rejects_fragmented_graph(self):
        with pytest.raises(NetworkTopologyError):
            assert_connected(FRAGMENTED, "S")

    def test_rejects_missing_root(self):
        with pytest.raises(NetworkTopologyError):
            assert_connected([("A", "B")], "S")

    def test_rejects_empty(self):
        with pytest.raises(NetworkTopologyError):
            assert_connected([], "S")


class TestCanonicalNetworkFile:
    def test_canonical_network_exists(self):
        assert CANONICAL.exists(), f"missing canonical network at {CANONICAL}"

    def test_canonical_is_connected_spanning_tree(self):
        edges = load_validated_network(str(CANONICAL))  # raises if fragmented
        nodes = nodes_of(edges)
        assert "S" in nodes
        assert len(edges) == 59
        assert len(nodes) == 60  # 59 gates + S
        assert is_spanning_tree(edges, "S")

    def test_every_gate_id_is_a_reachable_node(self):
        data = json.loads(CANONICAL.read_text())
        gate_ids = set(data["gates"].keys())
        reached = reachable_from([tuple(e) for e in data["edges"]], "S")
        assert gate_ids <= reached  # every gate is reachable from the source


class TestChildrenOf:
    def test_maps_each_parent_to_its_children(self):
        assert children_of(GOOD) == {"S": ["A"], "A": ["B", "C"], "C": ["D"]}

    def test_leaf_and_absent_nodes_have_no_children(self):
        adj = children_of(GOOD)
        assert adj.get("B", []) == []
        assert adj.get("D", []) == []


class TestTopologicalOrder:
    def test_every_parent_precedes_each_child(self):
        order = topological_order(GOOD)
        pos = {n: i for i, n in enumerate(order)}
        assert set(order) == {"S", "A", "B", "C", "D"}
        for parent, child in GOOD:
            assert pos[parent] < pos[child]

    def test_root_is_first(self):
        assert topological_order(GOOD)[0] == "S"

    def test_raises_on_cycle(self):
        cyclic = [("S", "A"), ("A", "B"), ("B", "A")]
        with pytest.raises(NetworkTopologyError):
            topological_order(cyclic)


def test_load_validated_network_rejects_malformed_file(tmp_path):
    # A structurally broken network file must raise NetworkTopologyError, not a raw KeyError.
    bad = tmp_path / "no_edges.json"
    bad.write_text('{"nodes": []}')
    with pytest.raises(NetworkTopologyError):
        load_validated_network(str(bad))
