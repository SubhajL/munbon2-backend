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

Wave 2.1a (WAVE_2-4_PLAN §1.5 amendment #2): a reach is an ORDERED LIST of
surveyed segments, not a single record. Multiple survey rows for one (from, to)
edge — which the 99-subsegment Characteristics sheet produces — are sorted by
chainage and validated non-overlapping; seepage sums per segment. The pre-2.1a
indexer silently kept only the LAST row.
"""
from __future__ import annotations

import math
import re
from typing import Callable, Optional

from .config_loader import ConfigError, is_positive_finite
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


def parse_chainage_m(km_marker) -> Optional[float]:
    """Survey chainage ``K+MMM`` (e.g. ``11+800``) in metres; None when absent or
    unparseable — the caller decides whether ordering is required."""
    if not isinstance(km_marker, str):
        return None
    match = re.fullmatch(r"(\d+)\+(\d+(?:\.\d+)?)", km_marker.strip())
    if not match:
        return None
    return float(match.group(1)) * 1000.0 + float(match.group(2))


def _segment_seepage_m3s(segment: dict) -> float:
    """Seepage flux ``rate * wetted_perimeter(cs, 0.7*depth) * length`` (m3/s)."""
    cs = segment["cross_section"]
    depth = OPERATING_DEPTH_FRAC * cs["depth_m"]
    return segment["seepage_rate_m_s"] * wetted_perimeter(cs, depth) * segment["length_m"]


def reach_seepage_m3s(segments: list) -> float:
    """Reach seepage: the sum over its ordered surveyed segments (m3/s)."""
    return sum(_segment_seepage_m3s(segment) for segment in segments)


def reach_loss_uplift(segments: list, throughflow: float) -> float:
    """Total loss to add upstream: summed segment seepage (fixed) + the reach
    operational fraction of throughflow.

    The operational fraction is a REACH-level concept: explicit per-segment values
    sum; when NO segment carries one, the default applies ONCE per reach — never
    once per segment (a 99-subsegment reach must not charge 99x the default)."""
    explicit = [
        segment.get("operational_loss_frac")
        for segment in segments
        if segment.get("operational_loss_frac") is not None
    ]
    op = sum(explicit) if explicit else DEFAULT_OPERATIONAL_LOSS_FRAC
    return reach_seepage_m3s(segments) + op * throughflow


def reach_chainage_gap_m(segments: list, span: Optional[tuple] = None) -> Optional[float]:
    """Total unsurveyed chainage of a reach (metres); 0.0 for a full survey,
    None when any segment lacks parseable chainage.

    Without ``span``, only gaps BETWEEN consecutive segments are measurable.
    With ``span`` = (reach_from_m, reach_to_m) — the gate-to-gate chainage the
    2.1b geometry carries in its ``reaches`` block — head and tail gaps count
    too: all five real partial reaches have their gap at a reach boundary
    (the M(0,0) flume, four canal tails), which between-segment measurement
    alone reports as zero.

    Partial surveys are LEGAL (several gates lack lengths entirely) — but they must
    be measurable so coverage consumers can surface incomplete reaches instead of
    silently understating seepage and capacity."""
    if any(
        segment["from_km_m"] is None or segment["to_km_m"] is None
        for segment in segments
    ):
        return None
    gap = 0.0
    for prev, nxt in zip(segments, segments[1:]):
        gap += max(0.0, nxt["from_km_m"] - prev["to_km_m"])
    if span is not None and segments:
        gap += max(0.0, segments[0]["from_km_m"] - span[0])
        gap += max(0.0, span[1] - segments[-1]["to_km_m"])
    return gap


def reach_spans_from_geometry(geometry: dict) -> dict:
    """Gate-to-gate chainage span per NORMALIZED (from, to) edge, from the
    geometry's ``reaches`` block (2.1b); {} for a pre-2.1b file without one.

    A reach record whose chainage does not parse or runs backwards is a broken
    artifact — fail closed rather than silently lose gap measurement."""
    spans: dict = {}
    for reach in geometry.get("reaches", []):
        key = (
            normalize_gate_id(reach["from_node"]),
            normalize_gate_id(reach["to_node"]),
        )
        from_m = parse_chainage_m(reach.get("from_km"))
        to_m = parse_chainage_m(reach.get("to_km"))
        if from_m is None or to_m is None or to_m <= from_m:
            raise ConfigError(
                f"reaches[{reach['from_node']!r} -> {reach['to_node']!r}]: span"
                f" chainage must parse and run forward, got"
                f" {reach.get('from_km')!r}..{reach.get('to_km')!r}"
            )
        spans[key] = (from_m, to_m)
    return spans


def _valid_q_max(value) -> Optional[float]:
    return float(value) if is_positive_finite(value) else None


def sections_by_edge_from_geometry(geometry: dict) -> dict:
    """Ordered surveyed segments per NORMALIZED (from, to) gate-id edge.

    Each segment carries its own cross-section, a ``seepage_rate_m_s`` derived from
    its ``lining_type`` (the survey has lining, not rate), the segment ``q_max``
    when valid, and parsed chainage. Multiple rows for one edge are subsegments:
    every row then needs parseable ``from_km``/``to_km`` (otherwise they are
    un-orderable), spans must run forward, and segments must not overlap — each of
    those used to be a silent last-row-wins overwrite."""
    grouped: dict = {}
    for s in geometry.get("canal_sections", []):
        geo = s["geometry"]
        hp = geo.get("hydraulic_params", {})
        key = (normalize_gate_id(s["from_node"]), normalize_gate_id(s["to_node"]))
        grouped.setdefault(key, []).append({
            "length_m": geo["length_m"],
            "cross_section": geo["cross_section"],
            "seepage_rate_m_s": seepage_rate_for_lining(hp.get("lining_type")),
            # None when the survey has no explicit value: reach_loss_uplift applies
            # the reach default ONCE, never once per segment.
            "operational_loss_frac": hp.get("operational_loss_frac"),
            "q_max": _valid_q_max(hp.get("q_max")),
            "from_km_m": parse_chainage_m(s.get("from_km")),
            "to_km_m": parse_chainage_m(s.get("to_km")),
        })
    for key, segments in grouped.items():
        # Span sanity applies to EVERY row whose chainage is parseable — single
        # rows included (an inverted marker is bad survey data either way).
        for segment in segments:
            if (
                segment["from_km_m"] is not None
                and segment["to_km_m"] is not None
                and segment["to_km_m"] <= segment["from_km_m"]
            ):
                raise ConfigError(
                    f"edge {key}: segment span must run forward, got"
                    f" {segment['from_km_m']}..{segment['to_km_m']}"
                )
        if len(segments) == 1:
            continue
        if any(
            segment["from_km_m"] is None or segment["to_km_m"] is None
            for segment in segments
        ):
            raise ConfigError(
                f"edge {key}: multiple survey segments require parseable chainage"
                " (from_km/to_km) on every row"
            )
        segments.sort(key=lambda segment: segment["from_km_m"])
        for prev, nxt in zip(segments, segments[1:]):
            if nxt["from_km_m"] < prev["to_km_m"] - 1e-9:
                raise ConfigError(
                    f"edge {key}: segments overlap at chainage"
                    f" {nxt['from_km_m']} < {prev['to_km_m']}"
                )
    return grouped


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
