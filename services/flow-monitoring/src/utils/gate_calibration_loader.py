#!/usr/bin/env python3
"""
Gate Calibration Loader
Loads K1/K2 calibration values from the extracted SCADA data. Lookups join by
NORMALIZED gate id (core.node_id, Wave 1.2), so compact 'M(0,3;1,0)' and survey
'M (0,3; 1,0)' spellings resolve to the same stored calibration.
"""

import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

from core.config_loader import is_positive_finite, load_gate_calibrations_config
from core.gate_flow import (
    GateFlowCalibration,
    binding_flow_capacity,
    build_gate_flow_calibration,
)
from core.node_id import normalize_gate_id

logger = logging.getLogger(__name__)


@dataclass
class GateCalibrationData:
    """Gate calibration data"""

    gate_id: str
    k1: float
    k2: float
    calibration_method: str
    confidence: float
    source_gate_ids: Tuple[str, ...]
    source_version: str
    shape: Optional[str] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    design_fsl_msl_m: Optional[float] = None
    sill_msl_m: Optional[float] = None
    structure_max_flow_m3s: Optional[float] = None
    design_fsl_reference_side: Optional[str] = None
    structure_data_status: str = "unavailable"
    structure_role: str = "unknown"


class GateCalibrationLoader:
    """Loads and provides gate K1/K2 calibration values"""

    def __init__(self, calibration_file: Optional[str] = None):
        """Initialize with calibration file path"""
        if calibration_file is None:
            # Default path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            calibration_file = os.path.join(
                base_dir, "config", "gate_calibrations.json"
            )

        self.calibration_file = calibration_file
        self.calibrations = {}
        self._stored_by_normalized = {}
        self._load_calibrations()

    def _load_calibrations(self):
        """Load calibrations strictly (Wave 1.1): a missing, corrupt, or count-drifted
        file raises ConfigError — never fall back to silent generic defaults for
        every gate."""
        data = load_gate_calibrations_config(self.calibration_file)

        logger.info(f"Loaded calibrations for {data['metadata']['total_gates']} gates")
        logger.info(
            "Calibration methods: %s",
            data["metadata"]["gates_by_calibration_method"],
        )

        self.calibrations = data["gates"]
        self.intended_use = data["metadata"]["intended_use"]
        # Wave 1.2: full normalized -> stored-key index (replaces the old hardcoded
        # PARTIAL alias table, whose unmapped compact ids silently fell through to
        # generic defaults). The strict loader guarantees ids parse and don't collide.
        self._stored_by_normalized = {
            normalize_gate_id(stored_id): stored_id for stored_id in self.calibrations
        }

    def get_gate_data(self, gate_id: str) -> dict:
        """Raw stored record for a gate id in ANY spacing; ``{}`` when the gate is not
        in the file. Raises NodeIdError on a grammar-invalid id (fail-closed)."""
        stored_id = self._stored_by_normalized.get(normalize_gate_id(gate_id))
        return self.calibrations.get(stored_id, {}) if stored_id is not None else {}

    def rated_q_max(self, gate_id: str) -> Optional[float]:
        """Binding Sheet1/structure capacity, preserving both raw source fields."""
        gate_data = self.get_gate_data(gate_id)
        return binding_flow_capacity(
            gate_data.get("q_max_m3s"), gate_data.get("structure_max_flow_m3s")
        )

    def get_calibration(self, gate_id: str) -> Optional[GateCalibrationData]:
        """Calibration for a gate id in ANY spacing (compact or survey-spaced).

        Raises NodeIdError on a grammar-invalid id (fail-closed); a valid id absent
        from the file still gets the documented size-based/generic default ladder.
        """
        excel_id = self._stored_by_normalized.get(normalize_gate_id(gate_id))

        # Check if we have data for this gate
        if excel_id is not None:
            gate_data = self.calibrations[excel_id]

            method = gate_data["calibration_method"]
            if method in ("measured", "inferred"):
                return GateCalibrationData(
                    gate_id=gate_id,
                    k1=gate_data["k1"],
                    k2=gate_data["k2"],
                    calibration_method=method,
                    confidence=gate_data["confidence"],
                    source_gate_ids=tuple(gate_data["source_gate_ids"]),
                    source_version=gate_data["source_version"],
                    shape=gate_data.get("shape"),
                    width_m=gate_data.get("width_m"),
                    height_m=gate_data.get("height_m"),
                    design_fsl_msl_m=gate_data["design_fsl_msl_m"],
                    sill_msl_m=gate_data["sill_msl_m"],
                    structure_max_flow_m3s=gate_data["structure_max_flow_m3s"],
                    design_fsl_reference_side=gate_data["design_fsl_reference_side"],
                    structure_data_status=gate_data["structure_data_status"],
                    structure_role=gate_data["structure_role"],
                )
            return self._get_default_calibration(gate_id, gate_data)

        # No data at all, use generic defaults
        return self._get_generic_default(gate_id)

    def _get_default_calibration(
        self, gate_id: str, gate_data: dict
    ) -> GateCalibrationData:
        """Get default calibration based on gate size and shape"""
        shape = gate_data.get("shape", "rectangular")

        if shape == "circular":
            height = gate_data.get("height_m", 1.0)
            if height >= 1.0:
                k1, k2 = 1.40, -3.50  # Large circular
            elif height >= 0.6:
                k1, k2 = 1.30, -3.00  # Medium circular
            else:
                k1, k2 = 1.20, -2.50  # Small circular
        else:  # rectangular
            width = gate_data.get("width_m", 2.0)
            if width >= 3.0:
                k1, k2 = 1.20, -1.30  # Large rectangular
            elif width >= 1.5:
                k1, k2 = 1.10, -1.80  # Medium rectangular
            else:
                k1, k2 = 0.95, -2.00  # Small rectangular

        return GateCalibrationData(
            gate_id=gate_id,
            k1=k1,
            k2=k2,
            calibration_method="default",
            confidence=gate_data["confidence"],
            source_gate_ids=tuple(gate_data["source_gate_ids"]),
            source_version=gate_data["source_version"],
            shape=shape,
            width_m=gate_data.get("width_m"),
            height_m=gate_data.get("height_m"),
            design_fsl_msl_m=gate_data["design_fsl_msl_m"],
            sill_msl_m=gate_data["sill_msl_m"],
            structure_max_flow_m3s=gate_data["structure_max_flow_m3s"],
            design_fsl_reference_side=gate_data["design_fsl_reference_side"],
            structure_data_status=gate_data["structure_data_status"],
            structure_role=gate_data["structure_role"],
        )

    def _get_generic_default(self, gate_id: str) -> GateCalibrationData:
        """Get generic default calibration when no data available"""
        logger.warning(f"No calibration data for gate {gate_id}, using generic default")

        return GateCalibrationData(
            gate_id=gate_id,
            k1=1.10,
            k2=-1.80,
            calibration_method="default",
            confidence=0.60,
            source_gate_ids=(),
            source_version="runtime-default-v1",
        )

    def build_flow_calibration(
        self, gate_id: str, calibration: Optional[GateCalibrationData] = None
    ) -> GateFlowCalibration:
        """Assemble the GateFlowCalibration the flow law needs (F-01), from calibration +
        rated capacity + gate geometry.

        The SINGLE home for this assembly (C10) — HydraulicService and
        NetworkFlowController both call it, never a re-implementation. Pass an
        already-fetched GateCalibrationData to skip the re-lookup; otherwise it is fetched
        via the documented default ladder. Missing geometry falls back to a documented
        default AND lowers confidence inside build_gate_flow_calibration, so a gate on
        assumed geometry is visibly less trustworthy.
        """
        if calibration is None:
            calibration = self.get_calibration(gate_id)
        return build_gate_flow_calibration(
            k1=calibration.k1,
            k2=calibration.k2,
            confidence=calibration.confidence,
            q_max_m3s=self.rated_q_max(gate_id),
            width_m=calibration.width_m,
            sill_m=calibration.sill_msl_m,
            max_opening_m=self._max_opening_from_geometry(calibration),
            shape=calibration.shape,
        )

    @staticmethod
    def _max_opening_from_geometry(calibration: GateCalibrationData) -> Optional[float]:
        """Max vertical opening (m) from workbook geometry: a gate cannot open past its
        leaf height (rectangular) or diameter (circular, carried as height_m==width_m).
        Bounded off the DIMENSION, not the shape label, so a circular gate mis-recorded as
        shape=None is still bounded — keeping the flow law off the 2.0 m default that
        over-reports a small orifice (2.3-retro HIGH). Falls back to width_m when height_m
        is absent, and returns None only when no positive geometry is on record."""
        for opening_m in (calibration.height_m, calibration.width_m):
            if is_positive_finite(opening_m):
                return float(opening_m)
        return None

    def get_all_calibrated_gates(self) -> Dict[str, Tuple[float, float]]:
        """All measured/inferred gates, keyed by CANONICAL COMPACT id."""
        return {
            normalize_gate_id(excel_id): (gate_data["k1"], gate_data["k2"])
            for excel_id, gate_data in self.calibrations.items()
            if gate_data["calibration_method"] != "default"
        }

    def print_calibration_summary(self):
        """Print summary of calibrations"""
        print("\n=== Gate Calibration Summary ===")

        calibrated_gates = self.get_all_calibrated_gates()
        print(f"\nGates with measured/inferred K1/K2: {len(calibrated_gates)}")

        for gate_id, (k1, k2) in sorted(calibrated_gates.items()):
            print(f"  {gate_id}: K1={k1:.4f}, K2={k2:.4f}")

        print(f"\nTotal gates in system: {len(self.calibrations)}")
        print(f"Gates using defaults: {len(self.calibrations) - len(calibrated_gates)}")


# Example usage
if __name__ == "__main__":
    loader = GateCalibrationLoader()
    loader.print_calibration_summary()

    # Test Zone 6 gates
    print("\n=== Zone 6 Path Calibrations ===")
    zone6_gates = [
        "M(0,0)",
        "M(0,1)",
        "M(0,1;1,0)",
        "M(0,1;1,1)",
        "M(0,1;1,1;1,0)",
        "M(0,1;1,1;1,1)",
        "M(0,1;1,1;1,2)",
        "M(0,1;1,1;1,2;1,0)",
    ]

    for gate_id in zone6_gates:
        cal = loader.get_calibration(gate_id)
        if cal:
            print(
                f"{gate_id}: K1={cal.k1:.4f}, K2={cal.k2:.4f}"
                f" ({cal.calibration_method})"
            )
        else:
            print(f"{gate_id}: No calibration data")
