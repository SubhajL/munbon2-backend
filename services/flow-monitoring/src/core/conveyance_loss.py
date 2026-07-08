"""
core.conveyance_loss — Tier-1 conveyance (seepage + operational) loss model (B5).

Fills the ``reach_loss`` seam of ``core.demand_aggregation.required_flow_per_reach`` so a
head gate carries Sigma(demand) + Sigma(losses). Per reach, seepage is a wetted-perimeter
flux at a fixed operating depth (0.7 * design depth) plus a flat operational fraction of the
throughflow (spill/check leakage):

    Q_seep = seepage_rate_m_s * wetted_perimeter(cs, 0.7*depth) * length_m
    uplift = Q_seep + operational_loss_frac * throughflow

Because seepage is evaluated at a FIXED depth (not flow-dependent) and the operational term
is linear, a single leaves->root aggregation pass is exact — no relaxation needed.

`seepage_rate_m_s` is PROVISIONAL: literature defaults by lining, pending a Tier-3
inflow/outflow calibration. Geometry comes from `src/config/canal_geometry.json` (surveyed
sections); reaches with no section get zero loss and are flagged by the caller, never a
fabricated seepage number.

Pure (stdlib only). Reach keys join to the network by NORMALIZED gate id
(`core.network_topology._normalize_gate_id`), since geometry uses compact ids and the
network edges use the exact (sometimes irregularly-spaced) gate-key strings.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from .network_topology import NetworkTopologyError, _normalize_gate_id

# Literature seepage flux by lining (m/s), replaced by Tier-3 calibration later.
SEEPAGE_RATE_BY_LINING = {"concrete": 3.0e-7, "earth": 1.5e-6, "unknown": 1.0e-6}
DEFAULT_OPERATIONAL_LOSS_FRAC = 0.05
OPERATING_DEPTH_FRAC = 0.7

ReachLoss = Callable[[str, str, float], float]


def seepage_rate_for_lining(lining) -> float:
    """Literature seepage flux for a lining, defaulting to the ``unknown`` rate."""
    return SEEPAGE_RATE_BY_LINING.get(lining, SEEPAGE_RATE_BY_LINING["unknown"])


def wetted_perimeter(cross_section: dict, depth: float) -> float:
    """Trapezoidal wetted perimeter ``b + 2*y*sqrt(1 + m^2)`` at water depth ``y``."""
    b = cross_section["bottom_width_m"]
    m = cross_section.get("side_slope", 0.0)
    return b + 2.0 * depth * math.sqrt(1.0 + m * m)


def reach_seepage_m3s(section: dict) -> float:
    """Seepage flux ``rate * wetted_perimeter(cs, 0.7*depth) * length`` (m3/s)."""
    cs = section["cross_section"]
    depth = OPERATING_DEPTH_FRAC * cs["depth_m"]
    return section["seepage_rate_m_s"] * wetted_perimeter(cs, depth) * section["length_m"]


def reach_loss_uplift(section: dict, throughflow: float) -> float:
    """Total loss to add upstream: seepage (fixed) + operational fraction of throughflow."""
    op = section.get("operational_loss_frac", DEFAULT_OPERATIONAL_LOSS_FRAC)
    return reach_seepage_m3s(section) + op * throughflow


def sections_by_edge_from_geometry(geometry: dict) -> dict:
    """Index surveyed sections by NORMALIZED (from, to) gate id, enriching each with a
    ``seepage_rate_m_s`` derived from its ``lining_type`` (the survey has lining, not rate)."""
    sections: dict = {}
    for s in geometry.get("canal_sections", []):
        geo = s["geometry"]
        hp = geo.get("hydraulic_params", {})
        key = (_normalize_gate_id(s["from_node"]), _normalize_gate_id(s["to_node"]))
        sections[key] = {
            "length_m": geo["length_m"],
            "cross_section": geo["cross_section"],
            "seepage_rate_m_s": seepage_rate_for_lining(hp.get("lining_type")),
            "operational_loss_frac": hp.get(
                "operational_loss_frac", DEFAULT_OPERATIONAL_LOSS_FRAC
            ),
        }
    return sections


def _lookup_section(sections_by_edge: dict, upstream: str, downstream: str) -> Optional[dict]:
    """The section for a reach, matched by normalized id; None if the edge has none or an
    endpoint is not a gate id (e.g. the source ``S``)."""
    try:
        key = (_normalize_gate_id(upstream), _normalize_gate_id(downstream))
    except NetworkTopologyError:
        return None
    return sections_by_edge.get(key)


def make_reach_loss(sections_by_edge: dict) -> ReachLoss:
    """A ``reach_loss(u, v, throughflow)`` for ``demand_aggregation.required_flow_per_reach``:
    the conveyance uplift where the reach has geometry, ``0.0`` where it does not (never a
    fabricated seepage)."""
    def reach_loss(upstream: str, downstream: str, throughflow: float) -> float:
        section = _lookup_section(sections_by_edge, upstream, downstream)
        return reach_loss_uplift(section, throughflow) if section is not None else 0.0

    return reach_loss


def reach_has_geometry(sections_by_edge: dict, upstream: str, downstream: str) -> bool:
    """True iff the reach (upstream, downstream) has a surveyed section (by normalized id)."""
    return _lookup_section(sections_by_edge, upstream, downstream) is not None
