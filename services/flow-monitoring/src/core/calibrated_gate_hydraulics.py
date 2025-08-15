#!/usr/bin/env python3
"""
Calibrated Gate Hydraulics Module for Munbon Irrigation Network
Implements the calibrated equation: Q = Cs × L × Hs × √(2g × ΔH)
Where Cs = K1 × (Hs/Go)^K2
"""

import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class GateType(Enum):
    """Types of gates in the irrigation network"""
    SLUICE_GATE = "sluice_gate"
    RADIAL_GATE = "radial_gate" 
    BUTTERFLY_VALVE = "butterfly_valve"
    SLIDE_GATE = "slide_gate"
    CHECK_GATE = "check_gate"
    WEIR_GATE = "weir_gate"


class FlowRegime(Enum):
    """Flow conditions through gate"""
    FREE_FLOW = "free_flow"
    SUBMERGED_FLOW = "submerged_flow"
    CRITICAL_FLOW = "critical_flow"  # At drop structures
    NO_FLOW = "no_flow"


@dataclass
class GateCalibration:
    """Calibration coefficients for gate flow equation"""
    gate_id: str
    K1: float  # Base discharge coefficient
    K2: float  # Opening ratio exponent
    calibration_date: Optional[datetime] = None
    calibration_method: str = "field_measurement"
    flow_range_tested: Tuple[float, float] = (0.0, 0.0)
    confidence: float = 1.0  # 0-1 confidence in calibration
    notes: str = ""


@dataclass
class GateProperties:
    """Physical properties of a gate"""
    gate_id: str
    gate_type: GateType
    width_m: float  # L - Gate width
    height_m: float  # Go - Gate height when fully open
    sill_elevation_m: float  # Bottom elevation of gate opening
    has_drop_structure: bool = False
    drop_height_m: float = 0.0
    drop_type: str = "none"  # vertical, inclined, stepped
    max_opening_m: Optional[float] = None
    min_opening_m: float = 0.0
    
    def __post_init__(self):
        if self.max_opening_m is None:
            self.max_opening_m = self.height_m


@dataclass
class HydraulicConditions:
    """Water levels and gate opening for flow calculation"""
    upstream_water_level_m: float  # Absolute elevation
    downstream_water_level_m: float  # Absolute elevation
    gate_opening_m: float  # Hs - Current gate opening height
    timestamp: Optional[datetime] = None


@dataclass
class FlowCalculationResult:
    """Result of gate flow calculation"""
    flow_rate_m3s: float
    flow_regime: FlowRegime
    discharge_coefficient: float  # Cs
    velocity_ms: float
    froude_number: float
    energy_loss_m: float
    confidence: float
    warnings: List[str] = field(default_factory=list)


class CalibratedGateHydraulics:
    """
    Calculate flow through irrigation gates using calibrated equation:
    Q = Cs × L × Hs × √(2g × ΔH)
    Where Cs = K1 × (Hs/Go)^K2
    """
    
    def __init__(self):
        self.gravity = 9.81
        self.calibrations: Dict[str, GateCalibration] = {}
        self.gate_properties: Dict[str, GateProperties] = {}
        
        # Default calibration values by gate type (when no calibration available)
        self.default_calibrations = {
            GateType.SLUICE_GATE: GateCalibration("default", K1=0.61, K2=0.08, confidence=0.3),
            GateType.RADIAL_GATE: GateCalibration("default", K1=0.68, K2=0.10, confidence=0.3),
            GateType.BUTTERFLY_VALVE: GateCalibration("default", K1=0.60, K2=0.12, confidence=0.3),
            GateType.SLIDE_GATE: GateCalibration("default", K1=0.60, K2=0.09, confidence=0.3),
            GateType.CHECK_GATE: GateCalibration("default", K1=0.58, K2=0.07, confidence=0.3),
            GateType.WEIR_GATE: GateCalibration("default", K1=0.62, K2=0.05, confidence=0.3),
        }
    
    def add_gate_calibration(self, calibration: GateCalibration):
        """Add calibration data for a specific gate"""
        self.calibrations[calibration.gate_id] = calibration
        logger.info(f"Added calibration for gate {calibration.gate_id}: K1={calibration.K1}, K2={calibration.K2}")
    
    def add_gate_properties(self, properties: GateProperties):
        """Add physical properties for a gate"""
        self.gate_properties[properties.gate_id] = properties
        logger.info(f"Added properties for gate {properties.gate_id}: {properties.gate_type.value}, {properties.width_m}m wide")
    
    def estimate_calibration_from_similar(self, gate_id: str, similar_gates: List[str]) -> Optional[GateCalibration]:
        """Estimate calibration based on similar calibrated gates"""
        if not similar_gates:
            return None
        
        # Get calibrations for similar gates
        similar_calibrations = []
        for similar_id in similar_gates:
            if similar_id in self.calibrations:
                similar_calibrations.append(self.calibrations[similar_id])
        
        if not similar_calibrations:
            return None
        
        # Calculate weighted average based on confidence
        total_weight = sum(cal.confidence for cal in similar_calibrations)
        if total_weight == 0:
            return None
        
        avg_k1 = sum(cal.K1 * cal.confidence for cal in similar_calibrations) / total_weight
        avg_k2 = sum(cal.K2 * cal.confidence for cal in similar_calibrations) / total_weight
        avg_confidence = np.mean([cal.confidence for cal in similar_calibrations]) * 0.7  # Reduce confidence
        
        return GateCalibration(
            gate_id=gate_id,
            K1=avg_k1,
            K2=avg_k2,
            calibration_method="similar_gates_estimation",
            confidence=avg_confidence,
            notes=f"Estimated from gates: {', '.join(similar_gates)}"
        )
    
    def get_calibration(self, gate_id: str, gate_type: Optional[GateType] = None) -> GateCalibration:
        """Get calibration for a gate, using estimation if needed"""
        # Check if we have specific calibration
        if gate_id in self.calibrations:
            return self.calibrations[gate_id]
        
        # Try to find similar gates for estimation
        if gate_id in self.gate_properties:
            gate_prop = self.gate_properties[gate_id]
            similar_gates = self._find_similar_gates(gate_prop)
            estimated = self.estimate_calibration_from_similar(gate_id, similar_gates)
            if estimated:
                logger.info(f"Using estimated calibration for gate {gate_id} with confidence {estimated.confidence:.2f}")
                return estimated
        
        # Fall back to default for gate type
        if gate_type or (gate_id in self.gate_properties):
            gt = gate_type or self.gate_properties[gate_id].gate_type
            default = self.default_calibrations.get(gt)
            if default:
                logger.warning(f"Using default calibration for gate {gate_id} of type {gt.value}")
                return GateCalibration(
                    gate_id=gate_id,
                    K1=default.K1,
                    K2=default.K2,
                    calibration_method="default_by_type",
                    confidence=default.confidence,
                    notes=f"Default values for {gt.value}"
                )
        
        # Last resort - generic default
        logger.warning(f"No calibration found for gate {gate_id}, using generic default")
        return GateCalibration(gate_id=gate_id, K1=0.61, K2=0.08, confidence=0.1, calibration_method="generic_default")
    
    def _find_similar_gates(self, gate: GateProperties, max_similar: int = 3) -> List[str]:
        """Find similar gates based on type, size, and location"""
        if not self.gate_properties:
            return []
        
        similarities = []
        
        for other_id, other in self.gate_properties.items():
            if other_id == gate.gate_id or other_id not in self.calibrations:
                continue
            
            # Calculate similarity score
            score = 0.0
            
            # Gate type match (highest weight)
            if other.gate_type == gate.gate_type:
                score += 0.5
            
            # Size similarity
            width_ratio = min(gate.width_m, other.width_m) / max(gate.width_m, other.width_m)
            height_ratio = min(gate.height_m, other.height_m) / max(gate.height_m, other.height_m)
            score += 0.3 * (width_ratio + height_ratio) / 2
            
            # Drop structure similarity
            if gate.has_drop_structure == other.has_drop_structure:
                score += 0.2
            
            similarities.append((other_id, score))
        
        # Sort by similarity score and return top matches
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [gate_id for gate_id, score in similarities[:max_similar] if score > 0.5]
    
    def calculate_discharge_coefficient(self, calibration: GateCalibration, gate: GateProperties, 
                                      opening_m: float) -> float:
        """
        Calculate discharge coefficient Cs using calibrated equation:
        Cs = K1 × (Hs/Go)^K2
        """
        if gate.height_m <= 0:
            return calibration.K1
        
        opening_ratio = min(opening_m / gate.height_m, 1.0)
        Cs = calibration.K1 * (opening_ratio ** calibration.K2)
        
        # Bound Cs to reasonable range
        return np.clip(Cs, 0.3, 0.85)
    
    def determine_flow_regime(self, gate: GateProperties, conditions: HydraulicConditions) -> FlowRegime:
        """Determine flow regime including drop structure effects"""
        # Calculate heads relative to sill
        h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
        h_downstream = conditions.downstream_water_level_m - gate.sill_elevation_m
        
        # Check for no flow conditions
        if h_upstream <= 0 or conditions.gate_opening_m <= 0:
            return FlowRegime.NO_FLOW
        
        # Check for critical flow at drop structure
        if gate.has_drop_structure and gate.drop_height_m > 0:
            # Drop structures typically create critical flow
            critical_depth = (conditions.gate_opening_m * 2 / 3)  # Simplified
            if h_downstream < gate.sill_elevation_m - gate.drop_height_m + critical_depth:
                return FlowRegime.CRITICAL_FLOW
        
        # Calculate submergence ratio
        if h_downstream > conditions.gate_opening_m:
            # Gate is submerged
            submergence_ratio = h_downstream / h_upstream
            if submergence_ratio > 0.8:  # Typical threshold
                return FlowRegime.SUBMERGED_FLOW
        
        return FlowRegime.FREE_FLOW
    
    def calculate_gate_flow(self, gate_id: str, conditions: HydraulicConditions) -> FlowCalculationResult:
        """
        Calculate flow through gate using calibrated equation:
        Q = Cs × L × Hs × √(2g × ΔH)
        """
        warnings = []
        
        # Get gate properties
        if gate_id not in self.gate_properties:
            warnings.append(f"Gate {gate_id} properties not found")
            return FlowCalculationResult(
                flow_rate_m3s=0.0,
                flow_regime=FlowRegime.NO_FLOW,
                discharge_coefficient=0.0,
                velocity_ms=0.0,
                froude_number=0.0,
                energy_loss_m=0.0,
                confidence=0.0,
                warnings=warnings
            )
        
        gate = self.gate_properties[gate_id]
        
        # Get calibration
        calibration = self.get_calibration(gate_id, gate.gate_type)
        
        # Determine flow regime
        flow_regime = self.determine_flow_regime(gate, conditions)
        
        if flow_regime == FlowRegime.NO_FLOW:
            return FlowCalculationResult(
                flow_rate_m3s=0.0,
                flow_regime=flow_regime,
                discharge_coefficient=0.0,
                velocity_ms=0.0,
                froude_number=0.0,
                energy_loss_m=0.0,
                confidence=calibration.confidence,
                warnings=warnings
            )
        
        # Calculate parameters
        L = gate.width_m  # Gate width
        Hs = min(conditions.gate_opening_m, gate.max_opening_m)  # Gate opening
        
        # Calculate head difference
        if gate.has_drop_structure and flow_regime == FlowRegime.CRITICAL_FLOW:
            # Use critical flow equation for drop structures
            ΔH = conditions.upstream_water_level_m - gate.sill_elevation_m
            Cs = self.calculate_discharge_coefficient(calibration, gate, Hs)
            
            # Modified equation for critical flow
            Q = (2/3) * Cs * L * np.sqrt(2 * self.gravity) * (ΔH ** 1.5)
            
        else:
            # Standard gate equation
            h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
            h_downstream = conditions.downstream_water_level_m - gate.sill_elevation_m
            
            if flow_regime == FlowRegime.FREE_FLOW:
                ΔH = h_upstream - Hs/2  # Energy head for free flow
            else:  # SUBMERGED_FLOW
                ΔH = h_upstream - h_downstream
                # Apply submergence reduction factor
                submergence_factor = 1 - ((h_downstream - Hs) / (h_upstream - Hs)) ** 2
                submergence_factor = max(0.3, submergence_factor)
                warnings.append(f"Submerged flow detected, reduction factor: {submergence_factor:.2f}")
            
            # Calculate discharge coefficient
            Cs = self.calculate_discharge_coefficient(calibration, gate, Hs)
            
            # Apply calibrated equation
            if ΔH > 0:
                Q = Cs * L * Hs * np.sqrt(2 * self.gravity * ΔH)
                if flow_regime == FlowRegime.SUBMERGED_FLOW:
                    Q *= submergence_factor
            else:
                Q = 0.0
                warnings.append("Negative or zero head difference")
        
        # Calculate velocity and Froude number
        flow_area = L * Hs
        velocity = Q / flow_area if flow_area > 0 else 0.0
        
        # Froude number
        hydraulic_depth = Hs
        froude = velocity / np.sqrt(self.gravity * hydraulic_depth) if hydraulic_depth > 0 else 0.0
        
        # Energy loss calculation
        if velocity > 0:
            velocity_head = velocity ** 2 / (2 * self.gravity)
            if gate.has_drop_structure:
                energy_loss = gate.drop_height_m + 0.5 * velocity_head  # Simplified
            else:
                energy_loss = 0.1 * velocity_head  # Minor loss coefficient
        else:
            energy_loss = 0.0
        
        # Adjust confidence based on flow conditions
        confidence = calibration.confidence
        if flow_regime == FlowRegime.SUBMERGED_FLOW:
            confidence *= 0.8  # Less confident in submerged conditions
        if gate.has_drop_structure:
            confidence *= 0.9  # Slightly less confident with drop structures
        
        return FlowCalculationResult(
            flow_rate_m3s=Q,
            flow_regime=flow_regime,
            discharge_coefficient=Cs,
            velocity_ms=velocity,
            froude_number=froude,
            energy_loss_m=energy_loss,
            confidence=confidence,
            warnings=warnings
        )
    
    def validate_calibration(self, gate_id: str, measured_flows: List[Tuple[HydraulicConditions, float]]) -> Dict:
        """Validate calibration against measured flow data"""
        if not measured_flows:
            return {"error": "No measured flow data provided"}
        
        errors = []
        for conditions, measured_q in measured_flows:
            calculated = self.calculate_gate_flow(gate_id, conditions)
            error = abs(calculated.flow_rate_m3s - measured_q) / measured_q if measured_q > 0 else 0.0
            errors.append(error)
        
        return {
            "mean_error": np.mean(errors),
            "max_error": np.max(errors),
            "rmse": np.sqrt(np.mean([e**2 for e in errors])),
            "within_5_percent": sum(1 for e in errors if e < 0.05) / len(errors)
        }