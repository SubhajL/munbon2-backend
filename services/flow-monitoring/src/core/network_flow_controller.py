"""
core.network_flow_controller — canonical demand→flow controller (spec §10 consolidation).

This module is the single home the remediation spec designates for flow-per-gate
computation (C9/C10), replacing the divergent duplicate implementations. It is being
built incrementally, item-by-item; this increment adds only the A1–A3 aggregation entry
point (`required_flow_per_reach`). Later P1 items attach the demand producer/contract
(C12), conveyance loss (B5), the branch-split inverse (B8), and the SCADA bridge, and
wire it into the running service (F-03/C9).

The controller loads and connectivity-guards the canonical network once at construction
(`core.network_topology.load_validated_network`) and delegates the pure aggregation to
`core.demand_aggregation`.
"""
from __future__ import annotations

from .demand_aggregation import required_flow_per_reach
from .network_topology import load_validated_network


class NetworkFlowController:
    """Loads the canonical network once (connectivity-guarded) and computes required
    per-reach flow from a per-node demand. This is the A1–A3 slice of the spec-§10
    consolidation module; later items attach the demand contract, loss, and SCADA bridge.
    """

    def __init__(self, network_path: str):
        self.edges = load_validated_network(network_path)

    def required_flow_per_reach(self, node_demand: dict) -> dict:
        """Flow each reach must carry to serve `node_demand`, keyed by (upstream, downstream)."""
        return required_flow_per_reach(self.edges, node_demand)
