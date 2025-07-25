#!/usr/bin/env python3
"""
Gate Opening Calculator
Calculates exact gate opening height (in meters) required for target flow
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from gate_hydraulics import GateProperties, HydraulicConditions, GateType

@dataclass
class GateOpeningResult:
    """Result of gate opening calculation"""
    required_opening_m: float
    opening_percent: float
    achievable_flow_m3s: float
    is_feasible: bool
    limiting_factor: Optional[str] = None
    recommendations: Optional[str] = None

class GateOpeningCalculator:
    """
    Calculates required gate opening height for target flow
    Using orifice equation: Q = Cd × b × a × √(2g × Δh)
    """
    
    def __init__(self):
        self.gravity = 9.81  # m/s²
        
    def calculate_required_opening(self, 
                                 target_flow: float,
                                 gate: GateProperties,
                                 upstream_level: float,
                                 downstream_level: float) -> GateOpeningResult:
        """
        Calculate gate opening height required for target flow
        
        Args:
            target_flow: Desired flow rate (m³/s)
            gate: Gate properties including dimensions
            upstream_level: Upstream water level (m MSL)
            downstream_level: Downstream water level (m MSL)
            
        Returns:
            GateOpeningResult with required opening and feasibility
        """
        
        # Calculate heads above sill
        h1 = upstream_level - gate.sill_elevation_m
        h2 = downstream_level - gate.sill_elevation_m
        
        # Check if water is above sill
        if h1 <= 0:
            return GateOpeningResult(
                required_opening_m=0,
                opening_percent=0,
                achievable_flow_m3s=0,
                is_feasible=False,
                limiting_factor="No water above gate sill",
                recommendations=f"Water level {upstream_level:.2f}m is below sill at {gate.sill_elevation_m:.2f}m"
            )
        
        # Determine flow regime
        submergence_ratio = h2 / h1 if h2 > 0 else 0
        is_submerged = submergence_ratio > 0.8  # For sluice gates
        
        if is_submerged:
            # Submerged flow - more complex calculation
            return self._calculate_submerged_opening(target_flow, gate, h1, h2)
        else:
            # Free flow - simpler calculation
            return self._calculate_free_flow_opening(target_flow, gate, h1)
    
    def _calculate_free_flow_opening(self, 
                                   target_flow: float,
                                   gate: GateProperties,
                                   upstream_head: float) -> GateOpeningResult:
        """
        Calculate opening for free flow condition
        Q = Cd × b × a × √(2g × h1)
        Therefore: a = Q / (Cd × b × √(2g × h1))
        """
        
        # Calculate denominator
        denominator = (gate.discharge_coefficient * 
                      gate.width_m * 
                      np.sqrt(2 * self.gravity * upstream_head))
        
        if denominator <= 0:
            return GateOpeningResult(
                required_opening_m=0,
                opening_percent=0,
                achievable_flow_m3s=0,
                is_feasible=False,
                limiting_factor="Invalid hydraulic conditions"
            )
        
        # Required opening height
        required_opening = target_flow / denominator
        
        # Apply contraction coefficient
        actual_opening = required_opening / gate.contraction_coefficient
        
        # Check feasibility
        if actual_opening > gate.max_opening_m:
            # Gate cannot open enough
            max_flow = self._calculate_max_flow(gate, upstream_head)
            
            return GateOpeningResult(
                required_opening_m=gate.max_opening_m,
                opening_percent=100.0,
                achievable_flow_m3s=max_flow,
                is_feasible=False,
                limiting_factor="Gate capacity exceeded",
                recommendations=f"Target flow {target_flow:.2f} m³/s exceeds max capacity {max_flow:.2f} m³/s. "
                              f"Consider: 1) Opening parallel gates, 2) Increasing upstream water level, "
                              f"3) Reducing target flow"
            )
        
        # Feasible opening
        opening_percent = (actual_opening / gate.max_opening_m) * 100
        
        return GateOpeningResult(
            required_opening_m=actual_opening,
            opening_percent=opening_percent,
            achievable_flow_m3s=target_flow,
            is_feasible=True,
            recommendations=f"Gate at {opening_percent:.1f}% opening ({actual_opening:.2f}m)"
        )
    
    def _calculate_submerged_opening(self,
                                   target_flow: float,
                                   gate: GateProperties,
                                   upstream_head: float,
                                   downstream_head: float) -> GateOpeningResult:
        """
        Calculate opening for submerged flow condition
        More complex - uses iterative approach
        """
        
        # Submerged flow coefficient (reduced from free flow)
        submergence_factor = self._calculate_submergence_factor(
            upstream_head, downstream_head, gate.gate_type
        )
        
        # Effective head for submerged condition
        effective_head = upstream_head - downstream_head
        
        # Modified discharge coefficient
        Cd_submerged = gate.discharge_coefficient * submergence_factor
        
        # Calculate required opening
        denominator = (Cd_submerged * 
                      gate.width_m * 
                      np.sqrt(2 * self.gravity * effective_head))
        
        if denominator <= 0:
            return GateOpeningResult(
                required_opening_m=0,
                opening_percent=0,
                achievable_flow_m3s=0,
                is_feasible=False,
                limiting_factor="Insufficient head difference for submerged flow"
            )
        
        required_opening = target_flow / denominator
        actual_opening = required_opening / gate.contraction_coefficient
        
        # Check feasibility
        if actual_opening > gate.max_opening_m:
            max_flow_submerged = (Cd_submerged * 
                                 gate.width_m * 
                                 gate.max_opening_m * 
                                 gate.contraction_coefficient *
                                 np.sqrt(2 * self.gravity * effective_head))
            
            return GateOpeningResult(
                required_opening_m=gate.max_opening_m,
                opening_percent=100.0,
                achievable_flow_m3s=max_flow_submerged,
                is_feasible=False,
                limiting_factor="Gate capacity exceeded in submerged condition",
                recommendations=f"Submerged flow limits capacity to {max_flow_submerged:.2f} m³/s. "
                              f"Consider: 1) Lowering downstream water level, "
                              f"2) Using multiple gates"
            )
        
        opening_percent = (actual_opening / gate.max_opening_m) * 100
        
        return GateOpeningResult(
            required_opening_m=actual_opening,
            opening_percent=opening_percent,
            achievable_flow_m3s=target_flow,
            is_feasible=True,
            recommendations=f"Submerged flow: Gate at {opening_percent:.1f}% ({actual_opening:.2f}m)"
        )
    
    def _calculate_submergence_factor(self, h1: float, h2: float, gate_type: GateType) -> float:
        """Calculate reduction factor for submerged flow"""
        
        submergence_ratio = h2 / h1 if h1 > 0 else 0
        
        # Empirical factors based on gate type
        if gate_type == GateType.SLUICE_GATE:
            # Sluice gate submergence curve
            if submergence_ratio < 0.8:
                return 1.0  # Still free flow
            elif submergence_ratio < 0.9:
                return 0.95
            elif submergence_ratio < 0.95:
                return 0.85
            else:
                return 0.7
        
        elif gate_type == GateType.RADIAL_GATE:
            # Radial gates handle submergence better
            if submergence_ratio < 0.75:
                return 1.0
            elif submergence_ratio < 0.85:
                return 0.98
            elif submergence_ratio < 0.95:
                return 0.90
            else:
                return 0.75
        
        else:  # VERTICAL_LIFT_GATE
            if submergence_ratio < 0.67:
                return 1.0
            elif submergence_ratio < 0.8:
                return 0.92
            elif submergence_ratio < 0.9:
                return 0.80
            else:
                return 0.65
    
    def _calculate_max_flow(self, gate: GateProperties, upstream_head: float) -> float:
        """Calculate maximum possible flow when gate fully open"""
        
        return (gate.discharge_coefficient * 
                gate.width_m * 
                gate.max_opening_m * 
                gate.contraction_coefficient *
                np.sqrt(2 * self.gravity * upstream_head))
    
    def calculate_gate_schedule(self,
                              gates_info: Dict[str, Dict],
                              water_levels: Dict[str, float]) -> Dict[str, GateOpeningResult]:
        """
        Calculate openings for multiple gates
        
        Args:
            gates_info: {gate_id: {'target_flow': float, 'properties': GateProperties}}
            water_levels: {node_id: water_level}
            
        Returns:
            {gate_id: GateOpeningResult}
        """
        
        results = {}
        
        for gate_id, info in gates_info.items():
            # Parse gate ID to get nodes
            parts = gate_id.split('->')
            if len(parts) != 2:
                continue
                
            upstream_node, downstream_node = parts
            
            # Get water levels
            upstream_level = water_levels.get(upstream_node, 0)
            downstream_level = water_levels.get(downstream_node, 0)
            
            # Calculate required opening
            result = self.calculate_required_opening(
                target_flow=info['target_flow'],
                gate=info['properties'],
                upstream_level=upstream_level,
                downstream_level=downstream_level
            )
            
            results[gate_id] = result
        
        return results


def demonstrate_gate_opening_calculation():
    """Demonstrate gate opening calculations"""
    
    print("=== GATE OPENING CALCULATOR DEMONSTRATION ===\n")
    
    calculator = GateOpeningCalculator()
    
    # Example gate properties
    gate = GateProperties(
        gate_id="Source->M(0,0)",
        gate_type=GateType.SLUICE_GATE,
        width_m=3.0,
        height_m=3.0,
        sill_elevation_m=218.0,
        discharge_coefficient=0.61,
        contraction_coefficient=0.9,
        max_opening_m=2.5
    )
    
    # Scenario 1: Free flow condition
    print("SCENARIO 1: Free Flow Condition")
    print("-" * 40)
    
    result = calculator.calculate_required_opening(
        target_flow=4.5,  # m³/s
        gate=gate,
        upstream_level=221.0,  # m MSL
        downstream_level=219.0  # m MSL
    )
    
    print(f"Target flow: 4.5 m³/s")
    print(f"Upstream level: 221.0 m")
    print(f"Downstream level: 219.0 m")
    print(f"Head difference: 2.0 m")
    print(f"\nRESULT:")
    print(f"Required opening: {result.required_opening_m:.3f} m")
    print(f"Opening percentage: {result.opening_percent:.1f}%")
    print(f"Feasible: {result.is_feasible}")
    if result.recommendations:
        print(f"Note: {result.recommendations}")
    
    # Scenario 2: Capacity exceeded
    print("\n\nSCENARIO 2: Capacity Exceeded")
    print("-" * 40)
    
    result = calculator.calculate_required_opening(
        target_flow=8.0,  # Too much!
        gate=gate,
        upstream_level=221.0,
        downstream_level=219.0
    )
    
    print(f"Target flow: 8.0 m³/s (high)")
    print(f"\nRESULT:")
    print(f"Required opening: {result.required_opening_m:.3f} m")
    print(f"Achievable flow: {result.achievable_flow_m3s:.2f} m³/s")
    print(f"Feasible: {result.is_feasible}")
    print(f"Limiting factor: {result.limiting_factor}")
    if result.recommendations:
        print(f"Recommendations: {result.recommendations}")
    
    # Scenario 3: Submerged flow
    print("\n\nSCENARIO 3: Submerged Flow")
    print("-" * 40)
    
    result = calculator.calculate_required_opening(
        target_flow=2.0,
        gate=gate,
        upstream_level=220.0,  # Lower upstream
        downstream_level=219.5  # High downstream (submerged)
    )
    
    print(f"Target flow: 2.0 m³/s")
    print(f"Upstream level: 220.0 m")
    print(f"Downstream level: 219.5 m")
    print(f"Submergence ratio: 75%")
    print(f"\nRESULT:")
    print(f"Required opening: {result.required_opening_m:.3f} m")
    print(f"Opening percentage: {result.opening_percent:.1f}%")
    print(f"Feasible: {result.is_feasible}")
    if result.recommendations:
        print(f"Note: {result.recommendations}")
    
    # Scenario 4: Multiple gates calculation
    print("\n\nSCENARIO 4: Multiple Gates Schedule")
    print("-" * 40)
    
    gates_info = {
        "Source->M(0,0)": {
            'target_flow': 4.5,
            'properties': gate
        },
        "M(0,0)->M(0,2)": {
            'target_flow': 4.5,
            'properties': GateProperties(
                gate_id="M(0,0)->M(0,2)",
                gate_type=GateType.SLUICE_GATE,
                width_m=3.0,
                height_m=2.5,
                sill_elevation_m=217.5,
                discharge_coefficient=0.61,
                contraction_coefficient=0.9,
                max_opening_m=2.0
            )
        }
    }
    
    water_levels = {
        'Source': 221.0,
        'M(0,0)': 219.2,
        'M(0,2)': 218.9
    }
    
    results = calculator.calculate_gate_schedule(gates_info, water_levels)
    
    print("\nGate Opening Schedule:")
    for gate_id, result in results.items():
        print(f"\n{gate_id}:")
        print(f"  Opening: {result.required_opening_m:.3f} m ({result.opening_percent:.1f}%)")
        print(f"  Flow: {result.achievable_flow_m3s:.2f} m³/s")
        print(f"  Status: {'OK' if result.is_feasible else 'LIMITED'}")


if __name__ == "__main__":
    demonstrate_gate_opening_calculation()