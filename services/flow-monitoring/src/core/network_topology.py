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
