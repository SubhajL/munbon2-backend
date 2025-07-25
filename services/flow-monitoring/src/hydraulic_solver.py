#!/usr/bin/env python3
"""
Iterative Hydraulic Solver for Munbon Irrigation Network
Solves the coupled system of water levels and flows
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import json
from datetime import datetime

from gate_hydraulics import GateHydraulics, GateProperties, HydraulicConditions, GateType
from water_gate_controller_fixed import WaterGateControllerFixed

@dataclass
class ConvergenceResult:
    """Result of hydraulic solver convergence"""
    converged: bool
    iterations: int
    max_error: float
    node_levels: Dict[str, float]
    gate_flows: Dict[str, float]
    warnings: List[str]

class HydraulicSolver:
    """
    Iterative solver for coupled hydraulic network
    Solves for steady-state water levels and flows
    """
    
    def __init__(self, network_file: str, geometry_file: str):
        """Initialize hydraulic solver"""
        
        # Load network
        self.controller = WaterGateControllerFixed(network_file, geometry_file)
        self.gate_hydraulics = GateHydraulics()
        
        # Solver parameters
        self.max_iterations = 100
        self.tolerance = 0.001  # 1mm convergence
        self.relaxation_factor = 0.7  # Under-relaxation for stability
        
        # Network structure
        self.nodes = set()
        self.gates = {}  # gate_id -> (upstream, downstream)
        self.gate_properties = {}
        self.gate_openings = {}  # Current gate settings
        
        # Hydraulic state
        self.water_levels = {}  # node -> water level (m MSL)
        self.flows = {}  # gate_id -> flow rate (m³/s)
        
        # Canal properties
        self.canal_inverts = {}
        self.canal_sections = self.controller.canal_sections
        
        # Initialize network
        self._initialize_network()
    
    def _initialize_network(self):
        """Build network structure and initial conditions"""
        
        # Extract all nodes
        for parent, child in self.controller.edges:
            self.nodes.add(parent)
            self.nodes.add(child)
            gate_id = f"{parent}->{child}"
            self.gates[gate_id] = (parent, child)
        
        # Set canal bottom elevations
        self.canal_inverts = {
            'Source': 221.0,
            'M(0,0)': 218.0,
            'M(0,1)': 217.9,
            'M(0,2)': 217.9,
            'M(0,3)': 217.8,
            'M(0,5)': 217.0,
            'M(0,12)': 215.0,
            'M(0,14)': 214.5
        }
        
        # Estimate remaining inverts
        for node in self.nodes:
            if node not in self.canal_inverts:
                # Simple estimation based on position
                self.canal_inverts[node] = 216.0
        
        # Initialize water levels (1m depth)
        for node in self.nodes:
            if node == 'Source':
                self.water_levels[node] = 221.0  # Reservoir level
            else:
                self.water_levels[node] = self.canal_inverts[node] + 1.0
        
        # Initialize gate properties
        for gate_id, (upstream, downstream) in self.gates.items():
            # Get capacity from network
            parent_info = self.controller.gates.get(upstream, {})
            q_max = parent_info.get('q_max', 5.0)
            if np.isnan(q_max):
                q_max = 5.0
            
            # Estimate gate properties
            gate_type = GateType.SLUICE_GATE
            self.gate_properties[gate_id] = self.gate_hydraulics.estimate_gate_properties(
                gate_id, q_max, gate_type
            )
            self.gate_properties[gate_id].sill_elevation_m = self.canal_inverts[upstream]
            
            # Ensure max_opening is set
            if self.gate_properties[gate_id].max_opening_m == 0:
                self.gate_properties[gate_id].max_opening_m = self.gate_properties[gate_id].height_m
            
            # Default gate opening (closed)
            self.gate_openings[gate_id] = 0.0
    
    def set_gate_opening(self, upstream: str, downstream: str, opening_m: float):
        """Set gate opening in meters"""
        gate_id = f"{upstream}->{downstream}"
        if gate_id in self.gates:
            self.gate_openings[gate_id] = opening_m
    
    def calculate_gate_flow(self, gate_id: str) -> float:
        """Calculate flow through gate based on current water levels"""
        
        if gate_id not in self.gates:
            return 0.0
        
        upstream, downstream = self.gates[gate_id]
        
        # Get current water levels
        h_upstream = self.water_levels.get(upstream, 0)
        h_downstream = self.water_levels.get(downstream, 0)
        
        # Get gate opening
        opening = self.gate_openings.get(gate_id, 0)
        
        if opening <= 0:
            return 0.0
        
        # Create hydraulic conditions
        conditions = HydraulicConditions(
            upstream_water_level_m=h_upstream,
            downstream_water_level_m=h_downstream,
            gate_opening_m=opening
        )
        
        # Calculate flow
        gate_props = self.gate_properties[gate_id]
        result = self.gate_hydraulics.calculate_gate_flow(gate_props, conditions)
        
        return result['flow_rate_m3s']
    
    def calculate_node_continuity(self, node: str) -> float:
        """
        Calculate flow imbalance at a node
        Positive = excess inflow, Negative = excess outflow
        """
        
        inflow = 0.0
        outflow = 0.0
        
        # Sum all flows connected to this node
        for gate_id, (upstream, downstream) in self.gates.items():
            flow = self.flows.get(gate_id, 0)
            
            if downstream == node:
                inflow += flow
            elif upstream == node:
                outflow += flow
        
        # Special case for source
        if node == 'Source':
            # Source can provide any required flow
            return 0.0
        
        return inflow - outflow
    
    def update_node_level(self, node: str, flow_imbalance: float, dt: float = 60.0):
        """
        Update water level based on flow imbalance
        Uses simplified storage routing
        """
        
        if node == 'Source':
            return  # Source level is fixed
        
        # Estimate node surface area (simplified)
        # Larger nodes have more storage
        if 'M(0,' in node and ')' == node[-1]:  # Main canal node
            surface_area = 5000.0  # m²
        else:
            surface_area = 1000.0  # m²
        
        # Change in water level
        dh = (flow_imbalance * dt) / surface_area
        
        # Apply with relaxation
        new_level = self.water_levels[node] + self.relaxation_factor * dh
        
        # Constraints
        min_level = self.canal_inverts[node] + 0.1  # Minimum 10cm depth
        max_level = self.canal_inverts[node] + 5.0  # Maximum 5m depth
        
        self.water_levels[node] = np.clip(new_level, min_level, max_level)
    
    def calculate_canal_head_loss(self, upstream: str, downstream: str, flow: float) -> float:
        """Calculate head loss in canal reach"""
        
        key = f"{upstream}->{downstream}"
        
        if key not in self.canal_sections or flow <= 0:
            return 0.0
        
        section = self.canal_sections[key]
        
        # Calculate normal depth and velocity
        y_normal = self.controller.calculate_normal_depth(flow, section)
        velocity = self.controller.calculate_velocity(flow, section)
        
        # Calculate hydraulic radius
        b = section.bottom_width_m
        m = section.side_slope
        A = b * y_normal + m * y_normal * y_normal
        P = b + 2 * y_normal * np.sqrt(1 + m * m)
        R = A / P if P > 0 else 0.1
        
        # Friction slope
        Sf = (section.manning_n * velocity) ** 2 / (R ** (4/3))
        
        # Head loss
        return Sf * section.length_m
    
    def solve_network(self, gate_settings: List[Dict]) -> ConvergenceResult:
        """
        Solve for steady-state water levels and flows
        gate_settings: [{'upstream': str, 'downstream': str, 'opening': float}]
        """
        
        # Set gate openings
        for setting in gate_settings:
            self.set_gate_opening(
                setting['upstream'],
                setting['downstream'],
                setting['opening']
            )
        
        # Initialize flows
        for gate_id in self.gates:
            self.flows[gate_id] = self.calculate_gate_flow(gate_id)
        
        # Iterative solution
        converged = False
        iteration = 0
        warnings = []
        
        print("\nIterative Hydraulic Solution:")
        print("-" * 60)
        
        while iteration < self.max_iterations and not converged:
            iteration += 1
            
            # Store previous levels for convergence check
            prev_levels = self.water_levels.copy()
            
            # Step 1: Update flows based on current water levels
            for gate_id in self.gates:
                self.flows[gate_id] = self.calculate_gate_flow(gate_id)
            
            # Step 2: Update water levels based on continuity
            for node in self.nodes:
                if node == 'Source':
                    continue
                
                # Calculate flow imbalance
                imbalance = self.calculate_node_continuity(node)
                
                # Update level
                self.update_node_level(node, imbalance)
            
            # Step 3: Apply canal head losses
            for gate_id, (upstream, downstream) in self.gates.items():
                flow = self.flows[gate_id]
                if flow > 0:
                    # Calculate head loss
                    head_loss = self.calculate_canal_head_loss(upstream, downstream, flow)
                    
                    # Adjust downstream level (simplified approach)
                    # In reality, would solve backwater curve
                    expected_downstream = self.water_levels[upstream] - head_loss
                    
                    # Blend with continuity-based level
                    current = self.water_levels[downstream]
                    self.water_levels[downstream] = (
                        0.5 * current + 0.5 * expected_downstream
                    )
            
            # Check convergence
            max_change = 0.0
            for node in self.nodes:
                if node != 'Source':
                    change = abs(self.water_levels[node] - prev_levels[node])
                    max_change = max(max_change, change)
            
            if iteration % 10 == 0:
                print(f"Iteration {iteration}: Max level change = {max_change:.4f}m")
            
            if max_change < self.tolerance:
                converged = True
        
        # Check for issues
        if not converged:
            warnings.append(f"Did not converge after {iteration} iterations")
        
        # Check for dry nodes
        for node in self.nodes:
            depth = self.water_levels[node] - self.canal_inverts[node]
            if depth < 0.1:
                warnings.append(f"Node {node} is nearly dry (depth={depth:.2f}m)")
        
        print(f"\nConverged: {converged} after {iteration} iterations")
        print(f"Final max error: {max_change:.4f}m")
        
        return ConvergenceResult(
            converged=converged,
            iterations=iteration,
            max_error=max_change,
            node_levels=self.water_levels.copy(),
            gate_flows=self.flows.copy(),
            warnings=warnings
        )
    
    def optimize_gates_for_target(self, target_flows: Dict[str, float]) -> Dict:
        """
        Optimize gate settings to achieve target flows
        Uses iterative adjustment
        """
        
        print("\nGate Optimization for Target Flows:")
        print("-" * 60)
        
        # Initial gate settings (start with small openings)
        for gate_id in self.gates:
            self.gate_openings[gate_id] = 0.1  # 10cm initial
        
        optimization_iterations = 20
        adjustment_factor = 0.3
        
        best_settings = {}
        best_error = float('inf')
        
        for opt_iter in range(optimization_iterations):
            # Solve network with current settings
            gate_settings = [
                {
                    'upstream': up,
                    'downstream': down,
                    'opening': self.gate_openings[f"{up}->{down}"]
                }
                for up, down in self.gates.values()
            ]
            
            result = self.solve_network(gate_settings)
            
            # Calculate error
            total_error = 0.0
            for location, target_flow in target_flows.items():
                # Find gates delivering to this location
                actual_flow = 0.0
                for gate_id, (up, down) in self.gates.items():
                    if down == location:
                        actual_flow += self.flows.get(gate_id, 0)
                
                error = target_flow - actual_flow
                total_error += abs(error)
                
                # Adjust upstream gates
                if abs(error) > 0.1:  # Significant error
                    # Find gates that can affect this flow
                    for gate_id, (up, down) in self.gates.items():
                        if down == location:
                            # Adjust this gate
                            current_opening = self.gate_openings[gate_id]
                            if error > 0:  # Need more flow
                                new_opening = current_opening * (1 + adjustment_factor)
                            else:  # Need less flow
                                new_opening = current_opening * (1 - adjustment_factor)
                            
                            # Constrain opening
                            max_opening = self.gate_properties[gate_id].height_m
                            self.gate_openings[gate_id] = np.clip(
                                new_opening, 0.0, max_opening
                            )
            
            print(f"Optimization iteration {opt_iter + 1}: Total error = {total_error:.3f} m³/s")
            
            if total_error < best_error:
                best_error = total_error
                best_settings = self.gate_openings.copy()
            
            if total_error < 0.1:  # Acceptable error
                break
        
        # Apply best settings
        self.gate_openings = best_settings
        
        return {
            'gate_settings': best_settings,
            'achieved_flows': self.flows.copy(),
            'water_levels': self.water_levels.copy(),
            'total_error': best_error
        }


def demonstrate_hydraulic_solver():
    """Demonstrate the iterative hydraulic solver"""
    
    # Initialize solver
    solver = HydraulicSolver(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== HYDRAULIC SOLVER DEMONSTRATION ===\n")
    
    # Scenario 1: Open specific gates and solve for water levels
    print("1. Solving for water levels with specified gate openings:")
    print("-" * 60)
    
    gate_settings = [
        {'upstream': 'Source', 'downstream': 'M(0,0)', 'opening': 0.8},
        {'upstream': 'M(0,0)', 'downstream': 'M(0,1)', 'opening': 0.4},
        {'upstream': 'M(0,0)', 'downstream': 'M(0,2)', 'opening': 0.6},
        {'upstream': 'M(0,2)', 'downstream': 'M(0,3)', 'opening': 0.5},
    ]
    
    result = solver.solve_network(gate_settings)
    
    print("\nResults:")
    print(f"Converged: {result.converged}")
    print(f"Iterations: {result.iterations}")
    
    print("\nWater Levels:")
    for node in ['Source', 'M(0,0)', 'M(0,1)', 'M(0,2)', 'M(0,3)']:
        if node in result.node_levels:
            level = result.node_levels[node]
            depth = level - solver.canal_inverts[node]
            print(f"  {node}: {level:.2f}m MSL (depth: {depth:.2f}m)")
    
    print("\nGate Flows:")
    for gate_id, flow in result.gate_flows.items():
        if flow > 0:
            print(f"  {gate_id}: {flow:.2f} m³/s")
    
    # Scenario 2: Optimize gates for target flows
    print("\n\n2. Optimizing gates to achieve target flows:")
    print("-" * 60)
    
    target_flows = {
        'M(0,1)': 1.0,  # 1 m³/s to RMC
        'M(0,2)': 2.0,  # 2 m³/s to LMC
        'M(0,3)': 1.5,  # 1.5 m³/s continuing on LMC
    }
    
    print("Target flows:")
    for location, flow in target_flows.items():
        print(f"  {location}: {flow} m³/s")
    
    optimization_result = solver.optimize_gates_for_target(target_flows)
    
    print("\nOptimized gate settings:")
    for gate_id, opening in optimization_result['gate_settings'].items():
        if opening > 0:
            print(f"  {gate_id}: {opening:.3f}m ({opening/solver.gate_properties[gate_id].height_m*100:.1f}%)")
    
    print("\nAchieved flows:")
    for location in target_flows:
        actual = 0
        for gate_id, (up, down) in solver.gates.items():
            if down == location:
                actual += optimization_result['achieved_flows'].get(gate_id, 0)
        print(f"  {location}: Target={target_flows[location]:.2f}, Actual={actual:.2f} m³/s")
    
    print(f"\nTotal error: {optimization_result['total_error']:.3f} m³/s")
    
    # Save results
    results_data = {
        'scenario_1': {
            'gate_settings': gate_settings,
            'converged': result.converged,
            'iterations': result.iterations,
            'water_levels': result.node_levels,
            'flows': result.gate_flows
        },
        'scenario_2': {
            'target_flows': target_flows,
            'optimized_gates': optimization_result['gate_settings'],
            'achieved_flows': optimization_result['achieved_flows'],
            'water_levels': optimization_result['water_levels'],
            'total_error': optimization_result['total_error']
        }
    }
    
    with open('hydraulic_solver_results.json', 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print("\n\nResults saved to hydraulic_solver_results.json")


if __name__ == "__main__":
    demonstrate_hydraulic_solver()