#!/usr/bin/env python3
"""
Water Gate Controller V2 - Updated for new SCADA format
Works with SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx
"""

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import math
import warnings
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple, Optional


class WaterGateControllerV2:
    """Updated Water Gate Controller for new SCADA format with travel time"""
    
    def __init__(self, scada_file: str, canal_geometry_file: Optional[str] = None):
        """
        Initialize controller with SCADA Excel file
        
        Args:
            scada_file: Path to SCADA Excel file
            canal_geometry_file: Optional canal geometry JSON
        """
        self.scada_file = scada_file
        self.canal_geometry = None
        
        # Load network structure from SCADA
        self.gate_info = {}
        self.G = self._build_network_from_scada()
        
        # Load canal geometry if provided
        if canal_geometry_file:
            self.load_canal_geometry(canal_geometry_file)
    
    def _build_network_from_scada(self) -> nx.DiGraph:
        """Build network from SCADA Excel file"""
        # Read the main sheet
        df = pd.read_excel(self.scada_file, sheet_name=0, header=1)
        
        # Extract gate valves and their connections
        G = nx.DiGraph()
        
        # Add source connection
        G.add_edge('S', 'M(0,0)')
        
        # Process each row
        prev_gate = None
        for idx, row in df.iterrows():
            if pd.notna(row.get('Gate Valve')):
                gate = row['Gate Valve']
                
                # Store gate information
                self.gate_info[gate] = {
                    'canal': row.get('Canal Name', ''),
                    'km': row.get('km', 0),
                    'area_rai': row.get('Area (Rais)', 0),
                    'q_max (m^3/s)': row.get('q_max (m^3/s)', 0),
                    'velocity': row.get('ความเร็วน้ำจากการทดลอง (m/s)', 1.0),
                    'distance_m': row.get('ระยะทาง (เมตร)', 0),
                    'Required Daily Water (cm)': row.get('Required Daily Water (cm)', 0),
                    'Required Daily Volume (m3)': row.get('Required Daily Volume (m3)', 0),
                    'zone': row.get('Zone', 1),
                    'indices': {
                        'i': row.get('i', 0),
                        'j': row.get('j', 0),
                        'k': row.get('k'),
                        'l': row.get('l'),
                        'm': row.get('m'),
                        'n': row.get('n')
                    }
                }
                
                # Build network based on indices
                i, j = int(row.get('i', 0)), int(row.get('j', 0))
                
                # Main canal progression (LMC)
                if prev_gate and row.get('Canal Name') == 'LMC':
                    G.add_edge(prev_gate, gate)
                
                # Handle branches based on indices
                if pd.notna(row.get('k')):  # Has branch
                    parent = f"M({i},{j})"
                    if parent in self.gate_info:
                        G.add_edge(parent, gate)
                
                prev_gate = gate if row.get('Canal Name') == 'LMC' else prev_gate
        
        # Add branch connections based on index patterns
        self._add_branch_connections(G)
        
        return G
    
    def _add_branch_connections(self, G):
        """Add branch canal connections based on index patterns"""
        # Pattern: M(i,j,k,...) branches from M(i,j)
        for gate in self.gate_info:
            parts = gate.strip('M()').split(',')
            if len(parts) > 2:  # Branch gate
                # Find parent gate
                parent_parts = parts[:-1]
                parent = f"M({','.join(parent_parts)})"
                if parent in self.gate_info:
                    G.add_edge(parent, gate)
                    self.gate_info[gate]['parent'] = parent
    
    def calculate_travel_time(self, from_node: str, to_node: str, 
                            flow_rate: float) -> float:
        """
        Calculate water travel time between nodes using distance and velocity
        
        Args:
            from_node: Starting node
            to_node: Ending node  
            flow_rate: Flow rate in m³/s
            
        Returns:
            Travel time in seconds
        """
        if to_node not in self.gate_info:
            return 0
        
        # Get distance from gate info
        distance = self.gate_info[to_node].get('distance_m', 0)
        if distance == 0:
            return 0
        
        # Use experimental velocity if available
        velocity = self.gate_info[to_node].get('velocity', 1.0)
        
        # If canal geometry provided, use it for more accurate calculation
        if self.canal_geometry:
            for section in self.canal_geometry.get('canal_sections', []):
                if section['from_node'] == from_node and section['to_node'] == to_node:
                    velocity = self._calculate_velocity(flow_rate, section['geometry'])
                    break
        
        # Travel time = Distance / Velocity
        travel_time = distance / velocity if velocity > 0 else 0
        
        return travel_time
    
    def _calculate_velocity(self, flow_rate: float, geometry: Dict) -> float:
        """Calculate velocity using Manning's equation"""
        # Implementation same as V1
        cs = geometry['cross_section']
        hp = geometry['hydraulic_params']
        
        if cs['type'] == 'trapezoidal':
            y = cs['depth_m'] * 0.7  # Assume 70% full
            b = cs['bottom_width_m']
            m = cs.get('side_slope', 1.0)
            
            area = y * (b + m * y)
            wetted_perimeter = b + 2 * y * math.sqrt(1 + m**2)
            R = area / wetted_perimeter
            
            n = hp['manning_n']
            S = hp['bed_slope']
            
            velocity = (1/n) * (R**(2/3)) * (S**0.5)
            
            # Adjust to match flow rate
            if abs(area * velocity - flow_rate) > 0.1:
                velocity = flow_rate / area
            
            return max(velocity, 0.1)
        
        return 1.0
    
    def load_canal_geometry(self, filename: str):
        """Load canal geometry from JSON file"""
        with open(filename, 'r') as f:
            self.canal_geometry = json.load(f)
    
    def visualize_network(self, highlight_nodes=None, save_path=None):
        """Visualize the network with hierarchical layout"""
        plt.figure(figsize=(20, 15))
        
        # Create hierarchical layout
        pos = nx.drawing.nx_pydot.graphviz_layout(self.G, prog='dot')
        
        # Node colors based on type and zone
        node_colors = []
        node_sizes = []
        
        for node in self.G.nodes():
            if node == 'S':
                node_colors.append('darkgreen')
                node_sizes.append(1000)
            elif node == 'T':
                node_colors.append('darkred')
                node_sizes.append(1000)
            elif highlight_nodes and node in highlight_nodes:
                node_colors.append('red')
                node_sizes.append(800)
            else:
                # Color by zone
                zone = self.gate_info.get(node, {}).get('zone', 0)
                zone_colors = ['skyblue', 'lightgreen', 'lightcoral', 
                              'lightyellow', 'lightpink', 'lightgray']
                node_colors.append(zone_colors[zone % len(zone_colors)])
                node_sizes.append(500)
        
        # Draw network
        nx.draw(self.G, pos, node_color=node_colors, node_size=node_sizes,
                with_labels=True, font_size=8, arrowsize=10)
        
        # Add title
        plt.title("Munbon Irrigation Network Structure\n(Updated from SCADA 2025-07-13)")
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()
    
    def get_network_summary(self):
        """Get summary of network structure"""
        summary = {
            'total_nodes': len(self.G.nodes()),
            'total_edges': len(self.G.edges()),
            'gates_by_zone': {},
            'gates_by_canal': {},
            'total_area_rai': 0,
            'total_required_volume': 0
        }
        
        for gate, info in self.gate_info.items():
            # By zone
            zone = info.get('zone', 'Unknown')
            if zone not in summary['gates_by_zone']:
                summary['gates_by_zone'][zone] = []
            summary['gates_by_zone'][zone].append(gate)
            
            # By canal
            canal = info.get('canal', 'Unknown')
            if canal not in summary['gates_by_canal']:
                summary['gates_by_canal'][canal] = []
            summary['gates_by_canal'][canal].append(gate)
            
            # Totals
            summary['total_area_rai'] += info.get('area_rai', 0) or 0
            summary['total_required_volume'] += info.get('Required Daily Volume (m3)', 0) or 0
        
        return summary
    
    def export_network_to_json(self, filename: str):
        """Export network structure to JSON"""
        network_data = {
            'nodes': list(self.G.nodes()),
            'edges': list(self.G.edges()),
            'gate_info': self.gate_info,
            'summary': self.get_network_summary()
        }
        
        with open(filename, 'w') as f:
            json.dump(network_data, f, indent=2)
        
        print(f"Network exported to {filename}")
    
    def run_optimization(self):
        """Run water distribution optimization with travel time"""
        # Initialize working graph
        working_G, gate_info = self._initialize_working_graph()
        
        operations = []
        water_arrival_times = {'S': 0}
        steps = 1
        
        while True:
            print(f'\nStep {steps}')
            
            # Run max flow
            flow_value, flow_dict = nx.algorithms.flow.maximum_flow(
                working_G, 'S', 'T'
            )
            
            if flow_value == 0:
                break
            
            # Calculate operations with travel time
            filled_area = {}
            
            for u in flow_dict:
                for v in flow_dict[u]:
                    if flow_dict[u][v] > 0 and v != 'T':
                        # Calculate travel time
                        travel_time = self.calculate_travel_time(u, v, flow_dict[u][v])
                        
                        # Update arrival time
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
            
            # Calculate time step
            time_step = min([
                filled_area[u]['fill_time'] + filled_area[u]['delay']
                for u in filled_area
            ])
            
            minute_step = math.ceil(time_step / 60)
            print(f'{minute_step} mins (including travel time)')
            
            # Store operations
            operations.append({
                'step': steps,
                'minute_step': minute_step,
                'flow_dict': flow_dict,
                'water_arrival_times': water_arrival_times.copy(),
                'filled_areas': filled_area
            })
            
            # Update gates
            self._update_gates(flow_dict, gate_info, minute_step, filled_area)
            
            # Update graph
            working_G = self._update_working_graph(gate_info)
            
            steps += 1
            
            if len(working_G.nodes) == 0:
                break
        
        return operations
    
    def _initialize_working_graph(self):
        """Initialize working graph for optimization"""
        # Create copy of gate info
        gate_info = self.gate_info.copy()
        
        # Find gates that need water
        gates_needing_water = [
            g for g, info in gate_info.items()
            if info.get('Required Daily Volume (m3)', 0) > 0
        ]
        
        # Find all gates that need to be open
        all_open_gates = set()
        for g in gates_needing_water:
            try:
                path = nx.shortest_path(self.G, 'S', g)
                all_open_gates.update(path)
            except nx.NetworkXNoPath:
                print(f"Warning: No path from S to {g}")
        
        # Create subgraph
        current_G = self.G.subgraph(all_open_gates)
        
        # Create working graph with capacities
        working_G = nx.DiGraph()
        working_G.add_nodes_from(current_G.nodes())
        
        for u, v in current_G.edges():
            capacity = gate_info.get(v, {}).get('q_max (m^3/s)', 10)
            if capacity > 0:
                working_G.add_edge(u, v, capacity=capacity)
        
        # Add sink connections
        for g in gates_needing_water:
            if g in working_G:
                working_G.add_edge(g, 'T')
        
        return working_G, gate_info
    
    def _update_gates(self, flow_dict, gate_info, minute_step, filled_area):
        """Update gate requirements after time step"""
        for u in filled_area:
            volume_delivered = minute_step * 60 * filled_area[u]['q_max']
            remaining = gate_info[u].get('Required Daily Volume (m3)', 0) - volume_delivered
            gate_info[u]['Required Daily Volume (m3)'] = max(0, remaining)
            print(f'Fill Area: {u}, Volume: {round(volume_delivered, 0)} m³')
    
    def _update_working_graph(self, gate_info):
        """Update working graph based on remaining requirements"""
        gates_needing_water = [
            g for g, info in gate_info.items()
            if info.get('Required Daily Volume (m3)', 0) > 0
        ]
        
        if not gates_needing_water:
            return nx.DiGraph()
        
        # Find all open gates
        all_open_gates = set()
        for g in gates_needing_water:
            try:
                path = nx.shortest_path(self.G, 'S', g)
                all_open_gates.update(path)
            except nx.NetworkXNoPath:
                continue
        
        # Create new working graph
        current_G = self.G.subgraph(all_open_gates)
        working_G = nx.DiGraph()
        working_G.add_nodes_from(current_G.nodes())
        
        for u, v in current_G.edges():
            capacity = gate_info.get(v, {}).get('q_max (m^3/s)', 10)
            if capacity > 0:
                working_G.add_edge(u, v, capacity=capacity)
        
        # Add sink connections
        for g in gates_needing_water:
            if g in working_G:
                working_G.add_edge(g, 'T')
        
        return working_G


# Example usage
if __name__ == "__main__":
    # Initialize controller with new SCADA file
    controller = WaterGateControllerV2(
        scada_file="/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    )
    
    # Get network summary
    summary = controller.get_network_summary()
    print("\n=== Network Summary ===")
    print(f"Total nodes: {summary['total_nodes']}")
    print(f"Total edges: {summary['total_edges']}")
    print(f"Total area: {summary['total_area_rai']} rai")
    print(f"Total required volume: {summary['total_required_volume']} m³")
    
    print("\nGates by zone:")
    for zone, gates in summary['gates_by_zone'].items():
        print(f"  Zone {zone}: {len(gates)} gates")
    
    # Visualize network
    controller.visualize_network(save_path='updated_network.png')
    
    # Export network structure
    controller.export_network_to_json('network_structure.json')
    
    # Run optimization
    print("\n=== Running Optimization ===")
    operations = controller.run_optimization()