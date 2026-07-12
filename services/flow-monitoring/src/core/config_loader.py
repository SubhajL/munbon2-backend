"""
core.config_loader — strict, fail-closed loading of the canonical runtime configs
(Wave 1.1, PROGRAM_REVIEW_2026-07-09 §2.2).

Every runtime read of ``src/config/*.json`` goes through here. Three failure classes
are rejected before any hydraulics can run on them: corrupt JSON (including the bare
``NaN``/``Infinity`` literals Python's ``json.dump`` emits but strict JSON forbids),
missing schema (absent or mistyped required keys), and metadata↔content drift
(declared counts that no longer match the data — a hand-edited or half-regenerated
file). Graph-structure validation (connectivity, spanning tree) stays with the
consumers in ``core.network_topology``.

Fail = raise ``ConfigError``. Never substitute defaults: a wrong-but-plausible config
is how this system silently misdelivers water.
"""
from __future__ import annotations

import json
import math

from .node_id import NodeIdError, normalize_gate_id

NETWORK_ROOT = "S"


class ConfigError(ValueError):
    """A canonical config file is unreadable, malformed, or self-inconsistent."""


def _reject_constant(name: str):
    raise ValueError(f"non-finite JSON constant {name}")


def load_strict_json_object(path: str) -> dict:
    """Read `path` as strict JSON (no NaN/Infinity) and require an object at top level."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read config file: {exc}") from exc
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:  # JSONDecodeError or a rejected constant
        raise ConfigError(f"{path}: not strict JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"{path}: top level must be a JSON object, got {type(data).__name__}"
        )
    return data


def _require_dict(data: dict, key: str, path: str) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: required object {key!r} is missing or not an object")
    return value


def _declared_count(container: dict, key: str, path: str, where: str) -> int:
    value = container.get(key)
    # bool is an int subclass; "2"/2.0 are truthy lookalikes — none may pass as a count.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{path}: {where}.{key} must be an integer, got {value!r}")
    return value


def _check_drift(declared: int, actual: int, path: str, label: str) -> None:
    if declared != actual:
        raise ConfigError(
            f"{path}: metadata drift: {label} declares {declared} but the file has {actual}"
        )


def _is_finite_number(value) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def load_network_config(path: str) -> dict:
    """The canonical network dict, or ConfigError on schema/drift violations.

    Validates: metadata.canonical is true; declared gate/edge counts match the content;
    every edge is a [parent, child] string pair with known endpoints; no duplicate edge.
    """
    data = load_strict_json_object(path)
    metadata = _require_dict(data, "metadata", path)
    gates = _require_dict(data, "gates", path)
    if not gates:
        raise ConfigError(f"{path}: 'gates' is empty")
    edges = data.get("edges")
    if not isinstance(edges, list) or not edges:
        raise ConfigError(f"{path}: required array 'edges' is missing or empty")
    if metadata.get("canonical") is not True:
        raise ConfigError(
            f"{path}: metadata.canonical must be true — refusing a non-canonical network"
        )
    normalized_nodes: dict = {}
    for gate_id, gate in gates.items():
        # Gate ids must parse under the naming grammar and stay unambiguous when
        # normalized — 'M(0,1)' beside 'M (0,1)' (or a leading-zero alias) would make
        # any-spacing id resolution at the boundaries ambiguous.
        try:
            normalized = normalize_gate_id(gate_id)
        except NodeIdError as exc:
            raise ConfigError(f"{path}: gates[{gate_id!r}]: invalid gate id: {exc}") from exc
        if normalized in normalized_nodes:
            raise ConfigError(
                f"{path}: gate ids collide when normalized:"
                f" {normalized_nodes[normalized]!r} and {gate_id!r}"
            )
        normalized_nodes[normalized] = gate_id
        if not isinstance(gate, dict):
            # capacity indexing would silently skip it and fall back to the default.
            raise ConfigError(f"{path}: gates[{gate_id!r}] is not an object")
        q_max = gate.get("q_max")
        if q_max is not None and (not _is_finite_number(q_max) or q_max <= 0):
            raise ConfigError(
                f"{path}: gates[{gate_id!r}].q_max must be null or a finite number > 0,"
                f" got {q_max!r}"
            )
    _check_drift(
        _declared_count(metadata, "total_gates", path, "metadata"),
        len(gates), path, "total_gates",
    )
    _check_drift(
        _declared_count(metadata, "total_connections", path, "metadata"),
        len(edges), path, "total_connections",
    )
    seen: set = set()
    for edge in edges:
        if not (
            isinstance(edge, list)
            and len(edge) == 2
            and all(isinstance(node, str) for node in edge)
        ):
            raise ConfigError(
                f"{path}: every edge must be a [parent, child] string pair, got {edge!r}"
            )
        parent, child = edge
        if child not in gates:
            raise ConfigError(f"{path}: edge child {child!r} is not a declared gate")
        if parent != NETWORK_ROOT and parent not in gates:
            raise ConfigError(
                f"{path}: edge parent {parent!r} is neither a gate nor the source"
                f" {NETWORK_ROOT!r}"
            )
        if (parent, child) in seen:
            raise ConfigError(f"{path}: duplicate edge {edge!r}")
        seen.add((parent, child))
    return data


def load_canal_geometry_config(path: str) -> dict:
    """The canonical geometry dict, or ConfigError on schema/drift violations.

    Validates: non-empty canal_sections, each with node ids, a finite positive
    length_m and a cross_section object; summary.total_sections matches the content.
    """
    data = load_strict_json_object(path)
    _require_dict(data, "metadata", path)
    sections = data.get("canal_sections")
    if not isinstance(sections, list) or not sections:
        raise ConfigError(f"{path}: required array 'canal_sections' is missing or empty")
    for i, section in enumerate(sections):
        where = f"canal_sections[{i}]"
        if not isinstance(section, dict):
            raise ConfigError(f"{path}: {where} is not an object")
        for key in ("from_node", "to_node"):
            if not (isinstance(section.get(key), str) and section[key]):
                raise ConfigError(f"{path}: {where}.{key} must be a non-empty string")
        geometry = section.get("geometry")
        if not isinstance(geometry, dict):
            raise ConfigError(f"{path}: {where}.geometry is missing or not an object")
        length = geometry.get("length_m")
        if not _is_finite_number(length) or length <= 0:
            raise ConfigError(
                f"{path}: {where}.geometry.length_m must be a finite number > 0,"
                f" got {length!r}"
            )
        cross_section = geometry.get("cross_section")
        if not isinstance(cross_section, dict):
            raise ConfigError(
                f"{path}: {where}.geometry.cross_section is missing or not an object"
            )
        # The B5 loss runtime computes the wetted perimeter from these; an empty
        # cross_section must fail here, not as a KeyError under apply_losses.
        for key in ("depth_m", "bottom_width_m"):
            value = cross_section.get(key)
            if not _is_finite_number(value) or value <= 0:
                raise ConfigError(
                    f"{path}: {where}.geometry.cross_section.{key} must be a finite"
                    f" number > 0, got {value!r}"
                )
        side_slope = cross_section.get("side_slope")
        if side_slope is not None and (
            not _is_finite_number(side_slope) or side_slope < 0
        ):
            raise ConfigError(
                f"{path}: {where}.geometry.cross_section.side_slope must be a finite"
                f" number >= 0 when present, got {side_slope!r}"
            )
    reaches = data.get("reaches")
    if reaches is not None:
        # 2.1b: per-reach gate-to-gate spans (head/tail gap measurement + the
        # legacy solver's physical reach length). Optional so pre-2.1b files
        # still load; when present it must be structurally sound.
        if not isinstance(reaches, list):
            raise ConfigError(f"{path}: 'reaches' must be an array when present")
        for i, reach in enumerate(reaches):
            where = f"reaches[{i}]"
            if not isinstance(reach, dict):
                raise ConfigError(f"{path}: {where} is not an object")
            for key in ("from_node", "to_node", "from_km", "to_km"):
                if not (isinstance(reach.get(key), str) and reach[key]):
                    raise ConfigError(
                        f"{path}: {where}.{key} must be a non-empty string"
                    )
            span = reach.get("span_m")
            if not _is_finite_number(span) or span <= 0:
                raise ConfigError(
                    f"{path}: {where}.span_m must be a finite number > 0,"
                    f" got {span!r}"
                )
            for key in ("covered_m", "gap_m"):
                value = reach.get(key)
                if not _is_finite_number(value) or value < 0:
                    raise ConfigError(
                        f"{path}: {where}.{key} must be a finite number >= 0,"
                        f" got {value!r}"
                    )
    summary = _require_dict(data, "summary", path)
    _check_drift(
        _declared_count(summary, "total_sections", path, "summary"),
        len(sections), path, "summary.total_sections",
    )
    return data


def load_gate_calibrations_config(path: str) -> dict:
    """The canonical calibrations dict, or ConfigError on schema/drift violations.

    Validates: declared total_gates/gates_with_k1_k2 match the content; has_calibration
    is a real boolean; every calibrated gate carries finite numeric k1/k2.
    """
    data = load_strict_json_object(path)
    metadata = _require_dict(data, "metadata", path)
    gates = _require_dict(data, "gates", path)
    if not gates:
        raise ConfigError(f"{path}: 'gates' is empty")
    calibrated = 0
    normalized_ids: dict = {}
    for gate_id, gate in gates.items():
        where = f"gates[{gate_id!r}]"
        try:
            normalized = normalize_gate_id(gate_id)
        except NodeIdError as exc:
            # A typo'd key silently pushes its real gate onto generic defaults via
            # get_calibration's fallback — refuse grammar-invalid ids at load.
            raise ConfigError(f"{path}: {where}: invalid gate id: {exc}") from exc
        if normalized in normalized_ids:
            raise ConfigError(
                f"{path}: gate ids collide when normalized:"
                f" {normalized_ids[normalized]!r} and {gate_id!r}"
            )
        normalized_ids[normalized] = gate_id
        if not isinstance(gate, dict):
            raise ConfigError(f"{path}: {where} is not an object")
        has_calibration = gate.get("has_calibration", False)
        if not isinstance(has_calibration, bool):
            raise ConfigError(
                f"{path}: {where}.has_calibration must be a boolean,"
                f" got {has_calibration!r}"
            )
        if has_calibration:
            calibrated += 1
            for key in ("k1", "k2"):
                if not _is_finite_number(gate.get(key)):
                    raise ConfigError(
                        f"{path}: {where}.{key} must be a finite number,"
                        f" got {gate.get(key)!r}"
                    )
    _check_drift(
        _declared_count(metadata, "total_gates", path, "metadata"),
        len(gates), path, "total_gates",
    )
    _check_drift(
        _declared_count(metadata, "gates_with_k1_k2", path, "metadata"),
        calibrated, path, "gates_with_k1_k2",
    )
    return data
