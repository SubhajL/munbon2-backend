"""
core.canal_capacity — per-reach canal capacity from the canonical network (F-04).

Replaces `hydraulic_service._get_canal_capacity`'s hardcoded 15.0 m3/s with the real
rated capacity of the reach, taken from the downstream gate's `q_max` in the canonical
`network.json`. A reach `C_{upstream}_{downstream}` cannot carry more than the gate that
terminates it passes; when a reach's capacity is unknown the caller falls back to a
documented default and flags it (rather than silently assuming 15.0).

Wave 2.1a (WAVE_2-4_PLAN §1.5 amendment #2): a reach is also bounded by its weakest
surveyed canal segment — capacity = min(downstream gate rating, min segment q_max)
over whichever of the two is known.

Pure (stdlib + core.node_id only).
"""
from __future__ import annotations

from .config_loader import is_positive_finite
from .node_id import NodeIdError, normalize_gate_id


def downstream_node(canal_id: str) -> str | None:
    """Extract the downstream gate id from a reach id `C_{upstream}_{downstream}`.

    Gate ids (e.g. ``M(0,3)``, ``S``) contain no underscores, so the reach id splits
    cleanly on ``_`` into the ``C`` prefix, the upstream node, and the downstream node.
    """
    if not canal_id.startswith("C_"):
        return None
    parts = canal_id[2:].split("_")
    if len(parts) < 2:
        return None
    return parts[-1]


def build_capacity_index(network: dict) -> dict:
    """Map gate_id -> rated q_max (m3/s) from a canonical network dict.

    Gates whose `q_max` is missing, non-numeric, non-finite (NaN/inf), or non-positive
    are omitted, so callers detect and flag missing data instead of comparing against a
    NaN capacity (which would make every over-capacity check silently false).
    """
    gates = network.get("gates", {})
    index: dict = {}
    for gate_id, gate in gates.items():
        if not isinstance(gate, dict):
            continue
        q = gate.get("q_max")
        if is_positive_finite(q):
            index[gate_id] = float(q)
    return index


def reach_nodes(canal_id: str) -> tuple[str, str] | None:
    """Extract (upstream, downstream) from a reach id `C_{upstream}_{downstream}`."""
    if not canal_id.startswith("C_"):
        return None
    parts = canal_id[2:].split("_")
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _normalize(node: str) -> str:
    try:
        return normalize_gate_id(node)
    except NodeIdError:
        return node


def min_segment_q_max(segments: list) -> float | None:
    """The weakest valid segment rating in a reach's surveyed segment list, or None.

    Invalid ratings (missing, non-numeric, bool, NaN/inf, non-positive) are ignored so
    a partially-rated reach still gets a bound from the segments that have one.
    """
    valid = [
        float(q)
        for segment in segments
        for q in [segment.get("q_max")]
        if is_positive_finite(q)
    ]
    return min(valid) if valid else None


def reach_capacity(
    capacity_index: dict,
    canal_id: str,
    default: float,
    sections_by_edge: dict | None = None,
) -> tuple[float, bool]:
    """Return (capacity_m3s, from_data) for a reach.

    Capacity = min over the known bounds: the downstream gate's rated q_max and the
    weakest surveyed canal segment (2.1a) when `sections_by_edge` (keyed by NORMALIZED
    (upstream, downstream)) is supplied. `from_data` is False only when NO bound is
    known and the value fell back to `default` — the caller should log that fallback
    so a hardcoded default is never silent.
    """
    bounds = []
    node = downstream_node(canal_id)
    if node is not None and node in capacity_index:
        bounds.append(capacity_index[node])
    if sections_by_edge:
        nodes = reach_nodes(canal_id)
        if nodes is not None:
            segments = sections_by_edge.get(
                (_normalize(nodes[0]), _normalize(nodes[1]))
            )
            if segments:
                segment_bound = min_segment_q_max(segments)
                if segment_bound is not None:
                    bounds.append(segment_bound)
    if bounds:
        return min(bounds), True
    return default, False
