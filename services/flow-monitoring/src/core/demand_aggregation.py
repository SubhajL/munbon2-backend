"""
core.demand_aggregation — graph-descendants demand aggregation (A1–A3).

Replaces the hardcoded 3-zone path table / synthetic node IDs / per-zone granularity
(audit A1/A2/A3) with a post-order sum over the connected canonical spanning tree
(`core.network_topology`): the flow that must cross reach ``(u, v)`` equals the total
water demand of the subtree rooted at ``v`` — ``v``'s own demand plus every descendant.
Every node with irrigated area contributes, and interior delivery nodes contribute
their OWN demand too (A4 rationale; 20 of 33 demand nodes are interior).

Pure (stdlib only), I/O-free — the network is loaded elsewhere and passed in as edges.
Reach keys are ``(upstream, downstream)`` tuples.

The `reach_loss` hook is the seam for B5 conveyance loss (a later P1 item): B5 supplies a
callable returning the extra flow a reach must carry; until then it defaults to zero loss.
"""
from __future__ import annotations

from typing import Callable, Optional

from .network_topology import (
    ROOT,
    NetworkTopologyError,
    children_of,
    is_spanning_tree,
    nodes_of,
    topological_order,
)

# A reach-loss function takes (upstream, downstream, through_flow) and returns the extra
# flow (seepage + operational) the reach must carry on top of the demand passing through.
ReachLoss = Callable[[str, str, float], float]


def _validate(edges, node_demand: dict, root: str) -> None:
    """Fail closed on inputs the aggregation cannot meaningfully serve.

    - the graph must be a spanning tree rooted at `root` (else the subtree-per-reach model
      double-counts a node with two parents) -> NetworkTopologyError via is_spanning_tree;
    - every demand key must be a real network node (kills synthetic ids like "Zone2", A2);
    - demand must be non-negative and never attach to the source (no upstream reach carries it).
    """
    if not is_spanning_tree(edges, root):
        raise NetworkTopologyError(
            f"demand aggregation requires a spanning tree rooted at {root!r}; "
            "got a graph that is not one"
        )
    nodes = nodes_of(edges)
    for node, value in node_demand.items():
        if node not in nodes:
            raise ValueError(f"demand for unknown node {node!r} (not in the network)")
        if node == root:
            raise ValueError(f"source node {root!r} cannot carry demand")
        if value < 0:
            raise ValueError(f"demand for {node!r} is negative: {value}")


def required_flow_per_reach(
    edges,
    node_demand: dict,
    root: str = ROOT,
    reach_loss: Optional[ReachLoss] = None,
) -> dict:
    """Flow each reach (u, v) must carry = the demand of the subtree rooted at v.

    A single leaves->root (reverse topological) sweep: each node's subtree demand is its
    own demand plus, for every child reach, the flow through that reach (child subtree +
    optional loss). This replaces the hardcoded 3-zone path table (A1/A3) — every node
    with demand contributes to exactly the reaches on its path to the source, and interior
    delivery nodes keep their own demand (A4). `reach_loss(u, v, through)` optionally adds
    conveyance loss on each reach (the B5 seam); with the default None the head reach
    carries exactly the sum of all demand, and losses compound up-tree when supplied.
    """
    _validate(edges, node_demand, root)
    children = children_of(edges)
    subtree: dict = {}
    reach_flow: dict = {}
    for node in reversed(topological_order(edges)):
        total = float(node_demand.get(node, 0.0))
        for child in children.get(node, []):
            through = subtree[child]
            loss = 0.0 if reach_loss is None else reach_loss(node, child, through)
            flow = through + loss
            reach_flow[(node, child)] = flow
            total += flow
        subtree[node] = total
    return reach_flow
