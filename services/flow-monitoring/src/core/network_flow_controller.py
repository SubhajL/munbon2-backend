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

import json

from .conveyance_loss import (
    make_reach_loss,
    reach_has_geometry,
    sections_by_edge_from_geometry,
)
from .demand_aggregation import required_flow_per_reach
from .network_topology import load_validated_network


class NetworkFlowController:
    """Loads the canonical network once (connectivity-guarded) and computes required
    per-reach flow from a per-node demand. This is the A1–A3 + B5 slice of the spec-§10
    consolidation module; later items attach the demand contract and the SCADA bridge.

    When a `geometry_path` is given, per-reach conveyance loss (B5) can be applied; reaches
    without a surveyed section are surfaced in `reaches_missing_geometry` (they take zero
    loss — never a fabricated seepage).
    """

    def __init__(self, network_path: str, geometry_path: str | None = None):
        self.edges = load_validated_network(network_path)
        self.sections: dict = {}
        if geometry_path is not None:
            with open(geometry_path, encoding="utf-8") as f:
                self.sections = sections_by_edge_from_geometry(json.load(f))
        self.reaches_missing_geometry = {
            edge for edge in self.edges
            if not reach_has_geometry(self.sections, edge[0], edge[1])
        }

    def required_flow_per_reach(self, node_demand: dict, apply_losses: bool = False) -> dict:
        """Flow each reach must carry to serve `node_demand`, keyed by (upstream, downstream).

        With `apply_losses=True` and geometry loaded, each reach also carries its conveyance
        (seepage + operational) loss (B5); otherwise the result is the lossless A1–A3 sum.
        """
        reach_loss = make_reach_loss(self.sections) if apply_losses else None
        return required_flow_per_reach(self.edges, node_demand, reach_loss=reach_loss)
