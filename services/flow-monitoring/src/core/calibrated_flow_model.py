#!/usr/bin/env python3
"""
Calibrated Flow Model for Enhanced Gate Hydraulics
Handles rectangular and circular gates with drop structures
Based on SCADA Excel specifications
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import logging
from enum import Enum

from .gate_properties_enhanced import (
    GatePropertiesEnhanced, GateShape, FlowRegime,
    CalibrationCoefficients
)

logger = logging.getLogger(__name__)


@dataclass
class HydraulicConditions:
    """Water levels and gate opening conditions"""
    upstream_water_level_m: float
    downstream_water_level_m: float
    gate_opening_m: float
    temperature_c: float = 20.0  # For viscosity effects
    

@dataclass
class FlowCalculationResult:
    """Results from flow calculation"""
    flow_rate_m3s: float
    flow_regime: FlowRegime
    discharge_coefficient: float
    velocity_ms: float
    froude_number: float
    energy_loss_m: float
    confidence: float
    warnings: List[str]
    hydraulic_radius_m: Optional[float] = None
    critical_depth_m: Optional[float] = None
    

class CalibratedFlowModel:
    """Enhanced flow calculation model with calibration support"""
    
    def __init__(self):
        self.gravity = 9.81  # m/s²
        self.water_density = 1000  # kg/m³
        self.kinematic_viscosity = 1.004e-6  # m²/s at 20°C
        
    def calculate_discharge_coefficient(
        self,
        calibration: CalibrationCoefficients,
        gate: GatePropertiesEnhanced,
        opening_m: float
    ) -> float:
        """
        Calculate discharge coefficient using calibrated equation:
        Cs = K1 × (Hs/H1)^K2
        """
        if opening_m <= 0:
            return 0.0
            
        # For automatic gates at discrete levels, use exact opening
        if gate.is_automatic and gate.control_levels:
            opening_m = gate.control_levels.get_nearest_level(opening_m)
            
        # Opening ratio
        if gate.shape == GateShape.CIRCULAR:
            opening_ratio = opening_m / gate.diameter_m
        else:
            opening_ratio = opening_m / gate.height_m
            
        # Apply calibration equation
        Cs = calibration.k1 * (opening_ratio ** calibration.k2)
        
        # Physical limits
        Cs = np.clip(Cs, 0.3, 1.2)
        
        return Cs
        
    def determine_flow_regime(
        self,
        gate: GatePropertiesEnhanced,
        conditions: HydraulicConditions
    ) -> FlowRegime:
        """Determine flow regime including drop structure effects"""
        
        h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
        h_downstream = conditions.downstream_water_level_m - gate.sill_elevation_m
        
        # Check for no flow
        if h_upstream <= 0 or conditions.gate_opening_m <= 0:
            return FlowRegime.NO_FLOW
            
        # Check for weir flow (gate fully open and submerged)
        if gate.shape == GateShape.RECTANGULAR:
            if conditions.gate_opening_m >= gate.height_m and h_upstream > gate.height_m:
                return FlowRegime.WEIR_FLOW
                
        # Check for critical flow at drop structure
        if gate.has_drop_structure:
            # Calculate critical depth at drop
            Q_est = self._estimate_flow_rate(gate, conditions)
            if gate.shape == GateShape.CIRCULAR:
                # Approximate critical depth for circular section
                A_crit = (Q_est ** 2 / self.gravity) ** (1/3)
                h_crit = self._inverse_circular_area(gate.diameter_m, A_crit)
            else:
                h_crit = (Q_est ** 2 / (self.gravity * gate.width_m ** 2)) ** (1/3)
                
            # Check if drop creates critical flow
            drop_crest = gate.sill_elevation_m + gate.drop_height_m
            if h_downstream < drop_crest + h_crit * 0.8:  # 80% of critical depth
                return FlowRegime.CRITICAL_FLOW
                
        # Check for submerged flow
        if h_downstream > conditions.gate_opening_m * 0.67:  # Typical submergence threshold
            submergence_ratio = h_downstream / h_upstream
            if submergence_ratio > 0.8:
                return FlowRegime.SUBMERGED_FLOW
                
        return FlowRegime.FREE_FLOW
        
    def calculate_gate_flow(
        self,
        gate: GatePropertiesEnhanced,
        conditions: HydraulicConditions
    ) -> FlowCalculationResult:
        """Calculate flow through gate with enhanced hydraulics"""
        
        warnings = []
        
        # Validate inputs
        if not gate.calibration:
            warnings.append("No calibration data - using defaults")
            
        # For automatic gates, snap to discrete level
        actual_opening = conditions.gate_opening_m
        if gate.is_automatic and gate.control_levels:
            actual_opening = gate.control_levels.get_nearest_level(actual_opening)
            if abs(actual_opening - conditions.gate_opening_m) > 0.01:
                warnings.append(f"Snapped to discrete level: {actual_opening:.2f}m")
                
        # Update conditions with actual opening
        conditions = HydraulicConditions(
            upstream_water_level_m=conditions.upstream_water_level_m,
            downstream_water_level_m=conditions.downstream_water_level_m,
            gate_opening_m=actual_opening,
            temperature_c=conditions.temperature_c
        )
        
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
                confidence=gate.calibration.confidence if gate.calibration else 0.0,
                warnings=warnings
            )
            
        # Calculate flow based on regime
        if flow_regime == FlowRegime.CRITICAL_FLOW:
            result = self._calculate_critical_flow(gate, conditions)
        elif flow_regime == FlowRegime.WEIR_FLOW:
            result = self._calculate_weir_flow(gate, conditions)
        elif flow_regime == FlowRegime.SUBMERGED_FLOW:
            result = self._calculate_submerged_flow(gate, conditions)
        else:  # FREE_FLOW
            result = self._calculate_free_flow(gate, conditions)
            
        # Add warnings and confidence
        result.warnings.extend(warnings)
        result.confidence = gate.calibration.confidence if gate.calibration else 0.8
        
        return result
        
    def _calculate_free_flow(
        self,
        gate: GatePropertiesEnhanced,
        conditions: HydraulicConditions
    ) -> FlowCalculationResult:
        """Calculate free flow through gate"""
        
        h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
        opening = conditions.gate_opening_m
        
        # Get discharge coefficient
        Cs = self.calculate_discharge_coefficient(gate.calibration, gate, opening)
        
        # Calculate flow area and hydraulic parameters
        flow_area = gate.get_flow_area(opening)
        wetted_perimeter = gate.get_wetted_perimeter(opening)
        hydraulic_radius = flow_area / wetted_perimeter if wetted_perimeter > 0 else 0
        
        # Energy head for free flow
        energy_head = h_upstream - opening / 2
        
        # Calculate flow rate
        if energy_head > 0:
            # Modified equation for gate flow
            if gate.shape == GateShape.CIRCULAR:
                # Additional correction for circular gates
                shape_factor = 0.95  # Empirical factor for circular gates
                Q = shape_factor * Cs * flow_area * np.sqrt(2 * self.gravity * energy_head)
            else:
                Q = Cs * gate.width_m * opening * np.sqrt(2 * self.gravity * energy_head)
        else:
            Q = 0.0
            
        # Calculate velocity and Froude number
        velocity = Q / flow_area if flow_area > 0 else 0
        froude = velocity / np.sqrt(self.gravity * hydraulic_radius) if hydraulic_radius > 0 else 0
        
        # Energy loss
        energy_loss = (1 - Cs ** 2) * velocity ** 2 / (2 * self.gravity)
        
        return FlowCalculationResult(
            flow_rate_m3s=Q,
            flow_regime=FlowRegime.FREE_FLOW,
            discharge_coefficient=Cs,
            velocity_ms=velocity,
            froude_number=froude,
            energy_loss_m=energy_loss,
            confidence=0.0,  # Set by caller
            warnings=[],
            hydraulic_radius_m=hydraulic_radius
        )
        
    def _calculate_submerged_flow(
        self,
        gate: GatePropertiesEnhanced,
        conditions: HydraulicConditions
    ) -> FlowCalculationResult:
        """Calculate submerged flow with reduction factor"""
        
        # Start with free flow calculation
        result = self._calculate_free_flow(gate, conditions)
        
        # Apply submergence reduction
        h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
        h_downstream = conditions.downstream_water_level_m - gate.sill_elevation_m
        opening = conditions.gate_opening_m
        
        # Submergence ratio
        S = (h_downstream - opening) / (h_upstream - opening) if h_upstream > opening else 1.0
        S = np.clip(S, 0, 1)
        
        # Reduction factor (empirical formula)
        reduction_factor = np.sqrt(1 - S ** 2)
        reduction_factor = max(0.3, reduction_factor)  # Minimum 30% flow
        
        # Apply reduction
        result.flow_rate_m3s *= reduction_factor
        result.velocity_ms *= reduction_factor
        result.flow_regime = FlowRegime.SUBMERGED_FLOW
        result.warnings.append(f"Submerged flow - reduction factor: {reduction_factor:.2f}")
        
        return result
        
    def _calculate_critical_flow(
        self,
        gate: GatePropertiesEnhanced,
        conditions: HydraulicConditions
    ) -> FlowCalculationResult:
        """Calculate critical flow at drop structure"""
        
        h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
        opening = conditions.gate_opening_m
        
        # Get discharge coefficient
        Cs = self.calculate_discharge_coefficient(gate.calibration, gate, opening)
        
        # For critical flow at drop, use broad-crested weir equation
        # Q = Cd × L × H^(3/2) × √(2g/3)
        
        if gate.shape == GateShape.CIRCULAR:
            # Effective width for circular gate
            L_eff = gate.diameter_m * 0.9  # Empirical factor
        else:
            L_eff = gate.width_m
            
        # Critical flow coefficient (includes 2/3 factor)
        C_crit = Cs * np.sqrt(2 * self.gravity / 3) * (2/3)
        
        # Head over drop crest
        H = min(h_upstream, opening + h_upstream - opening/2)
        
        if H > 0:
            Q = C_crit * L_eff * (H ** 1.5)
        else:
            Q = 0.0
            
        # Critical depth
        if gate.shape == GateShape.CIRCULAR:
            h_crit = 0.7 * opening  # Approximation
        else:
            h_crit = (Q ** 2 / (self.gravity * L_eff ** 2)) ** (1/3) if Q > 0 else 0
            
        # Velocity at critical section
        flow_area = gate.get_flow_area(h_crit)
        velocity = Q / flow_area if flow_area > 0 else 0
        
        # Froude number (should be ~1 at critical)
        froude = 1.0
        
        # Energy loss through drop
        energy_loss = gate.drop_height_m + h_upstream - h_crit - velocity ** 2 / (2 * self.gravity)
        
        return FlowCalculationResult(
            flow_rate_m3s=Q,
            flow_regime=FlowRegime.CRITICAL_FLOW,
            discharge_coefficient=Cs,
            velocity_ms=velocity,
            froude_number=froude,
            energy_loss_m=max(0, energy_loss),
            confidence=0.0,  # Set by caller
            warnings=[f"Critical flow at drop: {gate.drop_height_m:.2f}m"],
            critical_depth_m=h_crit
        )
        
    def _calculate_weir_flow(
        self,
        gate: GatePropertiesEnhanced,
        conditions: HydraulicConditions
    ) -> FlowCalculationResult:
        """Calculate flow over top of gate (weir flow)"""
        
        h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
        gate_top = gate.height_m
        
        # Head over gate top
        H = h_upstream - gate_top
        
        if H <= 0:
            return FlowCalculationResult(
                flow_rate_m3s=0.0,
                flow_regime=FlowRegime.NO_FLOW,
                discharge_coefficient=0.0,
                velocity_ms=0.0,
                froude_number=0.0,
                energy_loss_m=0.0,
                confidence=0.0,
                warnings=["No flow over gate top"]
            )
            
        # Weir coefficient (depends on gate shape)
        if gate.shape == GateShape.RECTANGULAR:
            Cw = 0.62  # Sharp-crested weir
            L = gate.width_m
        else:
            Cw = 0.55  # Lower for non-standard shape
            L = gate.diameter_m
            
        # Standard weir equation
        Q = Cw * L * np.sqrt(2 * self.gravity) * (H ** 1.5)
        
        # Velocity over weir
        velocity = np.sqrt(2 * self.gravity * H)
        
        # Froude number
        froude = velocity / np.sqrt(self.gravity * H)
        
        return FlowCalculationResult(
            flow_rate_m3s=Q,
            flow_regime=FlowRegime.WEIR_FLOW,
            discharge_coefficient=Cw,
            velocity_ms=velocity,
            froude_number=froude,
            energy_loss_m=H * 0.1,  # Approximate energy loss
            confidence=0.0,  # Set by caller
            warnings=["Flow over gate top (weir flow)"]
        )
        
    def _estimate_flow_rate(
        self,
        gate: GatePropertiesEnhanced,
        conditions: HydraulicConditions
    ) -> float:
        """Quick flow estimate for iterative calculations"""
        
        h_upstream = conditions.upstream_water_level_m - gate.sill_elevation_m
        opening = conditions.gate_opening_m
        
        if h_upstream <= 0 or opening <= 0:
            return 0.0
            
        # Simple orifice equation
        area = gate.get_flow_area(opening)
        head = h_upstream - opening / 2
        
        if head > 0:
            return 0.6 * area * np.sqrt(2 * self.gravity * head)
        return 0.0
        
    def _inverse_circular_area(self, diameter: float, target_area: float) -> float:
        """Find height that gives target area for circular section"""
        
        # Newton-Raphson iteration
        R = diameter / 2
        h = diameter / 2  # Initial guess
        
        for _ in range(10):
            theta = 2 * np.arccos((R - h) / R)
            area = R**2 * (theta - np.sin(theta)) / 2
            
            if abs(area - target_area) < 0.001:
                break
                
            # Derivative
            dA_dh = 2 * R * np.sin(theta / 2)
            
            # Update
            h = h - (area - target_area) / dA_dh
            h = np.clip(h, 0, diameter)
            
        return h