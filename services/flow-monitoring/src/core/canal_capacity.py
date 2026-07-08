"""
core.canal_capacity — per-reach canal capacity from the canonical network (F-04).

Replaces `hydraulic_service._get_canal_capacity`'s hardcoded 15.0 m3/s with the real
rated capacity of the reach, taken from the downstream gate's `q_max` in the canonical
`network.json`. A reach `C_{upstream}_{downstream}` cannot carry more than the gate that
terminates it passes; when a reach's capacity is unknown the caller falls back to a
documented default and flags it (rather than silently assuming 15.0).

Pure (stdlib only).
"""
from __future__ import annotations

import math


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
        if isinstance(q, (int, float)) and not isinstance(q, bool) and math.isfinite(q) and q > 0:
            index[gate_id] = float(q)
    return index


def reach_capacity(capacity_index: dict, canal_id: str, default: float) -> tuple[float, bool]:
    """Return (capacity_m3s, from_data) for a reach.

    `from_data` is True when the capacity came from the downstream gate's rated q_max,
    False when it fell back to `default` (unknown reach / missing q_max) — the caller
    should log the fallback so a hardcoded default is never silent.
    """
    node = downstream_node(canal_id)
    if node is not None and node in capacity_index:
        return capacity_index[node], True
    return default, False
