"""
core.node_id — canonical home of the ``M(i,j;...)`` gate-id naming grammar (Wave 1.2).

The SCADA survey writes gate ids with irregular spacing (``M (0,1; 1,0)``, 44 of 59
ids contain spaces) while programmatic producers use the compact form (``M(0,1;1,0)``).
This module owns parsing and the canonical compact format so every boundary — the
control API, geometry and calibration joins, config validation — normalizes the same
way instead of matching exact strings.

Leaf module: pure stdlib, imports nothing from ``core`` (config_loader and
network_topology import it, never the other way around).
"""
from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


class NodeIdError(ValueError):
    """A gate id does not conform to the ``M(i,j;...)`` naming grammar."""


def parse_gate_id(gate_id: str) -> list[tuple[int, int]]:
    """Parse ``M(0,1; 1,0)`` (any spacing) into ``[(0, 1), (1, 0)]``."""
    s = _WHITESPACE.sub("", gate_id)
    if not (s.startswith("M(") and s.endswith(")")):
        raise NodeIdError(f"malformed gate id {gate_id!r}")
    pairs = []
    for pair in s[2:-1].split(";"):
        parts = pair.split(",")
        # non-negative integers only: negative branch/position is a malformed id.
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise NodeIdError(f"malformed gate id {gate_id!r}")
        # leading zeros (M(00,00), M(0,00)) are textual aliases of another node:
        # they normalize to the same tuples but break exact-string consumers.
        if any(len(p) > 1 and p[0] == "0" for p in parts):
            raise NodeIdError(f"malformed gate id {gate_id!r} (leading zero)")
        pairs.append((int(parts[0]), int(parts[1])))
    return pairs


def format_gate_tuples(tuples_) -> str:
    """The canonical compact id for parsed tuples, e.g. ``M(0,1;1,0)``."""
    return "M(" + ";".join(f"{branch},{pos}" for branch, pos in tuples_) + ")"


def normalize_gate_id(gate_id: str) -> str:
    """Canonical compact form of a gate id; raises ``NodeIdError`` if malformed."""
    return format_gate_tuples(parse_gate_id(gate_id))


def normalize_node_id(node_id: str) -> str:
    """Canonical form of any network node id: gate ids are compacted, non-gate ids
    (the source ``S``) pass through unchanged — unknown junk simply fails membership
    checks downstream instead of being mangled here."""
    try:
        return normalize_gate_id(node_id)
    except NodeIdError:
        return node_id
