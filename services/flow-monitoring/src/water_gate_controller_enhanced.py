#!/usr/bin/env python3
"""
Enhanced Water Gate Controller with Proper Gate Hydraulics
Integrates gate-specific flow calculations with network control
"""

import numpy as np
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from water_gate_controller_fixed import WaterGateControllerFixed
from gate_hydraulics import (
    GateHydraulics, GateProperties, HydraulicConditions, 
    GateType, FlowRegime
)

class WaterGateControllerEnhanced(WaterGateControllerFixed):
    """Water gate controller with realistic gate hydraulics"""
    
    def __init__(self, network_file: str, geometry_file: str = None, gate_config_file: str = None):
        """Initialize with network, geometry, and gate configurations"""
        
        # Initialize parent class
        super().__init__(network_file, geometry_file)
        
        # Initialize gate hydraulics calculator
        self.gate_hydraulics = GateHydraulics()
        
        # Load or estimate gate properties
        self.gate_properties = {}
        if gate_config_file:
            self._load_gate_config(gate_config_file)
        else:
            self._estimate_gate_properties()
        
        # Water level tracking
        self.water_levels = {}
        self._initialize_water_levels()
        
    def _load_gate_config(self, config_file: str):
        """Load gate configuration from file"""
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        for gate_id, gate_data in config.get('gates', {}).items():
            gate_type = GateType(gate_data.get('type', 'sluice_gate'))
            
            self.gate_properties[gate_id] = GateProperties(
                gate_id=gate_id,
                gate_type=gate_type,
                width_m=gate_data['width_m'],
                height_m=gate_data['height_m'],
                sill_elevation_m=gate_data.get('sill_elevation_m', 0.0),
                discharge_coefficient=gate_data.get('cd', 
                    self.gate_hydraulics.default_cd[gate_type]),
                contraction_coefficient=gate_data.get('cc',
                    self.gate_hydraulics.default_cc[gate_type]),
                max_opening_m=gate_data.get('max_opening_m', gate_data['height_m'] * 0.8)
            )
    
    def _estimate_gate_properties(self):
        """Estimate gate properties from network data"""
        
        # Default gate type assignment based on position
        for gate_id, gate_info in self.gates.items():
            q_max = gate_info.get('q_max', 5.0)
            if isinstance(q_max, float) and np.isnan(q_max):
                q_max = 5.0
            
            # Determine gate type based on position and name
            if gate_id == 'M(0,0)':
                # Main inlet - large sluice gate
                gate_type = GateType.SLUICE_GATE
            elif 'RMC' in gate_info.get('canal', ''):
                # Right Main Canal - radial gates
                gate_type = GateType.RADIAL_GATE
            elif any(x in gate_id for x in ['1,0', '1,1', '1,2', '1,3', '1,4']):
                # Lateral gates - smaller sluice gates
                gate_type = GateType.SLUICE_GATE
            elif 'FTO' in gate_info.get('canal', ''):
                # Farm turnout - butterfly valves
                gate_type = GateType.BUTTERFLY_VALVE
            else:
                # Default to sluice gate
                gate_type = GateType.SLUICE_GATE
            
            # Estimate properties
            self.gate_properties[gate_id] = self.gate_hydraulics.estimate_gate_properties(
                gate_id, q_max, gate_type
            )
    
    def _initialize_water_levels(self):
        """Initialize water levels at each node"""
        
        # Set initial water levels based on typical operations
        # Main reservoir level
        reservoir_level = 221.0  # m MSL (from dam elevation)
        
        for gate_id in self.gates:
            # Initialize with estimates
            if gate_id == 'M(0,0)':
                # Outlet from reservoir
                upstream = reservoir_level
                downstream = reservoir_level - 2.0  # 2m drop
            else:
                # Estimate based on distance from source
                # Assume 0.1m drop per km
                path = self.find_path('M(0,0)', gate_id)
                if path:
                    distance_km = len(path) * 0.5  # Rough estimate
                    upstream = reservoir_level - distance_km * 0.1
                    downstream = upstream - 0.5  # 0.5m local drop
                else:
                    upstream = reservoir_level - 5.0
                    downstream = upstream - 0.5
            
            self.water_levels[gate_id] = {
                'upstream': upstream,
                'downstream': downstream,
                'updated': datetime.now()
            }
    
    def calculate_gate_flow_realistic(self, gate_id: str, gate_opening_m: float) -> Dict:
        """Calculate flow through gate using proper hydraulics"""
        
        if gate_id not in self.gate_properties:
            # Fallback to simple calculation
            return {
                'flow_rate_m3s': gate_opening_m * 5.0,  # Simple linear
                'flow_regime': 'unknown',
                'velocity_ms': 1.0,
                'warning': 'Gate properties not defined'
            }
        
        gate = self.gate_properties[gate_id]
        levels = self.water_levels.get(gate_id, {})
        
        # Create hydraulic conditions
        conditions = HydraulicConditions(
            upstream_water_level_m=levels.get('upstream', 220.0) - gate.sill_elevation_m,
            downstream_water_level_m=levels.get('downstream', 219.0) - gate.sill_elevation_m,
            gate_opening_m=gate_opening_m
        )
        
        # Calculate flow
        result = self.gate_hydraulics.calculate_gate_flow(gate, conditions)
        
        # Update gate state
        self.gate_states[gate_id].update({
            'flow_rate': result['flow_rate_m3s'],
            'flow_regime': result['flow_regime'],
            'velocity': result['velocity_ms'],
            'opening': gate_opening_m,
            'opening_percent': result['gate_opening_percent']
        })
        
        return result
    
    def open_gate_realistic(self, gate_id: str, opening_percent: float,
                          upstream_level: float = None, downstream_level: float = None):
        """Open gate to specified percentage with realistic flow calculation"""
        
        if gate_id not in self.gates:
            raise ValueError(f"Gate {gate_id} not found")
        
        # Update water levels if provided
        if upstream_level is not None:
            self.water_levels[gate_id]['upstream'] = upstream_level
        if downstream_level is not None:
            self.water_levels[gate_id]['downstream'] = downstream_level
        
        # Convert percentage to actual opening
        gate = self.gate_properties.get(gate_id)
        if gate:
            gate_opening_m = gate.max_opening_m * (opening_percent / 100.0)
        else:
            gate_opening_m = 1.0 * (opening_percent / 100.0)  # Default 1m max
        
        # Calculate realistic flow
        flow_result = self.calculate_gate_flow_realistic(gate_id, gate_opening_m)
        
        # Update network flows
        self.current_flows[gate_id] = flow_result['flow_rate_m3s']
        
        # Propagate water level changes downstream
        self._propagate_water_levels(gate_id, flow_result['flow_rate_m3s'])
        
        return {
            'gate_id': gate_id,
            'opening_percent': opening_percent,
            'opening_m': gate_opening_m,
            'flow_rate_m3s': flow_result['flow_rate_m3s'],
            'flow_regime': flow_result['flow_regime'],
            'velocity_ms': flow_result['velocity_ms'],
            'upstream_level': self.water_levels[gate_id]['upstream'],
            'downstream_level': self.water_levels[gate_id]['downstream']
        }
    
    def calculate_gate_opening_for_flow(self, gate_id: str, target_flow_m3s: float) -> Dict:
        """Calculate required gate opening to achieve target flow"""
        
        if gate_id not in self.gate_properties:
            # Simple linear estimate
            return {
                'gate_id': gate_id,
                'target_flow_m3s': target_flow_m3s,
                'required_opening_percent': min(100, target_flow_m3s / 5.0 * 100),
                'warning': 'Using simplified calculation'
            }
        
        gate = self.gate_properties[gate_id]
        levels = self.water_levels.get(gate_id, {})
        
        # Create hydraulic conditions
        conditions = HydraulicConditions(
            upstream_water_level_m=levels.get('upstream', 220.0) - gate.sill_elevation_m,
            downstream_water_level_m=levels.get('downstream', 219.0) - gate.sill_elevation_m,
            gate_opening_m=1.0  # Initial guess
        )
        
        # Calculate required opening
        required_opening_m = self.gate_hydraulics.calculate_required_opening(
            gate, target_flow_m3s, conditions
        )
        
        required_percent = (required_opening_m / gate.max_opening_m) * 100
        
        return {
            'gate_id': gate_id,
            'target_flow_m3s': target_flow_m3s,
            'required_opening_m': required_opening_m,
            'required_opening_percent': required_percent,
            'max_opening_m': gate.max_opening_m,
            'achievable': required_percent <= 100
        }
    
    def _propagate_water_levels(self, source_gate: str, flow_rate: float):
        """Propagate water level changes through network"""
        
        # Get downstream gates
        downstream_gates = self.get_downstream_gates(source_gate)
        
        for gate in downstream_gates:
            # Find canal section
            key = f"{source_gate}->{gate}"
            if key in self.canal_sections:
                section = self.canal_sections[key]
                
                # Calculate normal depth for this flow
                normal_depth = self.calculate_normal_depth(flow_rate, section)
                
                # Update downstream water level
                # New upstream level for downstream gate = 
                # downstream level of upstream gate + normal depth
                source_downstream = self.water_levels[source_gate]['downstream']
                
                self.water_levels[gate]['upstream'] = source_downstream + normal_depth
                
                # Assume 0.3m drop through gate
                self.water_levels[gate]['downstream'] = self.water_levels[gate]['upstream'] - 0.3
    
    def simulate_network_operation(self, gate_operations: List[Dict]) -> Dict:
        """
        Simulate network-wide gate operations with realistic hydraulics
        
        gate_operations: List of {'gate_id': str, 'opening_percent': float, 'time': datetime}
        """
        
        results = {
            'operations': [],
            'network_flows': {},
            'water_balance': {},
            'warnings': []
        }
        
        # Sort operations by time
        sorted_ops = sorted(gate_operations, key=lambda x: x.get('time', datetime.now()))
        
        for operation in sorted_ops:
            gate_id = operation['gate_id']
            opening = operation['opening_percent']
            
            # Open gate with realistic calculation
            result = self.open_gate_realistic(gate_id, opening)
            results['operations'].append(result)
            
            # Check for issues
            if result['velocity_ms'] > 3.0:
                results['warnings'].append(
                    f"High velocity at {gate_id}: {result['velocity_ms']:.1f} m/s - Risk of erosion"
                )
            
            if result['flow_regime'] == 'submerged_flow':
                results['warnings'].append(
                    f"Submerged flow at {gate_id} - Reduced efficiency"
                )
        
        # Calculate final network state
        results['network_flows'] = self.current_flows.copy()
        results['water_balance'] = self.calculate_network_water_balance()
        
        return results
    
    def export_gate_specifications(self) -> Dict:
        """Export all gate specifications for documentation"""
        
        specs = {
            'gates': {},
            'summary': {
                'total_gates': len(self.gate_properties),
                'gate_types': {},
                'total_capacity': 0
            }
        }
        
        for gate_id, gate in self.gate_properties.items():
            gate_info = self.gates.get(gate_id, {})
            
            specs['gates'][gate_id] = {
                'type': gate.gate_type.value,
                'dimensions': {
                    'width_m': gate.width_m,
                    'height_m': gate.height_m,
                    'max_opening_m': gate.max_opening_m
                },
                'hydraulic_properties': {
                    'discharge_coefficient': gate.discharge_coefficient,
                    'contraction_coefficient': gate.contraction_coefficient,
                    'sill_elevation_m': gate.sill_elevation_m
                },
                'location': {
                    'canal': gate_info.get('canal', 'Unknown'),
                    'zone': gate_info.get('zone', 0),
                    'km': gate_info.get('km', 'Unknown')
                },
                'capacity': {
                    'q_max_m3s': gate_info.get('q_max', 0),
                    'area_irrigated': gate_info.get('area', 0)
                }
            }
            
            # Update summary
            gate_type = gate.gate_type.value
            specs['summary']['gate_types'][gate_type] = \
                specs['summary']['gate_types'].get(gate_type, 0) + 1
            specs['summary']['total_capacity'] += gate_info.get('q_max', 0)
        
        return specs


# Example usage
if __name__ == "__main__":
    # Initialize enhanced controller
    controller = WaterGateControllerEnhanced(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== ENHANCED WATER GATE CONTROLLER ===")
    print(f"Total gates with hydraulic models: {len(controller.gate_properties)}")
    
    # Example 1: Open main gate to 50%
    print("\n1. Opening main gate M(0,0) to 50%:")
    result = controller.open_gate_realistic('M(0,0)', 50, 
                                          upstream_level=221.0, 
                                          downstream_level=219.0)
    print(f"   Flow rate: {result['flow_rate_m3s']:.2f} m³/s")
    print(f"   Flow regime: {result['flow_regime']}")
    print(f"   Velocity: {result['velocity_ms']:.2f} m/s")
    
    # Example 2: Calculate required opening for target flow
    print("\n2. Calculate opening for 6 m³/s at M(0,0):")
    required = controller.calculate_gate_opening_for_flow('M(0,0)', 6.0)
    print(f"   Required opening: {required['required_opening_percent']:.1f}%")
    print(f"   Required opening: {required['required_opening_m']:.2f} m")
    
    # Example 3: Simulate multiple gate operations
    print("\n3. Simulating network operation:")
    operations = [
        {'gate_id': 'M(0,0)', 'opening_percent': 60, 'time': datetime.now()},
        {'gate_id': 'M(0,2)', 'opening_percent': 40, 'time': datetime.now()},
        {'gate_id': 'M(0,3)', 'opening_percent': 30, 'time': datetime.now()}
    ]
    
    sim_result = controller.simulate_network_operation(operations)
    
    print("\nOperation Results:")
    for op in sim_result['operations']:
        print(f"   {op['gate_id']}: {op['flow_rate_m3s']:.2f} m³/s @ {op['opening_percent']}% open")
    
    if sim_result['warnings']:
        print("\nWarnings:")
        for warning in sim_result['warnings']:
            print(f"   ⚠️  {warning}")
    
    # Example 4: Export gate specifications
    print("\n4. Gate Type Summary:")
    specs = controller.export_gate_specifications()
    for gate_type, count in specs['summary']['gate_types'].items():
        print(f"   {gate_type}: {count} gates")
    print(f"   Total capacity: {specs['summary']['total_capacity']:.1f} m³/s")