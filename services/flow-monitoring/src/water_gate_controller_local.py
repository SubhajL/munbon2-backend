#!/usr/bin/env python3
"""
Water Gate Controller V 1.2 - Local Version
Modified to run locally without Colab dependencies
"""

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import math
import warnings
from datetime import datetime, timedelta
import os
import json
from typing import Dict, List, Tuple, Optional


class WaterGateController:
    """Water Gate Controller with travel time calculations"""
    
    def __init__(self, structure_file: str, requirement_file: str, 
                 canal_geometry_file: Optional[str] = None):
        """
        Initialize the controller
        
        Args:
            structure_file: Path to Structure.xlsx
            requirement_file: Path to SCADA requirements file
            canal_geometry_file: Optional path to canal geometry JSON
        """
        self.structure_df = pd.read_excel(structure_file)
        self.requirement_file = requirement_file
        self.canal_geometry = None
        
        # Build network graph
        self.G = self._build_network()
        
        # Load canal geometry if provided
        if canal_geometry_file:
            self.load_canal_geometry(canal_geometry_file)
    
    def _build_network(self) -> nx.DiGraph:
        """Build the network graph from structure data"""
        edges = list(zip(self.structure_df['Source'], self.structure_df['Target']))
        G = nx.DiGraph()
        G.add_edges_from(edges)
        G.add_edge('S', 'M(0,0)')  # Add source connection
        return G
    
    def load_canal_geometry(self, filename: str):
        """Load canal geometry from JSON file"""
        with open(filename, 'r') as f:
            self.canal_geometry = json.load(f)
    
    def calculate_travel_time(self, from_node: str, to_node: str, 
                            flow_rate: float) -> float:
        """
        Calculate water travel time between nodes
        
        Args:
            from_node: Starting node
            to_node: Ending node
            flow_rate: Flow rate in m³/s
            
        Returns:
            Travel time in seconds
        """
        if not self.canal_geometry:
            return 0  # No delay if geometry not provided
        
        # Find canal section
        for section in self.canal_geometry.get('canal_sections', []):
            if section['from_node'] == from_node and section['to_node'] == to_node:
                # Calculate velocity using Manning's equation
                geometry = section['geometry']
                velocity = self._calculate_velocity(flow_rate, geometry)
                
                # Travel time = Distance / Velocity
                travel_time = geometry['length_m'] / velocity
                return travel_time
        
        return 0  # Default if section not found
    
    def _calculate_velocity(self, flow_rate: float, geometry: Dict) -> float:
        """Calculate water velocity using Manning's equation"""
        cs = geometry['cross_section']
        hp = geometry['hydraulic_params']
        
        # Simplified calculation for trapezoidal channel
        if cs['type'] == 'trapezoidal':
            # Estimate water depth for given flow
            # This is simplified - in reality would need iterative solution
            y = cs['depth_m'] * 0.7  # Assume 70% full
            
            # Calculate area and wetted perimeter
            b = cs['bottom_width_m']
            m = cs.get('side_slope', 1.0)
            
            area = y * (b + m * y)
            wetted_perimeter = b + 2 * y * math.sqrt(1 + m**2)
            
            # Hydraulic radius
            R = area / wetted_perimeter
            
            # Manning's equation: V = (1/n) * R^(2/3) * S^(1/2)
            n = hp['manning_n']
            S = hp['bed_slope']
            
            velocity = (1/n) * (R**(2/3)) * (S**0.5)
            
            # Check if calculated velocity matches flow rate
            if abs(area * velocity - flow_rate) > 0.1:
                # Adjust velocity to match flow rate
                velocity = flow_rate / area
            
            return max(velocity, 0.1)  # Minimum velocity
        
        # Default velocity if calculation fails
        return 1.0
    
    def initialize(self):
        """Initialize gate requirements and working graph"""
        req_df = pd.read_excel(self.requirement_file, skiprows=1)
        req_df = req_df[['Gate Valve', 'q_max (m^3/s)', 'Required Daily Water (cm)', 
                        'Required Daily Volume (m3)']].dropna(subset=['Gate Valve'])
        
        gate_info = req_df.fillna(0).set_index('Gate Valve').to_dict(orient='index')
        
        # Find all gates that need to be open
        all_open_gates = set()
        for g in req_df[req_df['Required Daily Volume (m3)'] > 0]['Gate Valve']:
            all_open_gates = all_open_gates.union(set(nx.shortest_path(self.G, 'S', g)))
        
        adjustable_gates = [g for g in all_open_gates if g[0] != 'J']
        current_G = self.G.subgraph(all_open_gates)
        
        # Set parent relationships and capacities
        for node in self.G.nodes:
            for n in self.G.neighbors(node):
                if n in gate_info:
                    gate_info[n]['parent'] = node
                else:
                    gate_info[n] = dict()
                    gate_info[n]['parent'] = node
        
        # Set edge capacities
        for n in adjustable_gates:
            if n in gate_info and gate_info[n]['q_max (m^3/s)'] > 0:
                current_G[gate_info[n]['parent']][n]['capacity'] = gate_info[n]['q_max (m^3/s)']
        
        # Create working graph
        working_G = nx.DiGraph()
        working_G.add_nodes_from(current_G.nodes(data=True))
        working_G.add_edges_from(current_G.edges(data=True))
        
        # Add sink connections
        for g in gate_info:
            if 'Required Daily Volume (m3)' in gate_info[g]:
                if gate_info[g]['Required Daily Volume (m3)'] > 0:
                    working_G.add_edge(g, 'T')
        
        return working_G, gate_info
    
    def calculate_with_travel_time(self):
        """Calculate gate operations with travel time consideration"""
        working_G, gate_info = self.initialize()
        operations = []
        steps = 1
        
        # Track water arrival times at each node
        water_arrival_times = {'S': 0}  # Water available at source immediately
        
        while True:
            print(f'\nStep {steps}')
            steps += 1
            
            # Run max flow algorithm
            flow_value, flow_dict = nx.algorithms.flow.maximum_flow(working_G, 'S', 'T')
            
            if flow_value == 0:
                break
            
            # Calculate fill times and travel times
            filled_area = dict()
            gate_operations = []
            
            for u in flow_dict:
                for v in flow_dict[u]:
                    if flow_dict[u][v] > 0 and v != 'T':
                        # Calculate travel time
                        travel_time = self.calculate_travel_time(u, v, flow_dict[u][v])
                        
                        # Update water arrival time
                        if u in water_arrival_times:
                            arrival_time = water_arrival_times[u] + travel_time
                            water_arrival_times[v] = max(
                                water_arrival_times.get(v, 0), 
                                arrival_time
                            )
                    
                    if v == 'T' and flow_dict[u][v] > 0:
                        filled_area[u] = {
                            'q_max': flow_dict[u][v],
                            'fill_time': math.ceil(
                                gate_info[u]['Required Daily Volume (m3)'] / flow_dict[u][v]
                            ),
                            'delay': water_arrival_times.get(u, 0)
                        }
            
            if not filled_area:
                break
            
            # Find minimum time step considering delays
            time_step = min([
                filled_area[u]['fill_time'] + filled_area[u]['delay'] 
                for u in filled_area
            ])
            
            minute_step = math.ceil(time_step / 60)
            print(f'{minute_step} mins (including travel time)')
            
            # Store operations with timing
            operations.append({
                'step': steps - 1,
                'minute_step': minute_step,
                'flow_dict': flow_dict,
                'water_arrival_times': water_arrival_times.copy()
            })
            
            # Update gate requirements
            self._update_gates(flow_dict, gate_info, minute_step, filled_area)
            
            # Update graph
            working_G = self._update_graph(gate_info)
            
            if len(working_G.nodes) == 0:
                break
        
        return operations, gate_info
    
    def _update_gates(self, flow_dict, gate_info, minute_step, filled_area):
        """Update gate requirements after each step"""
        for u in filled_area:
            volume_delivered = minute_step * 60 * filled_area[u]['q_max']
            gate_info[u]['Required Daily Volume (m3)'] = max(
                0, 
                gate_info[u]['Required Daily Volume (m3)'] - volume_delivered
            )
            print(f'Fill Area: {u}, Volume: {round(volume_delivered, 0)} m³')
    
    def _update_graph(self, gate_info):
        """Update working graph based on remaining requirements"""
        all_open_gates = set()
        
        for g in gate_info:
            if 'Required Daily Volume (m3)' in gate_info[g] and \
               gate_info[g]['Required Daily Volume (m3)'] > 0:
                all_open_gates = all_open_gates.union(
                    set(nx.shortest_path(self.G, 'S', g))
                )
        
        if not all_open_gates:
            return nx.DiGraph()
        
        adjustable_gates = [g for g in all_open_gates if g[0] != 'J']
        current_G = self.G.subgraph(all_open_gates)
        
        # Set capacities
        for n in adjustable_gates:
            if n in gate_info and gate_info[n]['q_max (m^3/s)'] > 0:
                current_G[gate_info[n]['parent']][n]['capacity'] = \
                    gate_info[n]['q_max (m^3/s)']
        
        # Create working graph
        working_G = nx.DiGraph()
        working_G.add_nodes_from(current_G.nodes(data=True))
        working_G.add_edges_from(current_G.edges(data=True))
        
        # Add sink connections
        for g in gate_info:
            if 'Required Daily Volume (m3)' in gate_info[g]:
                if gate_info[g]['Required Daily Volume (m3)'] > 0:
                    working_G.add_edge(g, 'T')
        
        return working_G
    
    def visualize_network(self, highlight_nodes=None):
        """Visualize the network graph"""
        plt.figure(figsize=(15, 20))
        pos = nx.drawing.nx_pydot.graphviz_layout(self.G, prog='dot')
        
        # Node colors
        node_colors = []
        for node in self.G.nodes():
            if highlight_nodes and node in highlight_nodes:
                node_colors.append('red')
            elif node == 'S':
                node_colors.append('green')
            elif node.startswith('J'):
                node_colors.append('yellow')
            else:
                node_colors.append('skyblue')
        
        nx.draw(self.G, pos, with_labels=True, node_size=500, 
                node_color=node_colors, arrowsize=10)
        
        plt.title("Irrigation Network Structure")
        plt.tight_layout()
        plt.show()
    
    def add_canal_section(self, from_node: str, to_node: str):
        """Add a new canal section to the network"""
        self.G.add_edge(from_node, to_node)
        print(f"Added canal section: {from_node} -> {to_node}")
    
    def remove_canal_section(self, from_node: str, to_node: str):
        """Remove a canal section from the network"""
        if self.G.has_edge(from_node, to_node):
            self.G.remove_edge(from_node, to_node)
            print(f"Removed canal section: {from_node} -> {to_node}")
        else:
            print(f"Canal section {from_node} -> {to_node} does not exist")
    
    def modify_network_from_file(self, modifications_file: str):
        """Apply network modifications from a JSON file"""
        with open(modifications_file, 'r') as f:
            modifications = json.load(f)
        
        # Add new edges
        for edge in modifications.get('add_edges', []):
            self.add_canal_section(edge['from'], edge['to'])
        
        # Remove edges
        for edge in modifications.get('remove_edges', []):
            self.remove_canal_section(edge['from'], edge['to'])
        
        # Add new nodes with connections
        for node_data in modifications.get('add_nodes', []):
            node = node_data['node']
            self.G.add_node(node)
            
            # Add connections
            for conn in node_data.get('connections', []):
                if conn['direction'] == 'from':
                    self.G.add_edge(conn['node'], node)
                else:
                    self.G.add_edge(node, conn['node'])


# Example usage
if __name__ == "__main__":
    # Initialize controller
    controller = WaterGateController(
        structure_file='Structure.xlsx',
        requirement_file='SCADA Section Detailed Information 2024-01-15 V0.9 SL.xlsx'
    )
    
    # Visualize original network
    controller.visualize_network()
    
    # Run calculations
    operations, gate_info = controller.calculate_with_travel_time()
    
    # Export results
    # ... (export code here)