"""Canonical-config orchestration for the static design-profile oracle."""

import math

from core.config_loader import (
    ConfigError,
    file_sha256,
    load_canal_geometry_config,
    load_gate_calibrations_config,
    load_network_config,
    load_zone_topology_config,
)
from core.design_profile import (
    DesignProfileError,
    TrapezoidSection,
    forecast_design_level_msl,
    infer_effective_bed_msl,
)
from core.node_id import normalize_node_id
from utils.gate_calibration_loader import GateCalibrationLoader


class DesignProfileService:
    def __init__(
        self,
        network_path: str,
        geometry_path: str,
        calibration_path: str,
        topology_path: str,
    ) -> None:
        network = load_network_config(network_path)
        geometry = load_canal_geometry_config(geometry_path)
        calibrations = load_gate_calibrations_config(calibration_path)
        topology = load_zone_topology_config(topology_path)
        network_gates = set(network["gates"])
        calibration_gates = set(calibrations["gates"])
        if calibration_gates != network_gates:
            raise ConfigError(
                f"{calibration_path}: calibration gate set must match network;"
                f" missing={sorted(network_gates - calibration_gates)},"
                f" extra={sorted(calibration_gates - network_gates)}"
            )
        topology_gates = {
            topology["metadata"]["outlet_gate_id"],
            *(record["entrance_gate_id"] for record in topology["zones"]),
        }
        unknown_gates = topology_gates - network_gates
        if unknown_gates:
            raise ConfigError(
                f"{topology_path}: topology gates absent from network: {sorted(unknown_gates)}"
            )

        self.topology = topology
        self.calibration_loader = GateCalibrationLoader(calibration_path)
        self.calibration_metadata = calibrations["metadata"]
        self.parent_by_gate: dict[str, str] = {}
        self.children_by_gate: dict[str, list[str]] = {}
        for parent, child in network["edges"]:
            normalized_parent = normalize_node_id(parent)
            normalized_child = normalize_node_id(child)
            self.parent_by_gate[normalized_child] = normalized_parent
            self.children_by_gate.setdefault(normalized_parent, []).append(
                normalized_child
            )
        self.sections_by_edge: dict[tuple[str, str], list[dict]] = {}
        for record in geometry["canal_sections"]:
            edge = (
                normalize_node_id(record["from_node"]),
                normalize_node_id(record["to_node"]),
            )
            self.sections_by_edge.setdefault(edge, []).append(record)
        self.config_sha256 = {
            "network": file_sha256(network_path),
            "canal_geometry": file_sha256(geometry_path),
            "gate_calibrations": file_sha256(calibration_path),
            "zone_topology": file_sha256(topology_path),
        }

    def calculate(self, zones: list[int], flow_fraction: float) -> dict:
        if (
            isinstance(flow_fraction, bool)
            or not isinstance(flow_fraction, (int, float))
            or not math.isfinite(flow_fraction)
            or flow_fraction < 0.0
        ):
            raise DesignProfileError("flow_fraction must be a finite number >= 0")
        available_zones = {record["zone"] for record in self.topology["zones"]}
        if (
            not zones
            or any(
                isinstance(zone, bool) or not isinstance(zone, int) for zone in zones
            )
            or len(set(zones)) != len(zones)
            or not set(zones).issubset(available_zones)
        ):
            raise DesignProfileError("zones must be unique configured zone numbers")
        selected = [
            self._calculate_zone(record, float(flow_fraction))
            for record in self.topology["zones"]
            if record["zone"] in set(zones)
        ]
        return {
            "mode": "design_profile",
            "flow_fraction": float(flow_fraction),
            "open_loop": True,
            "actual_state_known": False,
            "commandable": False,
            "outlet_gate_id": self.topology["metadata"]["outlet_gate_id"],
            "canals": {
                canal: record["zones"]
                for canal, record in self.topology["canals"].items()
            },
            "source_workbook": self.calibration_metadata["source_workbook"],
            "source_sha256": self.calibration_metadata["source_sha256"],
            "config_sha256": self.config_sha256,
            "zones": selected,
        }

    def _calculate_zone(self, topology: dict, flow_fraction: float) -> dict:
        gate_id = topology["entrance_gate_id"]
        calibration = self.calibration_loader.get_calibration(gate_id)
        design_flow_m3s = calibration.structure_max_flow_m3s
        binding_capacity_m3s = self.calibration_loader.rated_q_max(gate_id)
        result = {
            **topology,
            "status": "unavailable",
            "reason": None,
            "detail": None,
            "structure_data_status": calibration.structure_data_status,
            "calibration_method": calibration.calibration_method,
            "confidence": calibration.confidence,
            "design_fsl_reference_side": calibration.design_fsl_reference_side,
            "design_fsl_msl_m": calibration.design_fsl_msl_m,
            "sill_msl_m": calibration.sill_msl_m,
            "design_flow_m3s": design_flow_m3s,
            "binding_capacity_m3s": binding_capacity_m3s,
            "flow_m3s": None,
            "reference_upstream": None,
            "reference_downstream": None,
            "effective_bed_msl_m": None,
            "normal_depth_m": None,
            "forecast_level_msl_m": None,
        }
        if calibration.structure_data_status != "complete":
            result["reason"] = f"structure_data_{calibration.structure_data_status}"
            return result
        flow_m3s = design_flow_m3s * flow_fraction
        result["flow_m3s"] = flow_m3s
        if binding_capacity_m3s is None or flow_m3s > binding_capacity_m3s:
            result["status"] = "over_capacity"
            result["reason"] = "flow_exceeds_binding_capacity"
            return result
        reference = self._reference_section(gate_id)
        if reference is None:
            result["reason"] = "upstream_geometry_unavailable"
            return result
        edge, record = reference
        result["reference_upstream"], result["reference_downstream"] = edge
        geometry = record["geometry"]
        cross_section = geometry["cross_section"]
        hydraulic = geometry["hydraulic_params"]
        try:
            section = TrapezoidSection(
                bottom_width_m=cross_section["bottom_width_m"],
                side_slope=cross_section.get("side_slope", 0.0),
                manning_n=hydraulic["manning_n"],
                bed_slope=hydraulic["bed_slope"],
                max_depth_m=cross_section["depth_m"],
            )
            effective_bed_msl_m = infer_effective_bed_msl(
                calibration.design_fsl_msl_m,
                design_flow_m3s,
                section,
            )
            forecast_level_msl_m, normal_depth = forecast_design_level_msl(
                flow_m3s,
                effective_bed_msl_m,
                section,
            )
        except (DesignProfileError, KeyError) as exc:
            result["status"] = "incompatible"
            result["reason"] = "profile_incompatible"
            result["detail"] = str(exc)
            return result
        result.update(
            status="available",
            effective_bed_msl_m=effective_bed_msl_m,
            normal_depth_m=normal_depth,
            forecast_level_msl_m=forecast_level_msl_m,
        )
        return result

    def _reference_section(self, gate_id: str) -> tuple[tuple[str, str], dict] | None:
        parent = self.parent_by_gate.get(gate_id)
        if parent is None:
            return None
        direct_edge = (parent, gate_id)
        direct = self.sections_by_edge.get(direct_edge)
        if direct:
            return direct_edge, direct[-1]
        grandparent = self.parent_by_gate.get(parent)
        if grandparent is not None:
            upstream_edge = (grandparent, parent)
            upstream = self.sections_by_edge.get(upstream_edge)
            if upstream:
                return upstream_edge, upstream[-1]
        for child in self.children_by_gate.get(gate_id, []):
            downstream_edge = (gate_id, child)
            downstream = self.sections_by_edge.get(downstream_edge)
            if downstream:
                return downstream_edge, downstream[0]
        return None
