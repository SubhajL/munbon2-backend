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

`seepage_rate_m_s` is PROVISIONAL (literature field values, pending a Tier-3 Munbon
inflow/outflow calibration). Geometry comes from `src/config/canal_geometry.json` (surveyed
sections); reaches with no section get zero loss and are flagged by the caller, never a
fabricated seepage number.

Seepage rates are AGED/deteriorated FIELD values, not new-lining design standards, because
the Munbon canals are ~50 years old. Sources (see docs/remediation/SEEPAGE_CALIBRATION.md):
  - NEW concrete standard: USBR (1975) 0.00024 L/s/m2 = 2.4e-7 m/s; FAO/Kraatz (1977) ~3e-7.
  - AGED concrete field (Turkey, ~30-60 yr): 0.0026-0.0754 L/s/m2 = 2.6e-6..7.5e-5 m/s
    (Bekifloglu 1993; Menemen ~1.4e-5, Ahmetli main 6.7e-5; Akkuzu et al.). Central ~1e-5.
  - FAO conveyance efficiency: lined 95% (~5% loss), "bad maintenance may lower ... by as
    much as 50%" -> aged lined mains realistically 70-90% efficient.
Operational loss defaults to 0: seepage is the dominant physical loss (Akkuzu 2011), and a
flat per-reach fraction is discretization-dependent (more gate nodes -> more modeled loss),
so it is not used by default; it stays a per-section knob if a calibrated value is supplied.

Pure (stdlib only). Reach keys join to the network by NORMALIZED gate id
(`core.node_id.normalize_gate_id`), since geometry uses compact ids and the
network edges use the exact (sometimes irregularly-spaced) gate-key strings.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from .node_id import NodeIdError, normalize_gate_id

# Aged/deteriorated field seepage flux by lining (m/s), PROVISIONAL pending Tier-3
# calibration. Ordering earth > unknown > concrete is preserved. See module docstring.
SEEPAGE_RATE_BY_LINING = {"concrete": 1.0e-5, "earth": 2.0e-5, "unknown": 1.5e-5}
DEFAULT_OPERATIONAL_LOSS_FRAC = 0.0
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
        key = (normalize_gate_id(s["from_node"]), normalize_gate_id(s["to_node"]))
        sections[key] = {
            "length_m": geo["length_m"],
            "cross_section": geo["cross_section"],
            "seepage_rate_m_s": seepage_rate_for_lining(hp.get("lining_type")),
            "operational_loss_frac": hp.get(
                "operational_loss_frac", DEFAULT_OPERATIONAL_LOSS_FRAC
            ),
        }
    return sections


def normalize_edge(upstream: str, downstream: str) -> tuple:
    """A reach key with gate ids normalized; non-gate endpoints (the source ``S``) pass
    through unchanged, so unknown junk simply fails membership checks downstream."""
    def norm(node: str) -> str:
        try:
            return normalize_gate_id(node)
        except NodeIdError:
            return node

    return (norm(upstream), norm(downstream))


def _lookup_section(sections_by_edge: dict, upstream: str, downstream: str) -> Optional[dict]:
    """The section for a reach, matched by normalized id; None if the edge has none or an
    endpoint is not a gate id (e.g. the source ``S``)."""
    try:
        key = (normalize_gate_id(upstream), normalize_gate_id(downstream))
    except NodeIdError:
        return None
    return sections_by_edge.get(key)


def make_reach_loss(
    sections_by_edge: dict,
    *,
    charge_dry_reaches: bool = False,
    always_wet: frozenset = frozenset(),
) -> ReachLoss:
    """A ``reach_loss(u, v, throughflow)`` for ``demand_aggregation.required_flow_per_reach``:
    the conveyance uplift where the reach has geometry, ``0.0`` where it does not (never a
    fabricated seepage).

    Dry-reach semantics (decision D1, PROGRAM_REVIEW_2026-07-09 §2.0): a reach carrying no
    flow for THIS plan is out of service and takes NO loss — fixed-depth seepage otherwise
    charges the whole surveyed network against every plan (~2.46 m3/s at zero demand).
    ``always_wet`` (normalized (u, v) reach keys) marks trunk canals that never drain and
    stay charged regardless; ``charge_dry_reaches=True`` restores the legacy
    everything-charged behavior for steady whole-network operation.
    """
    def reach_loss(upstream: str, downstream: str, throughflow: float) -> float:
        section = _lookup_section(sections_by_edge, upstream, downstream)
        if section is None:
            return 0.0
        if (
            throughflow <= 0.0
            and not charge_dry_reaches
            and normalize_edge(upstream, downstream) not in always_wet
        ):
            return 0.0
        return reach_loss_uplift(section, throughflow)

    return reach_loss


def reach_has_geometry(sections_by_edge: dict, upstream: str, downstream: str) -> bool:
    """True iff the reach (upstream, downstream) has a surveyed section (by normalized id)."""
    return _lookup_section(sections_by_edge, upstream, downstream) is not None
