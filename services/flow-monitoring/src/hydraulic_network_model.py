#!/usr/bin/env python3
"""
Hydraulic Network Model for Munbon Irrigation System
Tracks water levels throughout the network based on gate operations
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
from gate_hydraulics import GateHydraulics, GateProperties, HydraulicConditions, GateType
from water_gate_controller_fixed import WaterGateControllerFixed

@dataclass
class NodeHydraulics:
    """Hydraulic conditions at a network node"""
    node_id: str
    water_level: float  # m MSL
    flow_in: float      # m³/s
    flow_out: float     # m³/s
    canal_bottom: float # m MSL
    water_depth: float  # m
    updated: datetime

@dataclass
class ReachHydraulics:
    """Hydraulic conditions in a canal reach"""
    upstream_node: str
    downstream_node: str
    flow_rate: float    # m³/s
    upstream_level: float
    downstream_level: float
    head_loss: float    # m
    travel_time: float  # seconds
    velocity: float     # m/s
    froude_number: float

class HydraulicNetworkModel:
    """
    Models water levels and flows throughout the irrigation network
    Accounts for gate hydraulics, channel losses, and backwater effects
    """
    
    def __init__(self, network_file: str, geometry_file: str):
        """Initialize hydraulic network model"""
        
        # Load network controller
        self.controller = WaterGateControllerFixed(network_file, geometry_file)
        
        # Gate hydraulics calculator
        self.gate_hydraulics = GateHydraulics()
        
        # Node water levels (m MSL)
        self.node_levels = {}
        
        # Gate properties
        self.gate_properties = {}
        
        # Canal bottom elevations
        self.canal_inverts = {}
        
        # Initialize network
        self._initialize_network()
        
    def _initialize_network(self):
        """Initialize network with elevations and gate properties"""
        
        # Reservoir/source level
        RESERVOIR_LEVEL = 221.0  # m MSL at dam
        
        # Estimate canal bottom elevations based on typical slopes
        # Main canal slope: 0.0001 (1m per 10km)
        # Lateral canal slope: 0.0002 (2m per 10km)
        
        # Set known elevations
        self.canal_inverts = {
            'Source': 221.0,
            'M(0,0)': 218.0,    # Outlet sill
            'M(0,1)': 217.9,    # RMC start
            'M(0,2)': 217.9,    # LMC start
            'M(0,3)': 217.8,    # 9R branch
            'M(0,5)': 217.0,    # Zone 2 start
            'M(0,12)': 215.0,   # 38R branch
            'M(0,14)': 214.5    # LMC end
        }
        
        # Initialize water levels
        self.node_levels = {
            'Source': NodeHydraulics(
                node_id='Source',
                water_level=RESERVOIR_LEVEL,
                flow_in=0,
                flow_out=0,
                canal_bottom=221.0,
                water_depth=0,
                updated=datetime.now()
            )
        }
        
        # Initialize all nodes
        for node_id in self.controller.gates:
            if node_id not in self.canal_inverts:
                # Estimate based on position
                path = self.controller.find_path('M(0,0)', node_id)
                if path:
                    # Assume 0.5m drop per connection
                    self.canal_inverts[node_id] = 218.0 - 0.5 * len(path)
                else:
                    self.canal_inverts[node_id] = 216.0
            
            # Initial water level = bottom + 1m
            self.node_levels[node_id] = NodeHydraulics(
                node_id=node_id,
                water_level=self.canal_inverts[node_id] + 1.0,
                flow_in=0,
                flow_out=0,
                canal_bottom=self.canal_inverts[node_id],
                water_depth=1.0,
                updated=datetime.now()
            )
        
        # Initialize gate properties
        self._initialize_gates()
    
    def _initialize_gates(self):
        """Initialize gate properties for each connection"""
        
        for parent, child in self.controller.edges:
            gate_id = f"{parent}->{child}"
            
            # Skip if parent not in canal inverts (e.g., 'S')
            if parent not in self.canal_inverts:
                continue
                
            # Get flow capacity from network data
            parent_info = self.controller.gates.get(parent, {})
            q_max = parent_info.get('q_max', 5.0)
            if np.isnan(q_max):
                q_max = 5.0
            
            # Determine gate type
            if parent == 'M(0,0)':
                gate_type = GateType.SLUICE_GATE
            elif 'RMC' in parent_info.get('canal', ''):
                gate_type = GateType.RADIAL_GATE
            else:
                gate_type = GateType.SLUICE_GATE
            
            # Estimate gate properties
            self.gate_properties[gate_id] = self.gate_hydraulics.estimate_gate_properties(
                gate_id, q_max, gate_type
            )
            self.gate_properties[gate_id].sill_elevation_m = self.canal_inverts[parent]
    
    def calculate_gate_flow(self, upstream_node: str, downstream_node: str, 
                          gate_opening: float) -> Dict:
        """
        Calculate flow through gate based on actual water levels
        """
        
        gate_id = f"{upstream_node}->{downstream_node}"
        
        if gate_id not in self.gate_properties:
            return {
                'flow_rate': 0, 
                'velocity': 0,
                'regime': 'closed',
                'upstream_level': 0,
                'downstream_level': 0,
                'head_difference': 0,
                'error': 'Gate not found'
            }
        
        gate = self.gate_properties[gate_id]
        
        # Get actual water levels
        up_level = self.node_levels[upstream_node].water_level
        down_level = self.node_levels[downstream_node].water_level
        
        # Create hydraulic conditions
        conditions = HydraulicConditions(
            upstream_water_level_m=up_level,
            downstream_water_level_m=down_level,
            gate_opening_m=gate_opening
        )
        
        # Calculate flow
        result = self.gate_hydraulics.calculate_gate_flow(gate, conditions)
        
        return {
            'flow_rate': result['flow_rate_m3s'],
            'velocity': result['velocity_ms'],
            'regime': result['flow_regime'],
            'upstream_level': up_level,
            'downstream_level': down_level,
            'head_difference': up_level - down_level
        }
    
    def update_node_levels(self, node_id: str, new_level: float):
        """Update water level at a node"""
        if node_id in self.node_levels:
            self.node_levels[node_id].water_level = new_level
            self.node_levels[node_id].water_depth = new_level - self.canal_inverts[node_id]
            self.node_levels[node_id].updated = datetime.now()
    
    def calculate_canal_losses(self, upstream_node: str, downstream_node: str, 
                             flow_rate: float) -> float:
        """
        Calculate head loss in canal reach using Manning's equation
        """
        
        key = f"{upstream_node}->{downstream_node}"
        
        if key not in self.controller.canal_sections:
            # Default friction loss
            return 0.1  # 0.1m loss
        
        section = self.controller.canal_sections[key]
        
        # Calculate normal depth for this flow
        normal_depth = self.controller.calculate_normal_depth(flow_rate, section)
        
        # Calculate velocity
        velocity = self.controller.calculate_velocity(flow_rate, section)
        
        # Friction loss using Manning's equation
        # hf = (n² × L × V²) / (R^(4/3))
        # Where R = hydraulic radius
        
        b = section.bottom_width_m
        m = section.side_slope
        y = normal_depth
        
        # Area and wetted perimeter
        A = b * y + m * y * y
        P = b + 2 * y * np.sqrt(1 + m * m)
        R = A / P if P > 0 else 0.1
        
        # Friction slope
        Sf = (section.manning_n * velocity) ** 2 / (R ** (4/3))
        
        # Head loss
        head_loss = Sf * section.length_m
        
        return head_loss
    
    def propagate_levels_downstream(self, start_node: str, flow_rate: float):
        """
        Propagate water levels downstream from a node
        Uses energy equation: Z1 + V1²/2g = Z2 + V2²/2g + hf
        """
        
        # BFS to update all downstream nodes
        queue = [(start_node, flow_rate)]
        visited = set()
        
        while queue:
            current_node, current_flow = queue.pop(0)
            
            if current_node in visited:
                continue
            
            visited.add(current_node)
            
            # Get downstream nodes
            downstream_nodes = self.controller.get_downstream_gates(current_node)
            
            for down_node in downstream_nodes:
                # Calculate head loss in reach
                head_loss = self.calculate_canal_losses(current_node, down_node, current_flow)
                
                # Energy equation
                # Assuming velocity head is small compared to elevation head
                upstream_level = self.node_levels[current_node].water_level
                downstream_level = upstream_level - head_loss
                
                # Update downstream level
                self.update_node_levels(down_node, downstream_level)
                
                # Add to queue
                queue.append((down_node, current_flow))
    
    def calculate_backwater_curve(self, start_node: str, known_level: float, 
                                flow_rate: float) -> Dict[str, float]:
        """
        Calculate backwater curve upstream from known water level
        Uses standard step method
        """
        
        backwater_levels = {start_node: known_level}
        
        # Get upstream nodes
        upstream_nodes = self.controller.get_upstream_gates(start_node)
        
        for up_node in upstream_nodes:
            key = f"{up_node}->{start_node}"
            
            if key in self.controller.canal_sections:
                section = self.controller.canal_sections[key]
                
                # Calculate normal depth
                y_normal = self.controller.calculate_normal_depth(flow_rate, section)
                
                # Starting depth at downstream end
                y_downstream = known_level - self.canal_inverts[start_node]
                
                # If downstream depth > normal depth, backwater effect
                if y_downstream > y_normal:
                    # Simplified - assume linear transition
                    # In reality, would use standard step method
                    y_upstream = y_downstream + 0.5 * section.bed_slope * section.length_m
                else:
                    y_upstream = y_normal
                
                upstream_level = self.canal_inverts[up_node] + y_upstream
                backwater_levels[up_node] = upstream_level
        
        return backwater_levels
    
    def simulate_gate_operation(self, gate_operations: List[Dict]) -> Dict:
        """
        Simulate network operation with multiple gates
        gate_operations: [{'upstream': str, 'downstream': str, 'opening': float}]
        """
        
        results = {
            'operations': [],
            'node_levels': {},
            'reach_hydraulics': [],
            'warnings': []
        }
        
        # Step 1: Calculate flows through all gates
        total_flows = {}
        
        for op in gate_operations:
            up_node = op['upstream']
            down_node = op['downstream']
            opening = op['opening']
            
            # Calculate flow
            flow_result = self.calculate_gate_flow(up_node, down_node, opening)
            
            op_result = {
                'gate': f"{up_node}->{down_node}",
                'opening': opening,
                'flow_rate': flow_result['flow_rate'],
                'velocity': flow_result['velocity'],
                'regime': flow_result['regime'],
                'head_diff': flow_result['head_difference']
            }
            
            results['operations'].append(op_result)
            
            # Track flows
            if up_node not in total_flows:
                total_flows[up_node] = {'out': 0, 'in': 0}
            if down_node not in total_flows:
                total_flows[down_node] = {'out': 0, 'in': 0}
            
            total_flows[up_node]['out'] += flow_result['flow_rate']
            total_flows[down_node]['in'] += flow_result['flow_rate']
        
        # Step 2: Update water levels based on continuity
        for node_id, flows in total_flows.items():
            net_flow = flows['in'] - flows['out']
            
            if abs(net_flow) > 0.1:  # Significant imbalance
                # Adjust water level based on storage change
                # Simplified - assumes 1000 m² surface area per node
                area = 1000  # m²
                dt = 60  # seconds
                dh = (net_flow * dt) / area
                
                current_level = self.node_levels[node_id].water_level
                new_level = current_level + dh
                
                self.update_node_levels(node_id, new_level)
        
        # Step 3: Propagate levels through network
        # Start from source and work downstream
        if 'M(0,0)' in total_flows:
            self.propagate_levels_downstream('M(0,0)', total_flows['M(0,0)']['out'])
        
        # Step 4: Check for backwater effects at confluences
        # This is where downstream high water affects upstream
        
        # Step 5: Collect final results
        for node_id, node_data in self.node_levels.items():
            results['node_levels'][node_id] = {
                'water_level': node_data.water_level,
                'water_depth': node_data.water_depth,
                'canal_bottom': node_data.canal_bottom
            }
        
        # Calculate reach hydraulics
        for parent, child in self.controller.edges:
            if parent in self.node_levels and child in self.node_levels:
                up_level = self.node_levels[parent].water_level
                down_level = self.node_levels[child].water_level
                
                # Find flow in this reach
                flow = 0
                for op in results['operations']:
                    if op['gate'] == f"{parent}->{child}":
                        flow = op['flow_rate']
                        break
                
                if flow > 0:
                    # Calculate hydraulics
                    key = f"{parent}->{child}"
                    if key in self.controller.canal_sections:
                        section = self.controller.canal_sections[key]
                        velocity = self.controller.calculate_velocity(flow, section)
                        travel_time = section.length_m / velocity if velocity > 0 else 0
                        
                        # Froude number
                        depth = self.controller.calculate_normal_depth(flow, section)
                        froude = velocity / np.sqrt(9.81 * depth) if depth > 0 else 0
                        
                        reach = ReachHydraulics(
                            upstream_node=parent,
                            downstream_node=child,
                            flow_rate=flow,
                            upstream_level=up_level,
                            downstream_level=down_level,
                            head_loss=up_level - down_level,
                            travel_time=travel_time,
                            velocity=velocity,
                            froude_number=froude
                        )
                        
                        results['reach_hydraulics'].append({
                            'reach': key,
                            'flow': flow,
                            'velocity': velocity,
                            'head_loss': up_level - down_level,
                            'travel_time_min': travel_time / 60,
                            'froude': froude
                        })
        
        return results
    
    def create_hydraulic_profile_plot(self, path: List[str]) -> Dict:
        """
        Create hydraulic profile data along a path
        """
        
        profile_data = {
            'distance': [],
            'canal_bottom': [],
            'water_surface': [],
            'energy_grade': [],
            'nodes': []
        }
        
        cumulative_distance = 0
        
        for i, node in enumerate(path):
            # Add node data
            node_data = self.node_levels[node]
            water_level = node_data.water_level
            bottom = node_data.canal_bottom
            
            # Velocity head (simplified)
            velocity = 1.0  # m/s typical
            velocity_head = velocity**2 / (2 * 9.81)
            energy_level = water_level + velocity_head
            
            profile_data['distance'].append(cumulative_distance)
            profile_data['canal_bottom'].append(bottom)
            profile_data['water_surface'].append(water_level)
            profile_data['energy_grade'].append(energy_level)
            profile_data['nodes'].append(node)
            
            # Add distance to next node
            if i < len(path) - 1:
                key = f"{node}->{path[i+1]}"
                if key in self.controller.canal_sections:
                    section = self.controller.canal_sections[key]
                    cumulative_distance += section.length_m
                else:
                    cumulative_distance += 1000  # Default 1km
        
        return profile_data


# Example usage
if __name__ == "__main__":
    # Initialize model
    model = HydraulicNetworkModel(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== HYDRAULIC NETWORK MODEL ===")
    print(f"Nodes initialized: {len(model.node_levels)}")
    print(f"Gates configured: {len(model.gate_properties)}")
    
    # Example: Open main gate
    print("\n1. Opening main outlet gate 50%:")
    
    gate_ops = [
        {'upstream': 'Source', 'downstream': 'M(0,0)', 'opening': 0.6},  # 50% of 1.2m
        {'upstream': 'M(0,0)', 'downstream': 'M(0,2)', 'opening': 0.5},  # LMC
        {'upstream': 'M(0,2)', 'downstream': 'M(0,3)', 'opening': 0.4}   # To 9R
    ]
    
    results = model.simulate_gate_operation(gate_ops)
    
    print("\nGate Operations:")
    for op in results['operations']:
        print(f"  {op['gate']}: {op['flow_rate']:.2f} m³/s @ {op['velocity']:.2f} m/s ({op['regime']})")
    
    print("\nWater Levels at Key Nodes:")
    for node in ['Source', 'M(0,0)', 'M(0,2)', 'M(0,3)', 'M(0,5)']:
        if node in results['node_levels']:
            data = results['node_levels'][node]
            print(f"  {node}: {data['water_level']:.2f}m MSL (depth: {data['water_depth']:.2f}m)")
    
    # Create hydraulic profile
    print("\n2. Hydraulic Profile along LMC:")
    path = ['M(0,0)', 'M(0,2)', 'M(0,3)', 'M(0,5)', 'M(0,12)']
    profile = model.create_hydraulic_profile_plot(path)
    
    for i, node in enumerate(profile['nodes']):
        print(f"  {node}: Bottom={profile['canal_bottom'][i]:.1f}m, "
              f"Water={profile['water_surface'][i]:.1f}m, "
              f"Distance={profile['distance'][i]/1000:.1f}km")