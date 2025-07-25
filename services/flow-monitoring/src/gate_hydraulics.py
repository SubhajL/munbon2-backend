#!/usr/bin/env python3
"""
Gate Hydraulics Module for Munbon Irrigation Network
Implements proper hydraulic calculations for different gate types
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

class GateType(Enum):
    """Types of gates in the irrigation network"""
    SLUICE_GATE = "sluice_gate"          # Vertical lift gate
    RADIAL_GATE = "radial_gate"          # Tainter gate
    BUTTERFLY_VALVE = "butterfly_valve"   # Rotating disc valve
    CHECK_GATE = "check_gate"            # One-way flow
    WEIR_GATE = "weir_gate"              # Overflow structure
    ORIFICE_GATE = "orifice_gate"        # Submerged opening

class FlowRegime(Enum):
    """Flow conditions through gate"""
    FREE_FLOW = "free_flow"              # Downstream level doesn't affect flow
    SUBMERGED_FLOW = "submerged_flow"    # Downstream level affects flow
    WEIR_FLOW = "weir_flow"              # Flow over top of gate

@dataclass
class GateProperties:
    """Physical properties of a gate"""
    gate_id: str
    gate_type: GateType
    width_m: float                       # Gate width (b)
    height_m: float                      # Gate height when fully open
    sill_elevation_m: float              # Bottom elevation of gate opening
    discharge_coefficient: float         # Cd - varies by gate type (0.6-0.85)
    contraction_coefficient: float       # Cc - for vena contracta (0.6-1.0)
    max_opening_m: float                 # Maximum gate opening
    min_opening_m: float = 0.0           # Minimum gate opening
    
@dataclass
class HydraulicConditions:
    """Water levels and gate opening"""
    upstream_water_level_m: float        # H1 - upstream water surface elevation
    downstream_water_level_m: float      # H2 - downstream water surface elevation
    gate_opening_m: float                # a - vertical gate opening
    
class GateHydraulics:
    """Calculate flow through irrigation gates with proper hydraulics"""
    
    def __init__(self):
        """Initialize with typical gate properties for Munbon network"""
        self.gravity = 9.81
        
        # Default discharge coefficients by gate type
        self.default_cd = {
            GateType.SLUICE_GATE: 0.61,
            GateType.RADIAL_GATE: 0.70,
            GateType.BUTTERFLY_VALVE: 0.65,
            GateType.CHECK_GATE: 0.60,
            GateType.WEIR_GATE: 0.62,
            GateType.ORIFICE_GATE: 0.61
        }
        
        # Contraction coefficients
        self.default_cc = {
            GateType.SLUICE_GATE: 0.61,      # Significant contraction
            GateType.RADIAL_GATE: 0.95,      # Less contraction
            GateType.BUTTERFLY_VALVE: 0.90,   # Moderate contraction
            GateType.CHECK_GATE: 0.98,        # Minimal contraction
            GateType.WEIR_GATE: 1.00,         # No contraction
            GateType.ORIFICE_GATE: 0.62       # Significant contraction
        }
        
    def determine_flow_regime(self, gate: GateProperties, conditions: HydraulicConditions) -> FlowRegime:
        """Determine if flow is free, submerged, or weir flow"""
        
        # Calculate heads
        h1 = conditions.upstream_water_level_m - gate.sill_elevation_m
        h2 = conditions.downstream_water_level_m - gate.sill_elevation_m
        a = conditions.gate_opening_m
        
        # Check for weir flow (gate fully open and flow over top)
        if a >= gate.height_m and h1 > gate.height_m:
            return FlowRegime.WEIR_FLOW
        
        # Submergence ratio
        if h2 > 0 and h1 > 0:
            submergence_ratio = h2 / h1
            
            # Threshold depends on gate type
            if gate.gate_type == GateType.SLUICE_GATE:
                threshold = 0.8
            elif gate.gate_type == GateType.RADIAL_GATE:
                threshold = 0.75
            else:
                threshold = 0.67
            
            if submergence_ratio > threshold:
                return FlowRegime.SUBMERGED_FLOW
        
        return FlowRegime.FREE_FLOW
    
    def calculate_sluice_gate_flow(self, gate: GateProperties, conditions: HydraulicConditions) -> float:
        """
        Calculate flow through a sluice gate
        Q = Cd * b * a * sqrt(2 * g * h)
        where h depends on flow regime
        """
        
        regime = self.determine_flow_regime(gate, conditions)
        
        # Effective gate opening (considering contraction)
        a_effective = conditions.gate_opening_m * gate.contraction_coefficient
        
        # Upstream head
        h1 = conditions.upstream_water_level_m - gate.sill_elevation_m
        
        if h1 <= 0:
            return 0.0
        
        if regime == FlowRegime.FREE_FLOW:
            # Free flow - use upstream head only
            # Q = Cd * b * a * sqrt(2 * g * h1)
            flow_rate = (gate.discharge_coefficient * 
                        gate.width_m * 
                        a_effective * 
                        np.sqrt(2 * self.gravity * h1))
            
        elif regime == FlowRegime.SUBMERGED_FLOW:
            # Submerged flow - use head difference
            h2 = conditions.downstream_water_level_m - gate.sill_elevation_m
            delta_h = h1 - h2
            
            if delta_h <= 0:
                return 0.0
            
            # Submerged flow equation with reduction factor
            submergence_ratio = h2 / h1
            reduction_factor = np.sqrt(1 - submergence_ratio**2)
            
            flow_rate = (gate.discharge_coefficient * 
                        gate.width_m * 
                        a_effective * 
                        np.sqrt(2 * self.gravity * h1) *
                        reduction_factor)
        else:
            # Weir flow
            flow_rate = self.calculate_weir_flow(gate, conditions)
        
        return flow_rate
    
    def calculate_radial_gate_flow(self, gate: GateProperties, conditions: HydraulicConditions) -> float:
        """
        Calculate flow through a radial (Tainter) gate
        Similar to sluice gate but with different coefficients
        """
        
        # Radial gates have less contraction
        # Use similar approach but with radial gate coefficients
        regime = self.determine_flow_regime(gate, conditions)
        
        # For radial gates, the opening is measured as chord length
        # Convert to vertical opening equivalent
        a_vertical = conditions.gate_opening_m
        
        h1 = conditions.upstream_water_level_m - gate.sill_elevation_m
        
        if h1 <= 0:
            return 0.0
        
        if regime == FlowRegime.FREE_FLOW:
            # Free flow with radial gate coefficient
            flow_rate = (gate.discharge_coefficient * 
                        gate.width_m * 
                        a_vertical * 
                        np.sqrt(2 * self.gravity * h1))
            
        elif regime == FlowRegime.SUBMERGED_FLOW:
            # Submerged flow
            h2 = conditions.downstream_water_level_m - gate.sill_elevation_m
            
            # Use energy equation for submerged radial gate
            y1 = h1  # Upstream depth
            y3 = h2  # Downstream depth
            
            # Momentum equation for gate
            flow_rate = (gate.discharge_coefficient * 
                        gate.width_m * 
                        a_vertical * 
                        np.sqrt(2 * self.gravity * (y1 - y3)))
        else:
            # Weir flow
            flow_rate = self.calculate_weir_flow(gate, conditions)
        
        return flow_rate
    
    def calculate_butterfly_valve_flow(self, gate: GateProperties, conditions: HydraulicConditions) -> float:
        """
        Calculate flow through a butterfly valve
        Q = Cd * A * sqrt(2 * g * delta_h)
        """
        
        # For butterfly valve, opening is an angle (0-90 degrees)
        # Convert gate_opening_m to opening ratio (0-1)
        opening_ratio = conditions.gate_opening_m / gate.max_opening_m
        
        # Opening angle in radians
        theta = opening_ratio * np.pi / 2  # 0 to 90 degrees
        
        # Flow area depends on valve angle
        # Approximate flow area for circular butterfly valve
        if gate.height_m == gate.width_m:  # Circular
            diameter = gate.width_m
            area_full = np.pi * (diameter / 2) ** 2
        else:  # Rectangular
            area_full = gate.width_m * gate.height_m
        
        # Area reduction factor based on butterfly valve characteristics
        if theta < 0.1:  # Nearly closed
            area_factor = 0.05 * (theta / 0.1)
        elif theta < np.pi / 4:  # 0-45 degrees
            area_factor = np.sin(2 * theta) * 0.7
        else:  # 45-90 degrees
            area_factor = 0.7 + 0.3 * (theta - np.pi/4) / (np.pi/4)
        
        effective_area = area_full * area_factor
        
        # Head difference
        h1 = conditions.upstream_water_level_m - gate.sill_elevation_m
        h2 = conditions.downstream_water_level_m - gate.sill_elevation_m
        delta_h = h1 - h2
        
        if delta_h <= 0:
            return 0.0
        
        # Modified discharge coefficient for butterfly valve
        cd_modified = gate.discharge_coefficient * (1 - 0.3 * (1 - area_factor))
        
        flow_rate = cd_modified * effective_area * np.sqrt(2 * self.gravity * delta_h)
        
        return flow_rate
    
    def calculate_weir_flow(self, gate: GateProperties, conditions: HydraulicConditions) -> float:
        """
        Calculate flow over gate acting as a weir
        Q = Cd * b * (2/3) * sqrt(2*g) * H^(3/2)
        """
        
        # Head over weir crest
        crest_elevation = gate.sill_elevation_m + gate.height_m
        H = conditions.upstream_water_level_m - crest_elevation
        
        if H <= 0:
            return 0.0
        
        # Check for submergence
        h2 = conditions.downstream_water_level_m - crest_elevation
        
        if h2 > 0:
            # Submerged weir - apply reduction
            submergence_ratio = h2 / H
            if submergence_ratio > 0.9:
                return 0.0  # Too submerged
            
            # Villemonte reduction factor
            reduction = np.sqrt(1 - (submergence_ratio)**3)
        else:
            reduction = 1.0
        
        # Rectangular weir equation
        flow_rate = (gate.discharge_coefficient * 
                    gate.width_m * 
                    (2.0/3.0) * 
                    np.sqrt(2 * self.gravity) * 
                    H**(3.0/2.0) * 
                    reduction)
        
        return flow_rate
    
    def calculate_orifice_flow(self, gate: GateProperties, conditions: HydraulicConditions) -> float:
        """
        Calculate flow through submerged orifice
        Q = Cd * A * sqrt(2 * g * h)
        """
        
        # Orifice area
        area = gate.width_m * conditions.gate_opening_m
        
        # Effective head (center of orifice)
        center_elevation = gate.sill_elevation_m + conditions.gate_opening_m / 2
        h = conditions.upstream_water_level_m - center_elevation
        
        if h <= 0:
            return 0.0
        
        # Check if truly submerged
        if conditions.downstream_water_level_m < (gate.sill_elevation_m + conditions.gate_opening_m):
            # Not fully submerged, use sluice gate equation
            return self.calculate_sluice_gate_flow(gate, conditions)
        
        # Submerged orifice flow
        flow_rate = gate.discharge_coefficient * area * np.sqrt(2 * self.gravity * h)
        
        return flow_rate
    
    def calculate_gate_flow(self, gate: GateProperties, conditions: HydraulicConditions) -> Dict:
        """
        Main method to calculate flow through any gate type
        Returns flow rate and additional hydraulic information
        """
        
        # Validate inputs
        if conditions.gate_opening_m <= 0:
            return {
                'flow_rate_m3s': 0.0,
                'flow_regime': 'closed',
                'velocity_ms': 0.0,
                'froude_number': 0.0
            }
        
        # Limit gate opening
        actual_opening = min(conditions.gate_opening_m, gate.max_opening_m)
        conditions.gate_opening_m = actual_opening
        
        # Calculate flow based on gate type
        if gate.gate_type == GateType.SLUICE_GATE:
            flow_rate = self.calculate_sluice_gate_flow(gate, conditions)
        elif gate.gate_type == GateType.RADIAL_GATE:
            flow_rate = self.calculate_radial_gate_flow(gate, conditions)
        elif gate.gate_type == GateType.BUTTERFLY_VALVE:
            flow_rate = self.calculate_butterfly_valve_flow(gate, conditions)
        elif gate.gate_type == GateType.ORIFICE_GATE:
            flow_rate = self.calculate_orifice_flow(gate, conditions)
        else:
            # Default to sluice gate equation
            flow_rate = self.calculate_sluice_gate_flow(gate, conditions)
        
        # Calculate velocity through gate
        flow_area = gate.width_m * actual_opening
        velocity = flow_rate / flow_area if flow_area > 0 else 0.0
        
        # Calculate Froude number
        hydraulic_depth = actual_opening
        froude = velocity / np.sqrt(self.gravity * hydraulic_depth) if hydraulic_depth > 0 else 0.0
        
        # Determine flow regime
        regime = self.determine_flow_regime(gate, conditions)
        
        return {
            'flow_rate_m3s': flow_rate,
            'flow_regime': regime.value,
            'velocity_ms': velocity,
            'froude_number': froude,
            'gate_opening_m': actual_opening,
            'gate_opening_percent': (actual_opening / gate.max_opening_m) * 100
        }
    
    def estimate_gate_properties(self, gate_id: str, q_max: float, 
                               gate_type: GateType = GateType.SLUICE_GATE) -> GateProperties:
        """
        Estimate gate properties from maximum flow capacity
        Used when detailed gate data is not available
        """
        
        # Handle invalid q_max
        if q_max is None or np.isnan(q_max) or q_max <= 0:
            q_max = 5.0  # Default flow capacity
        
        # Assume typical head for max flow (2-3 m)
        design_head = 2.5  # meters
        
        # Get discharge coefficient
        cd = self.default_cd.get(gate_type, 0.61)
        cc = self.default_cc.get(gate_type, 0.61)
        
        # For maximum flow, assume gate is 80% open
        opening_ratio = 0.8
        
        # Estimate gate dimensions from Q = Cd * b * a * sqrt(2*g*h)
        # Assume width = 2 * height for typical gate proportions
        # Q_max = Cd * (2*h) * (0.8*h) * sqrt(2*g*H)
        # Q_max = 1.6 * Cd * h^2 * sqrt(2*g*H)
        
        height_estimate = np.sqrt(q_max / (1.6 * cd * np.sqrt(2 * self.gravity * design_head)))
        width_estimate = 2 * height_estimate
        
        # Round to reasonable dimensions
        height = round(height_estimate * 2) / 2 if not np.isnan(height_estimate) else 1.0
        width = round(width_estimate * 2) / 2 if not np.isnan(width_estimate) else 2.0
        
        return GateProperties(
            gate_id=gate_id,
            gate_type=gate_type,
            width_m=width,
            height_m=height,
            sill_elevation_m=0.0,  # Relative to datum
            discharge_coefficient=cd,
            contraction_coefficient=cc,
            max_opening_m=height * opening_ratio
        )
    
    def calculate_required_opening(self, gate: GateProperties, 
                                 target_flow: float,
                                 conditions: HydraulicConditions,
                                 tolerance: float = 0.01) -> float:
        """
        Calculate required gate opening to achieve target flow
        Uses iterative approach
        """
        
        # Initial guess - linear approximation
        opening_guess = gate.max_opening_m * (target_flow / (gate.width_m * 3.0))
        opening_guess = min(opening_guess, gate.max_opening_m)
        
        # Iterate to find correct opening
        max_iterations = 20
        for i in range(max_iterations):
            conditions.gate_opening_m = opening_guess
            result = self.calculate_gate_flow(gate, conditions)
            flow = result['flow_rate_m3s']
            
            error = flow - target_flow
            if abs(error) < tolerance:
                return opening_guess
            
            # Adjust opening
            if flow > 0:
                adjustment = error / flow * opening_guess * 0.5
            else:
                adjustment = 0.1
            
            opening_guess = max(0, min(gate.max_opening_m, opening_guess - adjustment))
        
        return opening_guess


# Example usage and testing
if __name__ == "__main__":
    # Create hydraulics calculator
    hydraulics = GateHydraulics()
    
    # Example 1: Main outlet gate M(0,0) with Q_max = 11.2 m³/s
    main_gate = hydraulics.estimate_gate_properties("M(0,0)", q_max=11.2)
    print(f"Estimated main gate dimensions: {main_gate.width_m}m x {main_gate.height_m}m")
    
    # Test conditions
    conditions = HydraulicConditions(
        upstream_water_level_m=3.0,    # 3m above sill
        downstream_water_level_m=1.5,   # 1.5m above sill
        gate_opening_m=0.8             # 0.8m opening
    )
    
    # Calculate flow
    result = hydraulics.calculate_gate_flow(main_gate, conditions)
    print(f"\nFlow calculation results:")
    print(f"Flow rate: {result['flow_rate_m3s']:.2f} m³/s")
    print(f"Flow regime: {result['flow_regime']}")
    print(f"Velocity: {result['velocity_ms']:.2f} m/s")
    print(f"Gate opening: {result['gate_opening_percent']:.1f}%")
    
    # Example 2: Find required opening for target flow
    target_flow = 5.0  # m³/s
    required_opening = hydraulics.calculate_required_opening(
        main_gate, target_flow, conditions
    )
    print(f"\nTo achieve {target_flow} m³/s, gate opening needed: {required_opening:.3f} m")
    
    # Example 3: Different gate types
    print("\n\nComparing gate types for same conditions:")
    gate_types = [GateType.SLUICE_GATE, GateType.RADIAL_GATE, GateType.BUTTERFLY_VALVE]
    
    for gate_type in gate_types:
        gate = GateProperties(
            gate_id="test",
            gate_type=gate_type,
            width_m=2.0,
            height_m=1.5,
            sill_elevation_m=0.0,
            discharge_coefficient=hydraulics.default_cd[gate_type],
            contraction_coefficient=hydraulics.default_cc[gate_type],
            max_opening_m=1.2
        )
        
        result = hydraulics.calculate_gate_flow(gate, conditions)
        print(f"\n{gate_type.value}:")
        print(f"  Flow: {result['flow_rate_m3s']:.2f} m³/s")
        print(f"  Velocity: {result['velocity_ms']:.2f} m/s")