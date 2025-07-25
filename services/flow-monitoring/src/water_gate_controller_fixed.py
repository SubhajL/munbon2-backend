#!/usr/bin/env python3
"""
Fixed Water Gate Controller with proper hydraulic calculations
Correctly calculates water depth based on flow rate
"""

import numpy as np
from water_gate_controller_integrated import WaterGateControllerIntegrated, CanalSection

class WaterGateControllerFixed(WaterGateControllerIntegrated):
    """Enhanced controller with correct hydraulic calculations"""
    
    def calculate_normal_depth(self, flow_rate: float, canal_section: CanalSection, 
                             tolerance: float = 0.001) -> float:
        """
        Calculate normal water depth for given flow rate using iterative method
        Solves Manning equation: Q = (1/n) * A * R^(2/3) * S^(1/2)
        """
        
        # Canal parameters
        b = canal_section.bottom_width_m
        m = canal_section.side_slope
        n = canal_section.manning_n
        S = canal_section.bed_slope
        
        # If no flow, depth is zero
        if flow_rate <= 0:
            return 0.0
        
        # Initial guess - use 70% of design depth
        y = canal_section.depth_m * 0.7
        
        # Newton-Raphson iteration to find normal depth
        max_iterations = 50
        for i in range(max_iterations):
            # Calculate area and wetted perimeter
            A = b * y + m * y * y
            P = b + 2 * y * np.sqrt(1 + m * m)
            
            # Hydraulic radius
            R = A / P if P > 0 else 0
            
            # Manning equation
            Q_calc = (1/n) * A * (R**(2/3)) * (S**0.5)
            
            # Check convergence
            error = abs(Q_calc - flow_rate)
            if error < tolerance:
                break
            
            # Calculate derivatives for Newton-Raphson
            # dA/dy = b + 2*m*y
            dA_dy = b + 2 * m * y
            
            # dP/dy = 2*sqrt(1 + m^2)
            dP_dy = 2 * np.sqrt(1 + m * m)
            
            # dR/dy = (dA/dy * P - A * dP/dy) / P^2
            dR_dy = (dA_dy * P - A * dP_dy) / (P * P) if P > 0 else 0
            
            # dQ/dy using chain rule
            if R > 0:
                dQ_dy = (1/n) * (S**0.5) * (
                    dA_dy * (R**(2/3)) + 
                    A * (2/3) * (R**(-1/3)) * dR_dy
                )
            else:
                dQ_dy = 0.1  # Avoid division by zero
            
            # Newton-Raphson update
            if abs(dQ_dy) > 0.0001:
                y_new = y - (Q_calc - flow_rate) / dQ_dy
                
                # Ensure positive depth and limit to design depth
                y_new = max(0.01, min(y_new, canal_section.depth_m))
                
                # Relaxation to improve convergence
                y = 0.7 * y + 0.3 * y_new
            else:
                # If derivative too small, use bisection
                if Q_calc < flow_rate:
                    y *= 1.1
                else:
                    y *= 0.9
        
        return y
    
    def calculate_velocity(self, flow_rate: float, canal_section: CanalSection) -> float:
        """Calculate water velocity using correct water depth"""
        
        # First calculate the actual water depth for this flow rate
        y = self.calculate_normal_depth(flow_rate, canal_section)
        
        # Now calculate velocity with correct depth
        b = canal_section.bottom_width_m
        m = canal_section.side_slope
        
        # Area with actual water depth
        area = b * y + m * y * y
        
        # Velocity from continuity equation
        velocity = flow_rate / area if area > 0 else 0
        
        return velocity
    
    def compare_velocities(self, canal_section: CanalSection):
        """Compare velocities at different flow rates"""
        
        flows = [3.0, 6.0, 9.0]
        print(f"\nCanal Section Analysis:")
        print(f"Bottom width: {canal_section.bottom_width_m} m")
        print(f"Design depth: {canal_section.depth_m} m")
        print(f"Manning's n: {canal_section.manning_n}")
        print(f"Bed slope: {canal_section.bed_slope}")
        print(f"\nFlow Rate | Water Depth | Area    | Velocity | Travel Time (1000m)")
        print("-" * 70)
        
        for Q in flows:
            y = self.calculate_normal_depth(Q, canal_section)
            A = canal_section.bottom_width_m * y + canal_section.side_slope * y * y
            V = self.calculate_velocity(Q, canal_section)
            travel_time = 1000 / V if V > 0 else float('inf')
            
            print(f"{Q:8.1f} | {y:10.3f} | {A:7.3f} | {V:8.3f} | {travel_time:10.1f} min")


# Test the fix
if __name__ == "__main__":
    import json
    
    # Load network and geometry
    controller = WaterGateControllerFixed(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== HYDRAULIC ANALYSIS WITH CORRECT CALCULATIONS ===\n")
    
    # Test key sections
    test_sections = [
        ('M(0,0)', 'M(0,1)', "Outlet"),
        ('M(0,2)', 'M(0,3)', "LMC Start"), 
        ('M(0,12)', 'M(0,13)', "LMC End")
    ]
    
    for from_node, to_node, desc in test_sections:
        key = f"{from_node}->{to_node}"
        if key in controller.canal_sections:
            print(f"\n{'='*70}")
            print(f"{desc}: {from_node} → {to_node}")
            section = controller.canal_sections[key]
            controller.compare_velocities(section)
    
    # Now test travel times with different flows
    print(f"\n{'='*70}")
    print("\nTRAVEL TIME COMPARISON")
    print("="*70)
    
    destinations = [
        ('M(0,2)', 'LMC Start'),
        ('M(0,5)', 'Zone 2 Start'),
        ('M(0,12)', '38R Branch')
    ]
    
    flow_rates = [3.0, 6.0, 9.0]
    
    print(f"\n{'Destination':<15} | {'Low (3 m³/s)':<15} | {'Med (6 m³/s)':<15} | {'High (9 m³/s)':<15}")
    print("-" * 70)
    
    for gate_id, desc in destinations:
        times = []
        for flow in flow_rates:
            arrival_times = controller.propagate_flow_with_delay('M(0,0)', flow)
            time_min = arrival_times.get(gate_id, 0) / 60
            times.append(time_min)
        
        print(f"{desc:<15} | {times[0]:>10.1f} min | {times[1]:>10.1f} min | {times[2]:>10.1f} min")
        
        # Show percentage reduction
        if times[0] > 0:
            reduction = (times[0] - times[2]) / times[0] * 100
            print(f"{'':15} | {'':15} | {'':15} | Reduction: {reduction:.1f}%")