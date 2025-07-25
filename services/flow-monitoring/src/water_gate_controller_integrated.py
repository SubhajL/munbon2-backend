#!/usr/bin/env python3
"""
Enhanced Water Gate Controller with Network Integration
Integrates with Munbon irrigation network structure and canal geometry
"""

import numpy as np
import json
from typing import Dict, List, Tuple, Optional
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CanalSection:
    """Represents a canal section with geometry"""
    section_id: str
    from_node: str
    to_node: str
    length_m: float
    bottom_width_m: float
    depth_m: float
    side_slope: float
    manning_n: float
    bed_slope: float
    q_max: float = None
    q_min: float = None

class WaterGateControllerIntegrated:
    """Enhanced water gate controller with network and geometry integration"""
    
    def __init__(self, network_file: str, geometry_file: str = None):
        """Initialize controller with network structure and optional geometry"""
        
        # Load network structure
        with open(network_file, 'r') as f:
            self.network = json.load(f)
        
        self.gates = self.network['gates']
        self.edges = self.network['edges']
        
        # Build adjacency structures
        self._build_adjacency()
        
        # Load canal geometry if provided
        self.canal_sections = {}
        if geometry_file:
            self._load_canal_geometry(geometry_file)
        
        # Gate states
        self.gate_states = {}
        self._initialize_gate_states()
        
        # Flow tracking
        self.current_flows = {}
        self.travel_times = {}
        
    def _build_adjacency(self):
        """Build adjacency lists for network traversal"""
        self.children = {}
        self.parents = {}
        
        for parent, child in self.edges:
            # Children
            if parent not in self.children:
                self.children[parent] = []
            self.children[parent].append(child)
            
            # Parents
            if child not in self.parents:
                self.parents[child] = []
            self.parents[child].append(parent)
    
    def _load_canal_geometry(self, geometry_file: str):
        """Load canal geometry data"""
        with open(geometry_file, 'r') as f:
            data = json.load(f)
        
        for section in data.get('canal_sections', []):
            # Handle both formats (template and actual data)
            if 'section_id' in section:
                # Template format
                cs = CanalSection(
                    section_id=section['section_id'],
                    from_node=section['from_node'],
                    to_node=section['to_node'],
                    length_m=section['geometry']['length_m'],
                    bottom_width_m=section['geometry']['cross_section']['bottom_width_m'],
                    depth_m=section['geometry']['cross_section']['depth_m'],
                    side_slope=section['geometry']['cross_section'].get('side_slope', 1.0),
                    manning_n=section['geometry']['hydraulic_params']['manning_n'],
                    bed_slope=section['geometry']['hydraulic_params']['bed_slope'],
                    q_max=section.get('design_flow', {}).get('q_max_m3s'),
                    q_min=section.get('design_flow', {}).get('q_min_m3s')
                )
            else:
                # Actual data format
                section_id = f"{section['canal_name']}_{section['section_no']}"
                cs = CanalSection(
                    section_id=section_id,
                    from_node=section['from_node'],
                    to_node=section['to_node'],
                    length_m=section['geometry']['length_m'],
                    bottom_width_m=section['geometry']['cross_section']['bottom_width_m'],
                    depth_m=section['geometry']['cross_section']['depth_m'],
                    side_slope=section['geometry']['cross_section'].get('side_slope', 1.0),
                    manning_n=section['geometry']['hydraulic_params']['manning_n'],
                    bed_slope=section['geometry']['hydraulic_params']['bed_slope'],
                    q_max=section['geometry']['hydraulic_params'].get('q_max'),
                    q_min=None
                )
            
            key = f"{cs.from_node}->{cs.to_node}"
            self.canal_sections[key] = cs
    
    def _initialize_gate_states(self):
        """Initialize all gates to closed state"""
        for gate_id in self.gates:
            self.gate_states[gate_id] = {
                'opening': 0.0,  # 0 = closed, 1 = fully open
                'flow_rate': 0.0,
                'upstream_level': 0.0,
                'downstream_level': 0.0,
                'last_updated': datetime.now()
            }
    
    def calculate_velocity(self, flow_rate: float, canal_section: CanalSection) -> float:
        """Calculate water velocity using Manning's equation"""
        
        # Calculate wetted area and perimeter for trapezoidal section
        y = canal_section.depth_m  # Assume normal depth
        b = canal_section.bottom_width_m
        m = canal_section.side_slope
        
        # Area = b*y + m*y^2
        area = b * y + m * y * y
        
        # Wetted perimeter = b + 2*y*sqrt(1 + m^2)
        perimeter = b + 2 * y * np.sqrt(1 + m * m)
        
        # Hydraulic radius
        R = area / perimeter
        
        # Manning's equation: V = (1/n) * R^(2/3) * S^(1/2)
        velocity = (1 / canal_section.manning_n) * (R ** (2/3)) * (canal_section.bed_slope ** 0.5)
        
        # Verify against continuity equation
        calculated_area = flow_rate / velocity if velocity > 0 else area
        
        return velocity
    
    def calculate_travel_time(self, from_node: str, to_node: str, flow_rate: float) -> float:
        """Calculate water travel time between nodes"""
        
        key = f"{from_node}->{to_node}"
        
        if key not in self.canal_sections:
            # No geometry data - use default estimate
            # Assume 0.5 m/s average velocity
            default_velocity = 0.5
            # Estimate distance from km values if available
            from_info = self.gates.get(from_node, {})
            to_info = self.gates.get(to_node, {})
            
            from_km = from_info.get('km', '0+000')
            to_km = to_info.get('km', '0+000')
            
            try:
                # Parse km format like "6+880"
                from_dist = float(from_km.split('+')[0]) * 1000 + float(from_km.split('+')[1])
                to_dist = float(to_km.split('+')[0]) * 1000 + float(to_km.split('+')[1])
                distance = abs(to_dist - from_dist)
            except:
                distance = 1000  # Default 1 km
            
            return distance / default_velocity
        
        # Use actual geometry
        section = self.canal_sections[key]
        velocity = self.calculate_velocity(flow_rate, section)
        
        # Travel time = Distance / Velocity
        travel_time = section.length_m / velocity if velocity > 0 else 0
        
        return travel_time
    
    def find_path(self, start_node: str, end_node: str) -> List[str]:
        """Find path between two nodes using BFS"""
        
        if start_node not in self.gates or end_node not in self.gates:
            return []
        
        # BFS
        queue = [(start_node, [start_node])]
        visited = set()
        
        while queue:
            node, path = queue.pop(0)
            
            if node == end_node:
                return path
            
            if node in visited:
                continue
            
            visited.add(node)
            
            # Check children
            for child in self.children.get(node, []):
                if child not in visited:
                    queue.append((child, path + [child]))
        
        return []
    
    def calculate_cumulative_travel_time(self, path: List[str], flow_rate: float) -> float:
        """Calculate total travel time along a path"""
        
        total_time = 0
        
        for i in range(len(path) - 1):
            travel_time = self.calculate_travel_time(path[i], path[i+1], flow_rate)
            total_time += travel_time
            
            # Store individual segment times
            key = f"{path[i]}->{path[i+1]}"
            self.travel_times[key] = {
                'time_seconds': travel_time,
                'time_minutes': travel_time / 60,
                'flow_rate': flow_rate,
                'calculated_at': datetime.now()
            }
        
        return total_time
    
    def open_gate(self, gate_id: str, opening: float, upstream_level: float = None):
        """Open a gate to specified opening (0-1)"""
        
        if gate_id not in self.gates:
            raise ValueError(f"Gate {gate_id} not found")
        
        # Update gate state
        self.gate_states[gate_id]['opening'] = np.clip(opening, 0, 1)
        self.gate_states[gate_id]['last_updated'] = datetime.now()
        
        if upstream_level is not None:
            self.gate_states[gate_id]['upstream_level'] = upstream_level
        
        # Calculate flow based on opening and head difference
        gate_info = self.gates[gate_id]
        q_max = gate_info.get('q_max', 0)
        
        if q_max and not np.isnan(q_max):
            # Simple linear relationship for now
            flow_rate = q_max * opening
            self.gate_states[gate_id]['flow_rate'] = flow_rate
            self.current_flows[gate_id] = flow_rate
        
        return self.gate_states[gate_id]
    
    def close_gate(self, gate_id: str):
        """Close a gate"""
        return self.open_gate(gate_id, 0.0)
    
    def get_downstream_gates(self, gate_id: str) -> List[str]:
        """Get all gates downstream of a given gate"""
        return self.children.get(gate_id, [])
    
    def get_upstream_gates(self, gate_id: str) -> List[str]:
        """Get all gates upstream of a given gate"""
        return self.parents.get(gate_id, [])
    
    def propagate_flow_with_delay(self, source_gate: str, flow_rate: float) -> Dict[str, float]:
        """Calculate when flow changes will reach each downstream gate"""
        
        arrival_times = {}
        
        # BFS to explore all downstream paths
        queue = [(source_gate, 0)]  # (gate, cumulative_time)
        visited = set()
        
        while queue:
            current_gate, current_time = queue.pop(0)
            
            if current_gate in visited:
                continue
            
            visited.add(current_gate)
            arrival_times[current_gate] = current_time
            
            # Process all downstream gates
            for child in self.get_downstream_gates(current_gate):
                if child not in visited:
                    # Calculate travel time to this child
                    travel_time = self.calculate_travel_time(current_gate, child, flow_rate)
                    queue.append((child, current_time + travel_time))
        
        return arrival_times
    
    def simulate_gate_operation(self, gate_id: str, opening: float, duration_hours: float):
        """Simulate gate operation and predict downstream impacts"""
        
        # Open the gate
        gate_state = self.open_gate(gate_id, opening)
        flow_rate = gate_state['flow_rate']
        
        # Calculate arrival times
        arrival_times = self.propagate_flow_with_delay(gate_id, flow_rate)
        
        # Create timeline of events
        timeline = []
        start_time = datetime.now()
        
        for gate, delay_seconds in arrival_times.items():
            arrival_time = start_time + timedelta(seconds=delay_seconds)
            timeline.append({
                'gate': gate,
                'event': 'flow_arrival',
                'time': arrival_time,
                'delay_minutes': delay_seconds / 60,
                'expected_flow': flow_rate if gate != gate_id else 0
            })
        
        # Sort by time
        timeline.sort(key=lambda x: x['time'])
        
        return {
            'source_gate': gate_id,
            'flow_rate': flow_rate,
            'duration_hours': duration_hours,
            'timeline': timeline,
            'total_volume': flow_rate * duration_hours * 3600  # m³
        }
    
    def calculate_network_water_balance(self) -> Dict:
        """Calculate water balance across the network"""
        
        total_inflow = 0
        total_outflow = 0
        zone_flows = {}
        
        for gate_id, state in self.gate_states.items():
            flow = state.get('flow_rate', 0)
            gate_info = self.gates.get(gate_id, {})
            zone = gate_info.get('zone', 0)
            
            if zone not in zone_flows:
                zone_flows[zone] = {'inflow': 0, 'outflow': 0}
            
            # Determine if inflow or outflow based on position
            if gate_id == 'M(0,0)':  # Main inlet
                total_inflow += flow
            elif len(self.get_downstream_gates(gate_id)) == 0:  # Terminal gates
                total_outflow += flow
                zone_flows[zone]['outflow'] += flow
            else:
                zone_flows[zone]['inflow'] += flow
        
        balance = {
            'total_inflow': total_inflow,
            'total_outflow': total_outflow,
            'balance': total_inflow - total_outflow,
            'efficiency': (total_outflow / total_inflow * 100) if total_inflow > 0 else 0,
            'zone_flows': zone_flows,
            'timestamp': datetime.now()
        }
        
        return balance
    
    def optimize_gate_operations(self, demand_by_zone: Dict[int, float]) -> List[Dict]:
        """Optimize gate operations to meet zone demands"""
        
        recommendations = []
        
        # Start from source and work downstream
        # This is a simplified optimization - real implementation would use
        # linear programming or other optimization techniques
        
        for zone, demand in demand_by_zone.items():
            # Find gates serving this zone
            zone_gates = [g for g, info in self.gates.items() 
                         if info.get('zone') == zone]
            
            # Calculate required flows
            for gate in zone_gates:
                gate_info = self.gates[gate]
                q_max = gate_info.get('q_max', 0)
                
                if q_max and not np.isnan(q_max):
                    # Simple proportional control
                    required_opening = min(demand / q_max, 1.0) if q_max > 0 else 0
                    
                    recommendations.append({
                        'gate': gate,
                        'zone': zone,
                        'current_opening': self.gate_states[gate]['opening'],
                        'recommended_opening': required_opening,
                        'expected_flow': q_max * required_opening,
                        'demand': demand
                    })
        
        return recommendations
    
    def export_network_state(self) -> Dict:
        """Export current network state for monitoring"""
        
        state = {
            'timestamp': datetime.now().isoformat(),
            'gates': {},
            'flows': self.current_flows,
            'travel_times': self.travel_times,
            'water_balance': self.calculate_network_water_balance()
        }
        
        for gate_id, gate_state in self.gate_states.items():
            gate_info = self.gates.get(gate_id, {})
            state['gates'][gate_id] = {
                'zone': gate_info.get('zone'),
                'canal': gate_info.get('canal'),
                'opening': gate_state['opening'],
                'flow_rate': gate_state['flow_rate'],
                'upstream_level': gate_state['upstream_level'],
                'downstream_level': gate_state['downstream_level'],
                'last_updated': gate_state['last_updated'].isoformat()
            }
        
        return state


# Example usage
if __name__ == "__main__":
    # Initialize controller
    controller = WaterGateControllerIntegrated(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("Munbon Water Gate Controller Initialized")
    print(f"Total Gates: {len(controller.gates)}")
    print(f"Total Connections: {len(controller.edges)}")
    
    # Example: Open main gate and simulate flow propagation
    print("\n=== Simulating Gate Operation ===")
    result = controller.simulate_gate_operation('M(0,0)', opening=0.8, duration_hours=4)
    
    print(f"\nSource Gate: {result['source_gate']}")
    print(f"Flow Rate: {result['flow_rate']:.2f} m³/s")
    print(f"Total Volume: {result['total_volume']:.0f} m³")
    
    print("\nFlow Arrival Timeline:")
    for event in result['timeline'][:10]:  # Show first 10
        print(f"  {event['gate']}: {event['delay_minutes']:.1f} minutes")
    
    # Calculate travel time example
    print("\n=== Travel Time Calculations ===")
    path = controller.find_path('M(0,0)', 'M(0,12)')
    if path:
        print(f"Path from M(0,0) to M(0,12): {' -> '.join(path)}")
        total_time = controller.calculate_cumulative_travel_time(path, flow_rate=5.0)
        print(f"Total travel time: {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)")
    
    # Water balance
    print("\n=== Water Balance ===")
    balance = controller.calculate_network_water_balance()
    print(f"Total Inflow: {balance['total_inflow']:.2f} m³/s")
    print(f"Total Outflow: {balance['total_outflow']:.2f} m³/s")
    print(f"Balance: {balance['balance']:.2f} m³/s")
    print(f"Efficiency: {balance['efficiency']:.1f}%")