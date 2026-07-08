"""
core.network_topology — canonical network loading + connectivity guard (F-11).

The wired topology (`munbon_network_final.json`) was ~76% wrong: most nodes were
unreachable from the source. The canonical, validated topology is
`src/config/network.json` (adopted from `munbon_network_updated.json`: a proper
spanning tree, 60 nodes = 59 gates + source `S`, 59 edges, every node reachable).

This module is PURE (stdlib only). `assert_connected` is the loader guard: it fails
fast so hydraulics never run on a fragmented graph.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict, deque

ROOT = "S"


class NetworkTopologyError(ValueError):
    """Raised when a network graph is fragmented or structurally invalid."""


def load_edges(path: str) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "edges" not in data:
        raise NetworkTopologyError(f"{path}: network JSON has no 'edges' key")
    return [tuple(e) for e in data["edges"]]


def nodes_of(edges) -> set:
    nodes: set = set()
    for a, b in edges:
        nodes.add(a)
        nodes.add(b)
    return nodes


def reachable_from(edges, root: str = ROOT) -> set:
    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
    seen = {root}
    queue = deque([root])
    while queue:
        node = queue.popleft()
        for nxt in adj[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def is_spanning_tree(edges, root: str = ROOT) -> bool:
    """True iff `edges` form a tree rooted at `root` spanning every node."""
    nodes = nodes_of(edges)
    if len(edges) != len(nodes) - 1:
        return False
    parent_count = defaultdict(int)
    for _, child in edges:
        parent_count[child] += 1
    if any(count > 1 for count in parent_count.values()):
        return False
    return reachable_from(edges, root) == nodes


def assert_connected(edges, root: str = ROOT) -> None:
    """Loader guard (F-11): raise unless every node is reachable from `root`.

    Fail fast — hydraulics must never run on a fragmented graph.
    """
    if not edges:
        raise NetworkTopologyError("network has no edges")
    nodes = nodes_of(edges)
    if root not in nodes:
        raise NetworkTopologyError(f"root {root!r} is not present in the network")
    reached = reachable_from(edges, root)
    if reached != nodes:
        missing = sorted(nodes - reached)
        raise NetworkTopologyError(
            f"network is fragmented: {len(missing)} of {len(nodes)} nodes are unreachable "
            f"from {root!r}: {missing[:8]}{'...' if len(missing) > 8 else ''}"
        )


def load_validated_network(path: str, root: str = ROOT) -> list[tuple[str, str]]:
    """Load edges from a network JSON file and guard connectivity; returns the edges."""
    edges = load_edges(path)
    assert_connected(edges, root)
    return edges


def children_of(edges) -> dict:
    """Adjacency map parent -> list of children, preserving edge order."""
    adj: dict = defaultdict(list)
    for parent, child in edges:
        adj[parent].append(child)
    return dict(adj)


def topological_order(edges) -> list:
    """Nodes ordered so every parent precedes its children (Kahn's algorithm).

    Raises `NetworkTopologyError` if the graph contains a cycle (no valid order).
    """
    adj = children_of(edges)
    nodes = nodes_of(edges)
    indegree = {n: 0 for n in nodes}
    for _, child in edges:
        indegree[child] += 1
    queue = deque(sorted(n for n in nodes if indegree[n] == 0))
    order: list = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in adj.get(node, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(nodes):
        raise NetworkTopologyError("graph contains a cycle; no topological order exists")
    return order


def _parse_gate_id(gate_id: str) -> list[tuple[int, int]]:
    """Parse ``M(0,1; 1,0)`` (any spacing) into ``[(0, 1), (1, 0)]``."""
    s = re.sub(r"\s+", "", gate_id)
    if not (s.startswith("M(") and s.endswith(")")):
        raise NetworkTopologyError(f"malformed gate id {gate_id!r}")
    pairs = []
    for pair in s[2:-1].split(";"):
        parts = pair.split(",")
        if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
            raise NetworkTopologyError(f"malformed gate id {gate_id!r}")
        pairs.append((int(parts[0]), int(parts[1])))
    return pairs


def _fmt_tuples(tuples) -> str:
    return "M(" + ";".join(f"{b},{p}" for b, p in tuples) + ")"


def _normalize_gate_id(gate_id: str) -> str:
    """Canonical, space-free form of a gate id, e.g. ``M(0,1;1,0)`` (for matching)."""
    return _fmt_tuples(_parse_gate_id(gate_id))


def _derived_parent(gate_id: str):
    """Normalized parent id per the naming grammar, or None for the root head ``M(0,0)``."""
    tuples = _parse_gate_id(gate_id)
    branch, pos = tuples[-1]
    if pos > 0:
        return _fmt_tuples(tuples[:-1] + [(branch, pos - 1)])  # serial predecessor
    if len(tuples) == 1:
        return None  # single tuple (x, 0) -> source root
    return _fmt_tuples(tuples[:-1])  # junction: drop the last tuple


def edges_from_names(gate_ids, root: str = ROOT) -> list[tuple[str, str]]:
    """Derive the serial-chain topology purely from the gate-id naming grammar (F-11b).

    Each id ``M(i,j; ...; a,p)`` encodes the path from the source to that valve. The
    parent is: the serial predecessor ``(a, p-1)`` when ``p > 0``; the valve on the parent
    canal (drop the last tuple) when ``p == 0``; the ``root`` for the single-tuple head
    ``M(0,0)``. Emits the EXACT input id strings (irregular spacing preserved) so the edges
    stay consistent with the gates dict. Raises ``NetworkTopologyError`` on a derived parent
    that is not among ``gate_ids`` or on two ids that normalize to the same node.
    """
    exact: dict = {}
    for gate_id in gate_ids:
        key = _normalize_gate_id(gate_id)
        if key in exact:
            raise NetworkTopologyError(
                f"gate ids collide when normalized: {exact[key]!r} and {gate_id!r}"
            )
        exact[key] = gate_id
    edges = []
    for gate_id in gate_ids:
        parent = _derived_parent(gate_id)
        if parent is None:
            edges.append((root, gate_id))
        elif parent in exact:
            edges.append((exact[parent], gate_id))
        else:
            raise NetworkTopologyError(
                f"gate {gate_id!r}: derived parent {parent!r} is not among the gates"
            )
    return edges
