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

import hashlib
import json
import math

from .node_id import NodeIdError, normalize_gate_id

NETWORK_ROOT = "S"

# Tolerance for the inferred-coefficient donor-range bound: wide enough to absorb the
# generator's 6-decimal rounding of a weighted average, tight enough to still reject a
# materially out-of-range coefficient.
_RANGE_TOL = 1e-6


class ConfigError(ValueError):
    """A canonical config file is unreadable, malformed, or self-inconsistent."""


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        raise ConfigError(
            f"{path}: required object {key!r} is missing or not an object"
        )
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


def is_positive_finite(value) -> bool:
    """A finite number strictly greater than zero (rejects None, bool, NaN, inf, <=0).
    The canonical positive-magnitude predicate — reuse it rather than re-inlining the
    isinstance/isfinite/>0 checks."""
    return _is_finite_number(value) and value > 0


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
            raise ConfigError(
                f"{path}: gates[{gate_id!r}]: invalid gate id: {exc}"
            ) from exc
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
        len(gates),
        path,
        "total_gates",
    )
    _check_drift(
        _declared_count(metadata, "total_connections", path, "metadata"),
        len(edges),
        path,
        "total_connections",
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
        raise ConfigError(
            f"{path}: required array 'canal_sections' is missing or empty"
        )
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
        len(sections),
        path,
        "summary.total_sections",
    )
    return data


def load_gate_calibrations_config(path: str) -> dict:
    """The canonical calibrations dict, or ConfigError on schema/drift violations.

    Measured, inferred and default records have explicit, non-interchangeable
    provenance. Inferred records may only cite measured gates from the same file.
    """
    data = load_strict_json_object(path)
    metadata = _require_dict(data, "metadata", path)
    source_workbook = metadata.get("source_workbook")
    if not isinstance(source_workbook, str) or not source_workbook.strip():
        raise ConfigError(
            f"{path}: metadata.source_workbook must be a non-empty string,"
            f" got {source_workbook!r}"
        )
    gates = _require_dict(data, "gates", path)
    if not gates:
        raise ConfigError(f"{path}: 'gates' is empty")
    source_sha256 = metadata.get("source_sha256")
    if not isinstance(source_sha256, str) or not source_sha256.strip():
        raise ConfigError(
            f"{path}: metadata.source_sha256 must be a non-empty string,"
            f" got {source_sha256!r}"
        )
    if metadata.get("intended_use") != "planning_only":
        raise ConfigError(
            f"{path}: metadata.intended_use must be 'planning_only',"
            f" got {metadata.get('intended_use')!r}"
        )
    if metadata.get("design_fsl_reference_side") != "upstream":
        raise ConfigError(
            f"{path}: metadata.design_fsl_reference_side must be 'upstream',"
            f" got {metadata.get('design_fsl_reference_side')!r}"
        )
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
        if gate_id != normalized:
            raise ConfigError(
                f"{path}: {where}: gate id must use canonical compact form"
                f" {normalized!r}"
            )
        normalized_ids[normalized] = gate_id
        if not isinstance(gate, dict):
            raise ConfigError(f"{path}: {where} is not an object")
        if gate.get("gate_id") != gate_id:
            raise ConfigError(
                f"{path}: {where}.gate_id must exactly match its key,"
                f" got {gate.get('gate_id')!r}"
            )

    methods = ("measured", "inferred", "default")
    method_counts = {method: 0 for method in methods}
    for gate_id, gate in gates.items():
        where = f"gates[{gate_id!r}]"
        method = gate.get("calibration_method")
        if method not in methods:
            raise ConfigError(
                f"{path}: {where}.calibration_method must be one of {methods},"
                f" got {method!r}"
            )
        method_counts[method] += 1
        confidence = gate.get("confidence")
        if not _is_finite_number(confidence) or not 0.0 <= confidence <= 1.0:
            raise ConfigError(
                f"{path}: {where}.confidence must be a finite number in [0, 1],"
                f" got {confidence!r}"
            )
        shape = gate.get("shape")
        if shape is not None and shape not in ("rectangular", "circular"):
            raise ConfigError(
                f"{path}: {where}.shape must be 'rectangular' or 'circular',"
                f" got {shape!r}"
            )
        for dimension in ("width_m", "height_m"):
            value = gate.get(dimension)
            if value is not None and (not _is_finite_number(value) or value <= 0):
                raise ConfigError(
                    f"{path}: {where}.{dimension} must be a finite number > 0,"
                    f" got {value!r}"
                )
        if shape == "circular" and (
            gate.get("width_m") is None
            or gate.get("height_m") is None
            or gate["width_m"] != gate["height_m"]
        ):
            raise ConfigError(
                f"{path}: {where}: circular width_m must equal height_m (diameter)"
            )
        structure_role = gate.get("structure_role")
        structure_roles = ("control", "junction", "tail", "turnout", "unknown")
        if structure_role not in structure_roles:
            raise ConfigError(
                f"{path}: {where}.structure_role must be one of"
                f" {structure_roles}, got {structure_role!r}"
            )
        structure_values = {}
        for key in (
            "design_fsl_msl_m",
            "sill_msl_m",
            "structure_max_flow_m3s",
        ):
            if key not in gate:
                raise ConfigError(f"{path}: {where}.{key} is required")
            value = gate[key]
            if value is not None and not _is_finite_number(value):
                raise ConfigError(
                    f"{path}: {where}.{key} must be a finite number or null,"
                    f" got {value!r}"
                )
            structure_values[key] = value
        if (
            structure_values["structure_max_flow_m3s"] is not None
            and structure_values["structure_max_flow_m3s"] <= 0
        ):
            raise ConfigError(
                f"{path}: {where}.structure_max_flow_m3s must be > 0 when present,"
                f" got {structure_values['structure_max_flow_m3s']!r}"
            )
        if (
            structure_values["design_fsl_msl_m"] is not None
            and structure_values["sill_msl_m"] is not None
            and structure_values["design_fsl_msl_m"] <= structure_values["sill_msl_m"]
        ):
            raise ConfigError(
                f"{path}: {where}.design_fsl_msl_m must exceed sill_msl_m"
            )
        expected_side = (
            "upstream" if structure_values["design_fsl_msl_m"] is not None else None
        )
        if gate.get("design_fsl_reference_side") != expected_side:
            raise ConfigError(
                f"{path}: {where}.design_fsl_reference_side must be"
                f" {expected_side!r}, got"
                f" {gate.get('design_fsl_reference_side')!r}"
            )
        presence = tuple(value is not None for value in structure_values.values())
        expected_status = (
            "complete"
            if all(presence)
            else "unavailable"
            if not any(presence)
            else "incomplete"
        )
        if gate.get("structure_data_status") != expected_status:
            raise ConfigError(
                f"{path}: {where}.structure_data_status must be"
                f" {expected_status!r}, got {gate.get('structure_data_status')!r}"
            )
        source_version = gate.get("source_version")
        if not isinstance(source_version, str) or not source_version.strip():
            raise ConfigError(
                f"{path}: {where}.source_version must be a non-empty string,"
                f" got {source_version!r}"
            )
        source_gate_ids = gate.get("source_gate_ids")
        if not isinstance(source_gate_ids, list):
            raise ConfigError(
                f"{path}: {where}.source_gate_ids must be an array,"
                f" got {source_gate_ids!r}"
            )
        normalized_sources = []
        for source_gate_id in source_gate_ids:
            if not isinstance(source_gate_id, str):
                raise ConfigError(
                    f"{path}: {where}.source_gate_ids must contain gate-id strings"
                )
            try:
                normalized_source = normalize_gate_id(source_gate_id)
            except NodeIdError as exc:
                raise ConfigError(
                    f"{path}: {where}.source_gate_ids contains an invalid gate id:"
                    f" {source_gate_id!r}"
                ) from exc
            if source_gate_id != normalized_source:
                raise ConfigError(
                    f"{path}: {where}.source_gate_ids must use canonical compact ids"
                )
            if normalized_source not in normalized_ids:
                raise ConfigError(
                    f"{path}: {where}.source_gate_ids contains unknown gate"
                    f" {source_gate_id!r}"
                )
            normalized_sources.append(normalized_source)
        if len(set(normalized_sources)) != len(normalized_sources):
            raise ConfigError(f"{path}: {where}.source_gate_ids contains duplicates")

        if method in ("measured", "inferred"):
            for key in ("k1", "k2"):
                value = gate.get(key)
                valid = _is_finite_number(value) and (
                    value > 0 if key == "k1" else value < 0
                )
                if not valid:
                    raise ConfigError(
                        f"{path}: {where}.{key} must be a finite"
                        f" {'positive' if key == 'k1' else 'negative'} number,"
                        f" got {value!r}"
                    )
        elif "k1" in gate or "k2" in gate:
            raise ConfigError(
                f"{path}: {where}: default calibrations must not carry k1/k2"
            )

        normalized_gate_id = normalize_gate_id(gate_id)
        if method == "measured" and normalized_sources != [normalized_gate_id]:
            raise ConfigError(
                f"{path}: {where}.source_gate_ids must contain only the measured"
                " gate itself"
            )
        if method == "default" and normalized_sources:
            raise ConfigError(
                f"{path}: {where}.source_gate_ids must be empty for defaults"
            )
        if method in ("measured", "default") and source_version != source_sha256:
            raise ConfigError(
                f"{path}: {where}.source_version must match metadata.source_sha256"
                f" for {method} records, got {source_version!r}"
            )
        if method == "inferred":
            if not normalized_sources:
                raise ConfigError(
                    f"{path}: {where}.source_gate_ids must identify measured sources"
                )
            non_measured_sources = [
                normalized_ids[source]
                for source in normalized_sources
                if gates[normalized_ids[source]].get("calibration_method") != "measured"
            ]
            if non_measured_sources:
                raise ConfigError(
                    f"{path}: {where}.source_gate_ids must reference measured gates,"
                    f" got {non_measured_sources!r}"
                )
            expected_source_version = f"similar-gate-v1:{source_sha256}"
            if source_version != expected_source_version:
                raise ConfigError(
                    f"{path}: {where}.source_version must be"
                    f" {expected_source_version!r}, got {source_version!r}"
                )
            source_confidences = [
                gates[normalized_ids[source]]["confidence"]
                for source in normalized_sources
            ]
            if confidence >= min(source_confidences):
                raise ConfigError(
                    f"{path}: {where}.confidence must be lower than every measured"
                    f" source, got {confidence!r} versus {source_confidences!r}"
                )
            # An inferred coefficient is a confidence-weighted blend of its measured
            # donors, so each MUST lie within that donor set's [min, max] range for
            # that coefficient. This per-axis range check (an axis-aligned bounding
            # box on k1 and k2 independently, not a 2-D convex hull) rejects
            # out-of-range values (e.g. k1=100, k2=-100) the old sign-only check let
            # through. _RANGE_TOL absorbs 6-decimal generator rounding without
            # admitting a materially out-of-range coefficient.
            for key in ("k1", "k2"):
                source_values = [
                    gates[normalized_ids[source]][key] for source in normalized_sources
                ]
                low, high = min(source_values), max(source_values)
                if not (low - _RANGE_TOL <= gate[key] <= high + _RANGE_TOL):
                    raise ConfigError(
                        f"{path}: {where}.{key} must lie within its measured donors'"
                        f" [{low}, {high}] range, got {gate[key]!r}"
                    )
    _check_drift(
        _declared_count(metadata, "total_gates", path, "metadata"),
        len(gates),
        path,
        "total_gates",
    )
    declared_methods = _require_dict(metadata, "gates_by_calibration_method", path)
    if set(declared_methods) != set(methods):
        raise ConfigError(
            f"{path}: metadata.gates_by_calibration_method must contain exactly"
            f" {methods}, got {tuple(declared_methods)}"
        )
    for method, count in method_counts.items():
        _check_drift(
            _declared_count(
                declared_methods, method, path, "metadata.gates_by_calibration_method"
            ),
            count,
            path,
            f"gates_by_calibration_method.{method}",
        )
    return data


def load_zone_topology_config(path: str) -> dict:
    """Load the approved outlet/canal/zone topology."""
    data = load_strict_json_object(path)
    metadata = _require_dict(data, "metadata", path)
    source = metadata.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ConfigError(
            f"{path}: metadata.source must be a non-empty string, got {source!r}"
        )
    total_zones = _declared_count(metadata, "total_zones", path, "metadata")
    if total_zones <= 0:
        raise ConfigError(f"{path}: metadata.total_zones must be > 0")
    outlet_gate_id = metadata.get("outlet_gate_id")
    if not isinstance(outlet_gate_id, str):
        raise ConfigError(f"{path}: metadata.outlet_gate_id must be a gate-id string")
    try:
        normalized_outlet = normalize_gate_id(outlet_gate_id)
    except NodeIdError as exc:
        raise ConfigError(f"{path}: invalid outlet gate id: {exc}") from exc
    if outlet_gate_id != normalized_outlet:
        raise ConfigError(
            f"{path}: metadata.outlet_gate_id must use canonical id {normalized_outlet!r}"
        )

    canals = _require_dict(data, "canals", path)
    if not canals:
        raise ConfigError(f"{path}: canals must not be empty")
    canal_zones = {}
    for canal, record in canals.items():
        if not isinstance(canal, str) or not canal:
            raise ConfigError(f"{path}: canal names must be non-empty strings")
        if not isinstance(record, dict) or not isinstance(record.get("zones"), list):
            raise ConfigError(f"{path}: canals[{canal!r}].zones must be an array")
        zones_for_canal = record["zones"]
        if any(
            isinstance(zone, bool) or not isinstance(zone, int)
            for zone in zones_for_canal
        ):
            raise ConfigError(f"{path}: canals[{canal!r}].zones must contain integers")
        if len(set(zones_for_canal)) != len(zones_for_canal):
            raise ConfigError(f"{path}: canals[{canal!r}].zones contains duplicates")
        canal_zones[canal] = set(zones_for_canal)

    zones = data.get("zones")
    if not isinstance(zones, list):
        raise ConfigError(f"{path}: zones must be an array")
    if len(zones) != total_zones:
        raise ConfigError(
            f"{path}: zones count {len(zones)} does not match metadata.total_zones"
        )
    by_zone = {}
    entrance_ids = set()
    for index, record in enumerate(zones):
        where = f"zones[{index}]"
        if not isinstance(record, dict):
            raise ConfigError(f"{path}: {where} must be an object")
        zone = record.get("zone")
        if isinstance(zone, bool) or not isinstance(zone, int):
            raise ConfigError(f"{path}: {where}.zone must be an integer")
        if zone in by_zone:
            raise ConfigError(f"{path}: zones contains duplicate zone {zone}")
        canal = record.get("canal")
        if canal not in canals:
            raise ConfigError(f"{path}: {where}.canal names unknown canal {canal!r}")
        entrance_gate_id = record.get("entrance_gate_id")
        if not isinstance(entrance_gate_id, str):
            raise ConfigError(f"{path}: {where}.entrance_gate_id must be a string")
        try:
            normalized = normalize_gate_id(entrance_gate_id)
        except NodeIdError as exc:
            raise ConfigError(
                f"{path}: {where}.entrance_gate_id is invalid: {exc}"
            ) from exc
        if entrance_gate_id != normalized:
            raise ConfigError(
                f"{path}: {where}.entrance_gate_id must use canonical id {normalized!r}"
            )
        if normalized in entrance_ids:
            raise ConfigError(f"{path}: zone entrance gate ids must be unique")
        entrance_ids.add(normalized)
        parent = record.get("branches_from_zone")
        if parent is not None and (
            isinstance(parent, bool) or not isinstance(parent, int)
        ):
            raise ConfigError(
                f"{path}: {where}.branches_from_zone must be null or integer"
            )
        by_zone[zone] = record

    expected_zones = set(range(1, total_zones + 1))
    if set(by_zone) != expected_zones:
        raise ConfigError(
            f"{path}: zones must contain exactly {sorted(expected_zones)},"
            f" got {sorted(by_zone)}"
        )
    partition = [zone for members in canal_zones.values() for zone in members]
    if len(partition) != total_zones or set(partition) != expected_zones:
        raise ConfigError(
            f"{path}: canal zone partition must cover every zone exactly once"
        )
    for zone, record in by_zone.items():
        if zone not in canal_zones[record["canal"]]:
            raise ConfigError(
                f"{path}: zone {zone} disagrees with the canal zone partition"
            )
        parent = record["branches_from_zone"]
        if parent is not None and parent not in by_zone:
            raise ConfigError(
                f"{path}: zone {zone} references unknown parent zone {parent}"
            )

    for zone in by_zone:
        seen = set()
        current = zone
        while current is not None:
            if current in seen:
                raise ConfigError(f"{path}: branch cycle includes zone {current}")
            seen.add(current)
            current = by_zone[current]["branches_from_zone"]
    return data


def validate_routing_topology_artifact(
    path: str,
    artifact: dict,
    topology,
    source_file_sha256: dict[str, str],
) -> None:
    """The routing artifact must be the exact serialization of `topology`
    with truthful root/summary/lineage — shared by startup loading (against
    the re-derived topology) and the offline CLI (against the case topology).
    """
    from core.routing_topology import ROOT, routing_topology_payload

    expected_keys = {
        "metadata",
        "schema_version",
        "root_node_id",
        "lineage",
        "elements",
        "summary",
        "content_hash",
    }
    if set(artifact) != expected_keys:
        raise ConfigError(
            f"{path}: routing topology must have exactly the keys "
            f"{sorted(expected_keys)}, got {sorted(artifact)}"
        )
    for object_key in ("metadata", "lineage", "summary"):
        if not isinstance(artifact[object_key], dict):
            raise ConfigError(
                f"{path}: {object_key} must be a JSON object, "
                f"got {type(artifact[object_key]).__name__}"
            )
    if artifact["root_node_id"] != ROOT:
        raise ConfigError(
            f"{path}: root_node_id must be {ROOT!r}, "
            f"got {artifact['root_node_id']!r}"
        )

    declared_sources = artifact["lineage"].get("source_artifacts")
    if not isinstance(declared_sources, list) or len(declared_sources) != len(
        source_file_sha256
    ):
        raise ConfigError(
            f"{path}: lineage.source_artifacts must declare exactly "
            f"{sorted(source_file_sha256)}"
        )
    seen_sources = set()
    for source in declared_sources:
        if not isinstance(source, dict):
            raise ConfigError(
                f"{path}: lineage.source_artifacts entries must be JSON objects"
            )
        source_id = source.get("source_id")
        if source_id not in source_file_sha256 or source_id in seen_sources:
            raise ConfigError(
                f"{path}: lineage.source_artifacts must declare exactly "
                f"{sorted(source_file_sha256)} without duplicates"
            )
        seen_sources.add(source_id)
        if source.get("filename") != f"{source_id}.json":
            raise ConfigError(
                f"{path}: source artifact {source_id!r} filename must be "
                f"{source_id}.json"
            )
        if source.get("sha256") != source_file_sha256[source_id]:
            raise ConfigError(
                f"{path}: source artifact {source_id!r} bytes have drifted "
                "since generation — regenerate via "
                "scripts/build_scada_config.py"
            )

    if artifact["schema_version"] != topology.schema_version:
        raise ConfigError(
            f"{path}: schema_version {artifact['schema_version']!r} does not "
            f"match derivation schema_version {topology.schema_version!r}"
        )
    payload = routing_topology_payload(topology)
    if artifact["elements"] != payload["elements"]:
        raise ConfigError(
            f"{path}: elements disagree with the canonical derivation — "
            "regenerate via scripts/build_scada_config.py"
        )
    if artifact["content_hash"] != topology.content_hash:
        raise ConfigError(
            f"{path}: content_hash {artifact['content_hash']!r} does not match "
            f"derived content_hash {topology.content_hash!r}"
        )
    role_counts: dict[str, int] = {}
    for element in topology.elements:
        role_counts[element.role.value] = role_counts.get(element.role.value, 0) + 1
    expected_summary = {
        "total_nodes": len(
            {ROOT} | {element.downstream_node_id for element in topology.elements}
        ),
        "total_elements": len(topology.elements),
        "by_role": role_counts,
    }
    if artifact["summary"] != expected_summary:
        raise ConfigError(
            f"{path}: summary {artifact['summary']!r} does not match the "
            f"derived topology summary {expected_summary!r}"
        )
    if artifact["metadata"].get("source_sha256") != topology.source_sha256:
        raise ConfigError(
            f"{path}: metadata.source_sha256 does not match the canonical "
            "workbook hash"
        )


def load_routing_topology(
    path: str,
    network_path: str,
    geometry_coverage_path: str,
    canal_geometry_path: str,
):
    """The derived routing topology, verified against a fresh re-derivation.

    The committed artifact is an interchange copy only — the canonical
    network, geometry coverage, and canal geometry remain the source of
    truth. Any element, schema, root, summary, lineage, or hash disagreement
    with the in-process derivation is drift and fails startup.
    """
    from core.routing_topology import (
        RoutingTopologyError,
        derive_routing_topology,
    )

    artifact = load_strict_json_object(path)
    source_paths = {
        "network": network_path,
        "geometry_coverage": geometry_coverage_path,
        "canal_geometry": canal_geometry_path,
    }
    network = load_network_config(network_path)
    geometry_coverage = load_strict_json_object(geometry_coverage_path)
    canal_geometry = load_strict_json_object(canal_geometry_path)
    try:
        derived = derive_routing_topology(
            network, geometry_coverage, canal_geometry
        )
    except RoutingTopologyError as exc:
        raise ConfigError(
            f"{path}: canonical artifacts no longer yield the reviewed "
            f"routing derivation: {exc}"
        ) from exc

    validate_routing_topology_artifact(
        path,
        artifact,
        derived,
        {
            source_id: file_sha256(source_path)
            for source_id, source_path in source_paths.items()
        },
    )
    return derived
