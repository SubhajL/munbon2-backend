#!/usr/bin/env python3
"""
Simple example showing the coupled nature of gate control
and how iteration solves the problem
"""

import numpy as np

def calculate_gate_flow(upstream_level, downstream_level, gate_opening, gate_width=2.0):
    """
    Calculate flow through a gate using orifice equation
    Q = Cd × A × √(2g × ΔH)
    """
    Cd = 0.6  # Discharge coefficient
    g = 9.81  # Gravity
    
    # Head difference
    delta_h = upstream_level - downstream_level
    
    if delta_h <= 0 or gate_opening <= 0:
        return 0.0
    
    # Opening area
    area = gate_width * gate_opening
    
    # Flow rate
    flow = Cd * area * np.sqrt(2 * g * delta_h)
    
    return flow

def simple_network_example():
    """
    Simple 3-node network example:
    
    Reservoir (221m) --> Gate 1 --> Canal Node (?) --> Gate 2 --> Field (?)
    
    Goal: Deliver 2 m³/s to the field
    """
    
    print("=== SIMPLE IRRIGATION GATE CONTROL EXAMPLE ===\n")
    print("Network: Reservoir -> Gate 1 -> Canal -> Gate 2 -> Field")
    print("Goal: Deliver 2 m³/s to the field\n")
    
    # Fixed parameters
    reservoir_level = 221.0  # m MSL
    canal_bottom = 218.0     # m MSL
    field_bottom = 217.5     # m MSL
    
    # Storage areas (simplified)
    canal_area = 5000.0      # m²
    field_area = 10000.0     # m²
    
    # Time step
    dt = 60.0  # seconds
    
    # Initial conditions
    canal_level = canal_bottom + 1.0  # Initial guess: 1m depth
    field_level = field_bottom + 0.5  # Initial guess: 0.5m depth
    
    # Gate openings (what we're trying to optimize)
    gate1_opening = 0.3  # Initial guess: 30cm
    gate2_opening = 0.5  # Initial guess: 50cm
    
    # Target flow
    target_flow = 2.0  # m³/s
    
    print("Initial Conditions:")
    print(f"  Reservoir: {reservoir_level:.1f}m")
    print(f"  Canal: {canal_level:.1f}m (depth: {canal_level-canal_bottom:.1f}m)")
    print(f"  Field: {field_level:.1f}m (depth: {field_level-field_bottom:.1f}m)")
    print(f"  Gate 1: {gate1_opening:.2f}m open")
    print(f"  Gate 2: {gate2_opening:.2f}m open")
    
    # Iterative solution
    print("\nIterative Solution:")
    print("-" * 60)
    print("Iter | Canal Level | Field Level | Flow G1 | Flow G2 | Error")
    print("-" * 60)
    
    iterations = 30
    tolerance = 0.01
    
    # Track convergence
    canal_levels = []
    field_levels = []
    flows = []
    
    for i in range(iterations):
        # Step 1: Calculate flows through gates
        flow_gate1 = calculate_gate_flow(reservoir_level, canal_level, gate1_opening)
        flow_gate2 = calculate_gate_flow(canal_level, field_level, gate2_opening)
        
        # Step 2: Update water levels based on continuity
        # Canal: inflow from gate1, outflow through gate2
        canal_imbalance = flow_gate1 - flow_gate2
        canal_level_change = (canal_imbalance * dt) / canal_area
        canal_level += canal_level_change
        
        # Field: inflow from gate2, outflow = target (assumed consumed)
        field_imbalance = flow_gate2 - target_flow
        field_level_change = (field_imbalance * dt) / field_area
        field_level += field_level_change
        
        # Constrain levels
        canal_level = max(canal_bottom + 0.1, min(canal_level, canal_bottom + 5.0))
        field_level = max(field_bottom + 0.1, min(field_level, field_bottom + 3.0))
        
        # Error
        error = abs(flow_gate2 - target_flow)
        
        # Store for plotting
        canal_levels.append(canal_level)
        field_levels.append(field_level)
        flows.append(flow_gate2)
        
        # Print every 5 iterations
        if i % 5 == 0:
            print(f"{i:4d} | {canal_level:11.2f} | {field_level:11.2f} | "
                  f"{flow_gate1:7.2f} | {flow_gate2:7.2f} | {error:6.3f}")
        
        # Check convergence
        if error < tolerance and i > 10:
            print(f"\nConverged after {i+1} iterations!")
            break
        
        # Step 3: Adjust gates (simple proportional control)
        if i % 5 == 0 and i > 0:  # Adjust every 5 iterations
            if flow_gate2 < target_flow:
                # Need more flow
                if canal_level - field_level < 1.0:
                    # Not enough head at gate 2, open gate 1 more
                    gate1_opening *= 1.1
                else:
                    # Enough head, open gate 2 more
                    gate2_opening *= 1.05
            else:
                # Too much flow
                gate2_opening *= 0.95
            
            # Constrain openings
            gate1_opening = min(gate1_opening, 1.0)  # Max 1m
            gate2_opening = min(gate2_opening, 1.0)  # Max 1m
    
    print("\nFinal Results:")
    print(f"  Canal Level: {canal_level:.2f}m (depth: {canal_level-canal_bottom:.2f}m)")
    print(f"  Field Level: {field_level:.2f}m (depth: {field_level-field_bottom:.2f}m)")
    print(f"  Gate 1: {gate1_opening:.3f}m ({gate1_opening*100:.1f}% open)")
    print(f"  Gate 2: {gate2_opening:.3f}m ({gate2_opening*100:.1f}% open)")
    print(f"  Flow to field: {flow_gate2:.3f} m³/s (target: {target_flow} m³/s)")
    
    # Create simple text-based visualization
    print("\n\nConvergence Visualization:")
    print("-" * 60)
    print("Canal Level Trend:")
    for i in range(0, len(canal_levels), 3):
        level = canal_levels[i]
        bar_length = int((level - 218) * 10)
        print(f"Iter {i:3d}: {'█' * bar_length} {level:.2f}m")
    
    print("\nFlow Rate Convergence to Target:")
    for i in range(0, len(flows), 3):
        flow = flows[i]
        target_bar = int(target_flow * 10)
        actual_bar = int(flow * 10)
        print(f"Iter {i:3d}: {'=' * target_bar}|{'█' * actual_bar} {flow:.2f} m³/s")
    
    # Explain the coupled nature
    print("\n" + "="*60)
    print("KEY INSIGHT: Why Simple Gate Control Doesn't Work")
    print("="*60)
    print("\nThe Coupling Problem:")
    print("1. You might think: 'Just calculate gate opening for 2 m³/s'")
    print("2. But gate flow depends on water levels before/after gate")
    print("3. And water levels depend on flows!")
    print("\nThe Solution:")
    print("- Start with initial guess of water levels")
    print("- Calculate flows")
    print("- Update water levels based on continuity")
    print("- Repeat until converged")
    print(f"\nIn this example, it took {i+1} iterations to find:")
    print(f"- Gate settings that deliver {target_flow} m³/s")
    print(f"- While maintaining hydraulic balance")


if __name__ == "__main__":
    simple_network_example()