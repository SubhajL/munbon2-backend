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

from .config_loader import load_canal_geometry_config
from .conveyance_loss import (
    make_reach_loss,
    normalize_edge,
    reach_has_geometry,
    sections_by_edge_from_geometry,
)
from .demand_aggregation import required_flow_per_reach
from .network_topology import (
    NetworkTopologyError,
    is_spanning_tree,
    load_validated_network,
    nodes_of,
)
from .node_id import normalize_node_id


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
        # load_validated_network only guards connectivity; the subtree-per-reach aggregation
        # also needs a proper spanning tree (no node with two parents) — enforce it here so a
        # malformed network fails at startup, not on every /plan request.
        if not is_spanning_tree(self.edges):
            raise NetworkTopologyError(
                f"{network_path}: network is connected but not a spanning tree "
                "(a node has multiple parents); aggregation would double-count it"
            )
        self.sections: dict = {}
        if geometry_path is not None:
            # Strict schema/drift validation (Wave 1.1) before the geometry is indexed.
            self.sections = sections_by_edge_from_geometry(
                load_canal_geometry_config(geometry_path)
            )
            if not self.sections:
                # geometry supplied but unusable -> losses would silently be zero; fail closed.
                raise ValueError(
                    f"{geometry_path}: geometry file has no usable canal_sections"
                )
        self.reaches_missing_geometry = {
            edge for edge in self.edges
            if not reach_has_geometry(self.sections, edge[0], edge[1])
        }
        self._normalized_edges = {normalize_edge(u, v) for u, v in self.edges}
        # Any-spacing id resolution (Wave 1.2): canonical compact form -> the exact
        # network key. Uniqueness is guaranteed by load_network_config's grammar +
        # normalized-collision validation.
        self._exact_by_normalized = {
            normalize_node_id(node): node for node in nodes_of(self.edges)
        }
        orphans = sorted(set(self.sections) - self._normalized_edges)
        if orphans:
            # Geometry describing reaches the network does not have means the two
            # files drifted apart (e.g. a half-regenerated survey) — fail closed
            # rather than silently losing loss coverage on the real reaches.
            raise ValueError(
                f"{geometry_path}: geometry sections are not network reaches: "
                f"{[list(edge) for edge in orphans[:5]]}"
                f"{'...' if len(orphans) > 5 else ''}"
            )

    def required_flow_per_reach(
        self,
        node_demand: dict,
        apply_losses: bool = False,
        charge_dry_reaches: bool = False,
        always_wet=(),
    ) -> dict:
        """Flow each reach must carry to serve `node_demand`, keyed by (upstream, downstream).

        With `apply_losses=True` and geometry loaded, each reach also carries its conveyance
        (seepage + operational) loss (B5); otherwise the result is the lossless A1–A3 sum.
        Dry-reach semantics (D1): reaches with no flow in this plan take no loss unless
        listed in `always_wet` ([upstream, downstream] pairs, any id spacing — must be real
        network reaches, fail-closed) or `charge_dry_reaches=True` (legacy whole-network
        steady mode). Both knobs require `apply_losses=True`.
        """
        if not apply_losses and (charge_dry_reaches or always_wet):
            raise ValueError(
                "charge_dry_reaches/always_wet only make sense with apply_losses=True"
            )
        node_demand = self._resolve_demands(node_demand)
        reach_loss = None
        if apply_losses:
            wet = set()
            unknown = []
            no_geometry = []
            for pair in always_wet:
                upstream, downstream = pair
                key = normalize_edge(upstream, downstream)
                if key not in self._normalized_edges:
                    unknown.append([upstream, downstream])
                elif key not in self.sections:
                    # "keep this reach charged" is unfulfillable without surveyed geometry
                    # (loss would silently be 0) -> fail closed, don't feign coverage.
                    no_geometry.append([upstream, downstream])
                else:
                    wet.add(key)
            if unknown:
                raise ValueError(f"always_wet contains unknown reaches: {unknown}")
            if no_geometry:
                raise ValueError(
                    "always_wet reaches have no surveyed geometry (their seepage cannot "
                    f"be charged): {no_geometry}"
                )
            reach_loss = make_reach_loss(
                self.sections,
                charge_dry_reaches=charge_dry_reaches,
                always_wet=frozenset(wet),
            )
        return required_flow_per_reach(self.edges, node_demand, reach_loss=reach_loss)

    def _resolve_demands(self, node_demand: dict) -> dict:
        """Demand keys accepted in ANY spacing (compact canonical or survey-spaced),
        re-keyed to the network-exact ids (Wave 1.2). Unknown ids and two keys naming
        the same physical node fail closed; values are validated downstream."""
        resolved: dict = {}
        alias_of: dict = {}
        for node_id, value in node_demand.items():
            if not isinstance(node_id, str):
                raise ValueError(f"demand key is not a node id string: {node_id!r}")
            exact = self._exact_by_normalized.get(normalize_node_id(node_id))
            if exact is None:
                raise ValueError(
                    f"demand for unknown node {node_id!r} (not in the network)"
                )
            if exact in resolved:
                raise ValueError(
                    "demand keys collide after normalization:"
                    f" {alias_of[exact]!r} and {node_id!r} both name {exact!r}"
                )
            resolved[exact] = value
            alias_of[exact] = node_id
        return resolved
