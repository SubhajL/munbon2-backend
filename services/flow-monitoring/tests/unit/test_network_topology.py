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
    edges_from_names,
    is_spanning_tree,
    load_validated_network,
    nodes_of,
    reachable_from,
    topological_order,
)
from core.network_topology import _normalize_gate_id, _parse_gate_id

# A tiny valid tree rooted at S:  S -> A -> {B, C};  C -> D
GOOD = [("S", "A"), ("A", "B"), ("A", "C"), ("C", "D")]
# Same but the C->D edge is dropped, so D is orphaned (fragmented).
FRAGMENTED = [("S", "A"), ("A", "B"), ("A", "C"), ("X", "D")]

CANONICAL = Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"
GEOMETRY = (
    Path(__file__).resolve().parents[2] / "src" / "config" / "canal_geometry.json"
)


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
        assert len(edges) == 58
        assert len(nodes) == 59  # 58 gates + S
        assert is_spanning_tree(edges, "S")

    def test_every_gate_id_is_a_reachable_node(self):
        data = json.loads(CANONICAL.read_text())
        gate_ids = set(data["gates"].keys())
        reached = reachable_from([tuple(e) for e in data["edges"]], "S")
        assert gate_ids <= reached  # every gate is reachable from the source

    def test_canonical_network_is_strict_json(self):
        # Bare NaN/Infinity is a Python-only extension: jq / JS / strict parsers
        # reject it. Missing numeric fields must be null (Wave 0.5).
        def _reject(constant):
            raise AssertionError(
                f"non-strict JSON constant {constant!r} in network.json"
            )

        json.loads(CANONICAL.read_text(), parse_constant=_reject)


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


class TestParseAndNormalizeGateId:
    def test_parses_single_tuple(self):
        assert _parse_gate_id("M(0,0)") == [(0, 0)]

    def test_parses_multi_tuple_ignoring_spacing(self):
        # the canonical file uses irregular spacing; both must parse identically.
        assert _parse_gate_id("M (0,1; 1,0)") == [(0, 1), (1, 0)]
        assert _parse_gate_id("M(0,1;1,0)") == [(0, 1), (1, 0)]

    def test_normalize_collapses_spacing(self):
        assert _normalize_gate_id("M (0,1; 1,0)") == _normalize_gate_id("M(0,1;1,0)")
        assert " " not in _normalize_gate_id("M (0,1; 1,0)")

    def test_rejects_negative_index(self):
        # A negative branch/position is a malformed id -> fail closed, not a silent root.
        with pytest.raises(NetworkTopologyError):
            _parse_gate_id("M(0,-1)")


class TestEdgesFromNamesRules:
    # A self-contained lateral: LMC head + 2 serial LMC valves + a branch with 2 serial valves.
    VALID = ["M(0,0)", "M(0,1)", "M(0,2)", "M(0,1;1,0)", "M(0,1;1,1)"]

    def _map(self):
        return {c: p for p, c in edges_from_names(self.VALID)}

    def test_head_gate_attaches_to_source_root(self):
        assert self._map()["M(0,0)"] == "S"

    def test_serial_valve_parent_is_previous_on_same_canal(self):
        m = self._map()
        assert m["M(0,1)"] == "M(0,0)"
        assert m["M(0,2)"] == "M(0,1)"  # NOT M(0,0) -> this is the star bug being fixed
        assert m["M(0,1;1,1)"] == "M(0,1;1,0)"  # serial along the branch

    def test_branch_first_valve_attaches_to_parent_canal(self):
        assert self._map()["M(0,1;1,0)"] == "M(0,1)"  # junction: drop last tuple

    def test_result_is_a_spanning_tree(self):
        edges = edges_from_names(self.VALID)
        assert len(edges) == len(self.VALID)
        assert is_spanning_tree(edges, "S")

    def test_preserves_exact_input_strings_including_spacing(self):
        spaced = ["M(0,0)", "M(0,1)", "M (0,1; 1,0)", "M (0,1; 1,1)"]
        edges = edges_from_names(spaced)
        assert (
            "M (0,1; 1,0)",
            "M (0,1; 1,1)",
        ) in edges  # exact spaced strings, not reformatted

    def test_sparse_serial_number_uses_previous_existing_valve(self):
        assert edges_from_names(["M(0,0)", "M(0,2)"]) == [
            ("S", "M(0,0)"),
            ("M(0,0)", "M(0,2)"),
        ]

    def test_sparse_chain_without_position_zero_fails_closed(self):
        with pytest.raises(NetworkTopologyError, match="no earlier valve"):
            edges_from_names(["M(0,2)"])

    def test_rejects_ids_that_collide_when_normalized(self):
        with pytest.raises(NetworkTopologyError):
            edges_from_names(["M(0,1;1,0)", "M (0,1; 1,0)"])

    def test_rejects_non_head_single_tuple_attaching_to_root(self):
        # M(1,0) parses fine, but only M(0,0) may hang off the source: accepting it
        # creates a second root-attached chain that still passes is_spanning_tree.
        with pytest.raises(NetworkTopologyError, match=r"only M\(0,0\) may attach"):
            edges_from_names(["M(0,0)", "M(1,0)"])

    @pytest.mark.parametrize("lone_head", ["M(1,0)", "M(3,0)", "M (2, 0)", "M(10,0)"])
    def test_rejects_lone_non_head_single_tuple(self, lone_head):
        with pytest.raises(NetworkTopologyError, match=r"only M\(0,0\) may attach"):
            edges_from_names([lone_head])

    @pytest.mark.parametrize("alias", ["M(00,00)", "M(0,00)", "M(000,0)"])
    def test_rejects_leading_zero_aliases_of_the_root(self, alias):
        # These parse to (0,0) but are textual aliases: accepting them would attach
        # a non-canonical root spelling that exact-string consumers can't resolve.
        with pytest.raises(NetworkTopologyError, match="leading zero"):
            edges_from_names([alias])


class TestEdgesFromNamesRealNetwork:
    def _gate_ids(self):
        return list(json.loads(CANONICAL.read_text())["gates"].keys())

    def test_derives_a_full_spanning_tree_over_all_58_gates(self):
        edges = edges_from_names(self._gate_ids())
        assert len(edges) == 58
        assert is_spanning_tree(edges, "S")
        assert len(reachable_from(edges, "S")) == 59  # 58 gates + S

    def test_reproduces_the_surveyed_geometry_chain(self):
        # Generated SCADA V5 geometry lists the surveyed serial reaches; every one must
        # appear in the independently name-derived topology.
        import re

        def norm(x):
            return re.sub(r"\s+", "", x)

        survey = json.loads(GEOMETRY.read_text())["canal_sections"]
        derived = {(norm(u), norm(v)) for u, v in edges_from_names(self._gate_ids())}
        survey_edges = {(norm(s["from_node"]), norm(s["to_node"])) for s in survey}
        assert survey_edges <= derived, survey_edges - derived


class TestRegeneratedNetworkFileIsConsistent:
    def test_committed_edges_equal_names_derivation(self):
        # Locks the regeneration: network.json's edges must be exactly what the naming
        # grammar derives from its own gate keys (no hand-edited drift, no star relics).
        data = json.loads(CANONICAL.read_text())
        committed = [tuple(e) for e in data["edges"]]
        derived = edges_from_names(list(data["gates"].keys()))
        assert set(committed) == set(derived)


def test_load_validated_network_rejects_malformed_file(tmp_path):
    # A structurally broken network file must raise the strict loader's ConfigError
    # (Wave 1.1), not a raw KeyError.
    from core.config_loader import ConfigError

    bad = tmp_path / "no_edges.json"
    bad.write_text('{"nodes": []}')
    with pytest.raises(ConfigError):
        load_validated_network(str(bad))
