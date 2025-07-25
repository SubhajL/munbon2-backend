#!/usr/bin/env python3
"""
Calibrated Gate Flow Calculation
Uses the correct equation: Q = Cs × L × Hs × √(2g × ΔH)
Where Cs = K1 × (Hs/Go)^K2 from gate calibration
"""

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import json

@dataclass
class GateCalibration:
    """Gate calibration parameters"""
    gate_id: str
    K1: float  # Calibration coefficient
    K2: float  # Calibration exponent
    L: float   # Gate width (m)
    min_opening: float  # Minimum gate opening (m)
    max_opening: float  # Maximum gate opening (m)
    calibration_range: Dict[str, float]  # Valid range for Hs/Go ratio

@dataclass
class FlowCalculationResult:
    """Result of flow calculation"""
    flow_rate_m3s: float
    discharge_coefficient: float
    hs_go_ratio: float
    reynolds_number: Optional[float]
    is_within_calibration: bool
    warnings: list

class CalibratedGateFlow:
    """
    Calculates gate flow using calibrated discharge coefficients
    """
    
    def __init__(self):
        self.gravity = 9.81  # m/s²
        self.calibrations = self._load_calibrations()
        
    def _load_calibrations(self) -> Dict[str, GateCalibration]:
        """Load gate calibration data"""
        
        # Example calibration data for Munbon gates
        # In reality, this would come from calibration tests
        calibrations = {
            "Source->M(0,0)": GateCalibration(
                gate_id="Source->M(0,0)",
                K1=0.85,
                K2=-0.15,
                L=3.0,  # 3m wide gate
                min_opening=0.1,
                max_opening=2.5,
                calibration_range={"min": 0.2, "max": 2.0}
            ),
            "M(0,0)->M(0,2)": GateCalibration(
                gate_id="M(0,0)->M(0,2)",
                K1=0.82,
                K2=-0.12,
                L=3.0,
                min_opening=0.1,
                max_opening=2.5,
                calibration_range={"min": 0.2, "max": 2.0}
            ),
            "M(0,5)->Zone2": GateCalibration(
                gate_id="M(0,5)->Zone2",
                K1=0.78,
                K2=-0.18,
                L=2.5,  # Smaller gate
                min_opening=0.1,
                max_opening=2.0,
                calibration_range={"min": 0.15, "max": 2.5}
            )
        }
        
        return calibrations
    
    def calculate_discharge_coefficient(self, 
                                      Hs: float, 
                                      Go: float, 
                                      calibration: GateCalibration) -> Tuple[float, bool]:
        """
        Calculate discharge coefficient using calibration curve
        Cs = K1 × (Hs/Go)^K2
        
        Returns:
            Tuple of (Cs, is_within_calibration_range)
        """
        
        if Go <= 0:
            return 0.0, False
            
        # Calculate Hs/Go ratio
        hs_go_ratio = Hs / Go
        
        # Check if within calibration range
        is_within_range = (calibration.calibration_range["min"] <= hs_go_ratio <= 
                          calibration.calibration_range["max"])
        
        # Calculate Cs
        Cs = calibration.K1 * (hs_go_ratio ** calibration.K2)
        
        # Apply physical limits (Cs typically between 0.3 and 1.0)
        Cs = max(0.3, min(1.0, Cs))
        
        return Cs, is_within_range
    
    def calculate_flow(self,
                      gate_id: str,
                      upstream_level: float,
                      downstream_level: float,
                      gate_opening: float) -> FlowCalculationResult:
        """
        Calculate flow using: Q = Cs × L × Hs × √(2g × ΔH)
        
        Args:
            gate_id: Gate identifier
            upstream_level: Upstream water level (m)
            downstream_level: Downstream water level (m)
            gate_opening: Gate opening height Go (m)
            
        Returns:
            FlowCalculationResult with flow rate and diagnostics
        """
        
        warnings = []
        
        # Get calibration
        calibration = self.calibrations.get(gate_id)
        if not calibration:
            warnings.append(f"No calibration data for gate {gate_id}")
            # Use default
            calibration = GateCalibration(
                gate_id=gate_id,
                K1=0.8,
                K2=-0.15,
                L=3.0,
                min_opening=0.1,
                max_opening=2.5,
                calibration_range={"min": 0.1, "max": 3.0}
            )
        
        # Calculate hydraulic parameters
        Hs = downstream_level  # Downstream water level
        ΔH = upstream_level - downstream_level  # Head difference
        
        # Check physical conditions
        if ΔH <= 0:
            return FlowCalculationResult(
                flow_rate_m3s=0.0,
                discharge_coefficient=0.0,
                hs_go_ratio=0.0,
                reynolds_number=None,
                is_within_calibration=False,
                warnings=["No positive head difference - no flow possible"]
            )
        
        if Hs <= 0:
            return FlowCalculationResult(
                flow_rate_m3s=0.0,
                discharge_coefficient=0.0,
                hs_go_ratio=0.0,
                reynolds_number=None,
                is_within_calibration=False,
                warnings=["Downstream water level below gate - free flow condition not applicable"]
            )
        
        # Check gate opening limits
        if gate_opening < calibration.min_opening:
            warnings.append(f"Gate opening {gate_opening:.2f}m below minimum {calibration.min_opening:.2f}m")
            gate_opening = calibration.min_opening
        elif gate_opening > calibration.max_opening:
            warnings.append(f"Gate opening {gate_opening:.2f}m above maximum {calibration.max_opening:.2f}m")
            gate_opening = calibration.max_opening
        
        # Calculate discharge coefficient
        Cs, is_within_calibration = self.calculate_discharge_coefficient(Hs, gate_opening, calibration)
        
        if not is_within_calibration:
            warnings.append(f"Hs/Go ratio {Hs/gate_opening:.2f} outside calibration range "
                          f"[{calibration.calibration_range['min']:.1f}, "
                          f"{calibration.calibration_range['max']:.1f}]")
        
        # Calculate flow rate
        # Q = Cs × L × Hs × √(2g × ΔH)
        Q = Cs * calibration.L * Hs * np.sqrt(2 * self.gravity * ΔH)
        
        # Calculate Reynolds number (optional)
        # Assuming hydraulic diameter ≈ 4 × Hs × L / (2 × (Hs + L))
        hydraulic_diameter = 4 * Hs * calibration.L / (2 * (Hs + calibration.L))
        velocity = Q / (calibration.L * Hs)
        kinematic_viscosity = 1e-6  # m²/s for water at 20°C
        reynolds = velocity * hydraulic_diameter / kinematic_viscosity
        
        return FlowCalculationResult(
            flow_rate_m3s=Q,
            discharge_coefficient=Cs,
            hs_go_ratio=Hs/gate_opening,
            reynolds_number=reynolds,
            is_within_calibration=is_within_calibration,
            warnings=warnings
        )
    
    def calculate_required_opening(self,
                                 gate_id: str,
                                 target_flow: float,
                                 upstream_level: float,
                                 downstream_level: float) -> Dict:
        """
        Calculate required gate opening for target flow
        This requires iteration since Cs depends on Go
        """
        
        calibration = self.calibrations.get(gate_id)
        if not calibration:
            return {"error": f"No calibration for gate {gate_id}"}
        
        Hs = downstream_level
        ΔH = upstream_level - downstream_level
        L = calibration.L
        
        if ΔH <= 0 or Hs <= 0:
            return {"error": "Invalid hydraulic conditions"}
        
        # Initial guess for gate opening
        Go = 1.0  # Start with 1m opening
        
        # Iterate to find correct opening
        max_iterations = 50
        tolerance = 0.001  # m³/s
        
        for i in range(max_iterations):
            # Calculate flow with current opening
            result = self.calculate_flow(gate_id, upstream_level, downstream_level, Go)
            Q = result.flow_rate_m3s
            
            # Check convergence
            error = target_flow - Q
            if abs(error) < tolerance:
                return {
                    "gate_opening_m": Go,
                    "achieved_flow_m3s": Q,
                    "discharge_coefficient": result.discharge_coefficient,
                    "iterations": i + 1,
                    "converged": True
                }
            
            # Adjust gate opening
            # Use Newton-Raphson-like approach
            # Since Q ∝ Cs and Cs ∝ (Hs/Go)^K2, we have Q ∝ Go^(-K2)
            # So dQ/dGo ∝ -K2 × Q / Go
            
            dQ_dGo = -calibration.K2 * Q / Go
            
            # Limit step size for stability
            step = error / dQ_dGo
            step = max(-0.2, min(0.2, step))  # Limit to 20cm per iteration
            
            Go = Go + step
            
            # Apply limits
            Go = max(calibration.min_opening, min(calibration.max_opening, Go))
        
        return {
            "gate_opening_m": Go,
            "achieved_flow_m3s": Q,
            "discharge_coefficient": result.discharge_coefficient,
            "iterations": max_iterations,
            "converged": False,
            "warning": "Did not converge to target flow"
        }
    
    def demonstrate_calculation(self):
        """Demonstrate the calibrated flow calculation"""
        
        print("=== CALIBRATED GATE FLOW CALCULATION ===\n")
        
        # Example conditions
        gate_id = "Source->M(0,0)"
        upstream_level = 221.0  # m
        downstream_level = 219.0  # m
        gate_opening = 1.5  # m
        
        print(f"Gate: {gate_id}")
        print(f"Upstream level (Hu): {upstream_level} m")
        print(f"Downstream level (Hs): {downstream_level} m") 
        print(f"Head difference (ΔH): {upstream_level - downstream_level} m")
        print(f"Gate opening (Go): {gate_opening} m")
        
        # Calculate flow
        result = self.calculate_flow(gate_id, upstream_level, downstream_level, gate_opening)
        
        print(f"\nResults:")
        print(f"Hs/Go ratio: {result.hs_go_ratio:.2f}")
        print(f"Discharge coefficient (Cs): {result.discharge_coefficient:.3f}")
        print(f"Flow rate (Q): {result.flow_rate_m3s:.2f} m³/s")
        print(f"Reynolds number: {result.reynolds_number:.0f}")
        
        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")
        
        # Show how Cs varies with Hs/Go
        print("\n\nDischarge Coefficient Variation:")
        print("Hs/Go Ratio    Cs")
        print("-" * 20)
        
        calibration = self.calibrations[gate_id]
        for ratio in [0.2, 0.5, 1.0, 1.5, 2.0]:
            Cs = calibration.K1 * (ratio ** calibration.K2)
            print(f"{ratio:>6.1f}      {Cs:.3f}")
        
        # Calculate required opening for target flow
        print("\n\nCalculate Required Opening:")
        target_flow = 4.5  # m³/s
        print(f"Target flow: {target_flow} m³/s")
        
        opening_result = self.calculate_required_opening(
            gate_id, target_flow, upstream_level, downstream_level
        )
        
        if "error" not in opening_result:
            print(f"Required gate opening: {opening_result['gate_opening_m']:.3f} m")
            print(f"Achieved flow: {opening_result['achieved_flow_m3s']:.2f} m³/s")
            print(f"Discharge coefficient: {opening_result['discharge_coefficient']:.3f}")
            print(f"Converged in {opening_result['iterations']} iterations")


if __name__ == "__main__":
    calculator = CalibratedGateFlow()
    calculator.demonstrate_calculation()