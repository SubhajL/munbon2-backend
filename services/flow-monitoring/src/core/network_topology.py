"""
core.network_topology — canonical network loading + connectivity guard (F-11).

The wired topology (`munbon_network_final.json`) was ~76% wrong: most nodes were
unreachable from the source. The canonical, validated topology is
`src/config/network.json` (generated from the approved SCADA V5 workbook: a proper
spanning tree, 59 nodes = 58 gates + source `S`, 58 edges, every node reachable).

This module is PURE (stdlib only). `assert_connected` is the loader guard: it fails
fast so hydraulics never run on a fragmented graph.
"""
from __future__ import annotations

from collections import defaultdict, deque

from .config_loader import load_network_config
from .node_id import NodeIdError, format_gate_tuples, normalize_gate_id, parse_gate_id

ROOT = "S"


class NetworkTopologyError(ValueError):
    """Raised when a network graph is fragmented or structurally invalid."""


def load_edges(path: str) -> list[tuple[str, str]]:
    """Edges of a canonical network file, strictly loaded (Wave 1.1).

    Schema + metadata-drift validation lives in `core.config_loader` (ConfigError);
    graph structure (connectivity, spanning tree) is validated by the callers below.
    """
    return [tuple(e) for e in load_network_config(path)["edges"]]


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
    parent_count: defaultdict[str, int] = defaultdict(int)
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
        raise NetworkTopologyError(
            "graph contains a cycle; no topological order exists"
        )
    return order


def _parse_gate_id(gate_id: str) -> list[tuple[int, int]]:
    """Back-compat wrapper: the grammar lives in `core.node_id` (Wave 1.2); this module's
    consumers and tests expect grammar failures as NetworkTopologyError."""
    try:
        return parse_gate_id(gate_id)
    except NodeIdError as exc:
        raise NetworkTopologyError(str(exc)) from exc


_fmt_tuples = format_gate_tuples


def _normalize_gate_id(gate_id: str) -> str:
    """Back-compat wrapper around `core.node_id.normalize_gate_id` (NetworkTopologyError)."""
    try:
        return normalize_gate_id(gate_id)
    except NodeIdError as exc:
        raise NetworkTopologyError(str(exc)) from exc


def _derived_parent(gate_id: str, previous_serial: dict[str, str]):
    """Normalized parent id, or None for the root head ``M(0,0)``."""
    tuples = _parse_gate_id(gate_id)
    _, pos = tuples[-1]
    if pos > 0:
        normalized = _normalize_gate_id(gate_id)
        parent = previous_serial.get(normalized)
        if parent is None:
            raise NetworkTopologyError(
                f"gate {gate_id!r}: serial chain has no earlier valve"
            )
        return parent
    if len(tuples) == 1:
        # Only the head gate M(0,0) hangs off the source; any other single tuple
        # (e.g. M(1,0)) would silently start a second root-attached chain.
        if tuples[0] == (0, 0):
            return None
        raise NetworkTopologyError(
            f"gate {gate_id!r}: only M(0,0) may attach to the source root"
        )
    return _fmt_tuples(tuples[:-1])  # junction: drop the last tuple


def edges_from_names(gate_ids, root: str = ROOT) -> list[tuple[str, str]]:
    """Derive the serial-chain topology purely from the gate-id naming grammar (F-11b).

    Each id ``M(i,j; ...; a,p)`` encodes the path from the source to that valve. The
    parent is: the previous EXISTING serial valve when ``p > 0``; the valve on the
    parent canal (drop the last tuple) when ``p == 0``; the ``root`` for the
    single-tuple head ``M(0,0)``. Sparse serial labels are deliberate: removing a
    nonexistent valve such as ``M(0,1)`` must not renumber downstream SCADA ids.
    Emits the EXACT input id strings (irregular spacing preserved) so the edges stay
    consistent with the gates dict. Raises ``NetworkTopologyError`` on a derived parent
    that is not among ``gate_ids`` or on two ids that normalize to the same node.
    """
    exact: dict[str, str] = {}
    for gate_id in gate_ids:
        normalized_id = _normalize_gate_id(gate_id)
        if normalized_id in exact:
            raise NetworkTopologyError(
                f"gate ids collide when normalized: {exact[normalized_id]!r} and {gate_id!r}"
            )
        exact[normalized_id] = gate_id
    serial_chains: dict = defaultdict(list)
    for normalized in exact:
        tuples = _parse_gate_id(normalized)
        chain_key = (tuple(tuples[:-1]), tuples[-1][0])
        serial_chains[chain_key].append((tuples[-1][1], normalized))
    previous_serial = {}
    for members in serial_chains.values():
        members.sort()
        for (_, parent), (_, child) in zip(members, members[1:]):
            previous_serial[child] = parent
    edges = []
    for gate_id in gate_ids:
        parent = _derived_parent(gate_id, previous_serial)
        if parent is None:
            edges.append((root, gate_id))
        elif parent in exact:
            edges.append((exact[parent], gate_id))
        else:
            raise NetworkTopologyError(
                f"gate {gate_id!r}: derived parent {parent!r} is not among the gates"
            )
    return edges
