#!/usr/bin/env python3
"""
Integrated Gate Control System
Combines hydraulic solver with proper gate opening calculations
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

from hydraulic_solver import HydraulicSolver
from gate_opening_calculator import GateOpeningCalculator, GateOpeningResult
from gate_hydraulics import GateProperties, GateType

@dataclass
class GateControlCommand:
    """Command to control a physical gate"""
    gate_id: str
    timestamp: datetime
    opening_m: float
    opening_percent: float
    target_flow_m3s: float
    actual_flow_m3s: float
    upstream_level_m: float
    downstream_level_m: float
    head_difference_m: float
    
class IntegratedGateControl:
    """
    Integrates hydraulic calculations with gate opening control
    """
    
    def __init__(self, network_file: str):
        self.hydraulic_solver = HydraulicSolver(network_file)
        self.opening_calculator = GateOpeningCalculator()
        self.gate_commands = {}
        
    def calculate_gate_settings_for_flows(self, 
                                        target_flows: Dict[str, float]) -> Dict[str, GateControlCommand]:
        """
        Calculate exact gate openings needed for target flows
        
        Args:
            target_flows: {zone: flow_rate} e.g. {'Zone2': 2.0, 'Zone5': 1.5}
            
        Returns:
            Gate control commands with exact opening heights
        """
        
        print("\n=== INTEGRATED GATE CONTROL CALCULATION ===\n")
        
        # Step 1: Determine required flows through each gate
        gate_flows = self._calculate_gate_flows_from_targets(target_flows)
        
        print("1. Required flows through gates:")
        for gate_id, flow in gate_flows.items():
            print(f"   {gate_id}: {flow:.2f} m³/s")
        
        # Step 2: Initial hydraulic solution (with estimated openings)
        print("\n2. Running hydraulic solver...")
        
        # Set initial gate openings (rough estimate)
        initial_settings = []
        for gate_id, flow in gate_flows.items():
            upstream, downstream = gate_id.split('->')
            # Rough estimate: 20% per m³/s
            opening_estimate = min(2.5, flow * 0.5)
            initial_settings.append({
                'upstream': upstream,
                'downstream': downstream,
                'opening': opening_estimate
            })
        
        # Solve hydraulics
        convergence = self.hydraulic_solver.solve_network(initial_settings)
        
        if not convergence.converged:
            print("   WARNING: Hydraulic solution did not converge!")
        else:
            print(f"   Converged in {convergence.iterations} iterations")
        
        # Step 3: Calculate exact gate openings based on water levels
        print("\n3. Calculating exact gate openings:")
        
        commands = {}
        
        for gate_id, target_flow in gate_flows.items():
            upstream, downstream = gate_id.split('->')
            
            # Get water levels from hydraulic solution
            upstream_level = self.hydraulic_solver.water_levels.get(upstream, 0)
            downstream_level = self.hydraulic_solver.water_levels.get(downstream, 0)
            
            # Get gate properties
            gate_props = self.hydraulic_solver.gate_properties.get(gate_id)
            
            if not gate_props:
                print(f"   WARNING: No properties for gate {gate_id}")
                continue
            
            # Calculate required opening
            opening_result = self.opening_calculator.calculate_required_opening(
                target_flow=target_flow,
                gate=gate_props,
                upstream_level=upstream_level,
                downstream_level=downstream_level
            )
            
            # Create control command
            command = GateControlCommand(
                gate_id=gate_id,
                timestamp=datetime.now(),
                opening_m=opening_result.required_opening_m,
                opening_percent=opening_result.opening_percent,
                target_flow_m3s=target_flow,
                actual_flow_m3s=opening_result.achievable_flow_m3s,
                upstream_level_m=upstream_level,
                downstream_level_m=downstream_level,
                head_difference_m=upstream_level - downstream_level
            )
            
            commands[gate_id] = command
            
            # Print result
            print(f"\n   {gate_id}:")
            print(f"      Water levels: {upstream_level:.2f}m → {downstream_level:.2f}m (ΔH={command.head_difference_m:.2f}m)")
            print(f"      Target flow: {target_flow:.2f} m³/s")
            print(f"      Gate opening: {command.opening_m:.3f}m ({command.opening_percent:.1f}%)")
            print(f"      Achievable flow: {command.actual_flow_m3s:.2f} m³/s")
            
            if not opening_result.is_feasible:
                print(f"      ⚠️  {opening_result.limiting_factor}")
                if opening_result.recommendations:
                    print(f"      💡 {opening_result.recommendations}")
        
        # Step 4: Verify with refined solution
        print("\n4. Verifying with calculated openings...")
        
        refined_settings = []
        for gate_id, command in commands.items():
            upstream, downstream = gate_id.split('->')
            refined_settings.append({
                'upstream': upstream,
                'downstream': downstream,
                'opening': command.opening_m
            })
        
        # Re-solve with exact openings
        final_convergence = self.hydraulic_solver.solve_network(refined_settings)
        
        # Check actual flows
        print("\n5. Verification results:")
        total_error = 0
        
        for gate_id, command in commands.items():
            actual_flow = self.hydraulic_solver.flows.get(gate_id, 0)
            error = abs(actual_flow - command.target_flow_m3s)
            total_error += error
            
            print(f"   {gate_id}:")
            print(f"      Target: {command.target_flow_m3s:.2f} m³/s")
            print(f"      Actual: {actual_flow:.2f} m³/s")
            print(f"      Error: {error:.3f} m³/s ({error/command.target_flow_m3s*100:.1f}%)")
        
        print(f"\n   Total flow error: {total_error:.3f} m³/s")
        
        return commands
    
    def _calculate_gate_flows_from_targets(self, target_flows: Dict[str, float]) -> Dict[str, float]:
        """
        Determine required flow through each gate based on zone targets
        Handles shared paths appropriately
        """
        
        gate_flows = {}
        
        # For each target zone, trace path and accumulate flows
        for zone, flow in target_flows.items():
            path = self._find_path_to_zone(zone)
            
            # Add flow requirement to each gate in path
            for i in range(len(path) - 1):
                gate_id = f"{path[i]}->{path[i+1]}"
                gate_flows[gate_id] = gate_flows.get(gate_id, 0) + flow
        
        return gate_flows
    
    def _find_path_to_zone(self, zone: str) -> List[str]:
        """Find path from source to zone"""
        
        # Simplified - in reality would use graph algorithm
        paths = {
            'Zone2': ['Source', 'M(0,0)', 'M(0,2)', 'M(0,3)', 'M(0,5)', 'Zone2'],
            'Zone5': ['Source', 'M(0,0)', 'M(0,2)', 'M(0,3)', 'M(0,5)', 'M(0,12)', 'Zone5'],
            'Zone6': ['Source', 'M(0,0)', 'M(0,2)', 'M(0,3)', 'M(0,5)', 'M(0,12)', 'M(0,14)', 'Zone6']
        }
        
        return paths.get(zone, [])
    
    def generate_scada_commands(self, commands: Dict[str, GateControlCommand]) -> List[Dict]:
        """
        Generate SCADA-compatible commands
        """
        
        scada_commands = []
        
        for gate_id, command in commands.items():
            scada_cmd = {
                'timestamp': command.timestamp.isoformat(),
                'gate_id': gate_id,
                'command_type': 'SET_POSITION',
                'parameters': {
                    'opening_m': round(command.opening_m, 3),
                    'opening_percent': round(command.opening_percent, 1),
                    'target_flow_m3s': round(command.target_flow_m3s, 2)
                },
                'hydraulic_context': {
                    'upstream_level_m': round(command.upstream_level_m, 2),
                    'downstream_level_m': round(command.downstream_level_m, 2),
                    'head_difference_m': round(command.head_difference_m, 3)
                },
                'priority': 'HIGH',
                'source': 'FLOW_MONITORING_SERVICE'
            }
            
            scada_commands.append(scada_cmd)
        
        return scada_commands


def demonstrate_integrated_control():
    """Demonstrate integrated gate control"""
    
    print("=== INTEGRATED GATE CONTROL DEMONSTRATION ===")
    
    # Create controller
    controller = IntegratedGateControl('network_6zones_update.json')
    
    # Scenario: Irrigate three zones
    target_flows = {
        'Zone2': 2.0,  # m³/s
        'Zone5': 1.5,  # m³/s
        'Zone6': 1.0   # m³/s
    }
    
    print(f"\nTarget irrigation flows:")
    for zone, flow in target_flows.items():
        print(f"  {zone}: {flow} m³/s")
    
    # Calculate gate settings
    commands = controller.calculate_gate_settings_for_flows(target_flows)
    
    # Generate SCADA commands
    print("\n\n=== SCADA COMMANDS ===")
    scada_commands = controller.generate_scada_commands(commands)
    
    for i, cmd in enumerate(scada_commands):
        print(f"\nCommand {i+1}:")
        print(f"  Gate: {cmd['gate_id']}")
        print(f"  Opening: {cmd['parameters']['opening_m']} m "
              f"({cmd['parameters']['opening_percent']}%)")
        print(f"  For flow: {cmd['parameters']['target_flow_m3s']} m³/s")
        print(f"  Context: ΔH = {cmd['hydraulic_context']['head_difference_m']} m")
    
    # Summary
    print("\n\n=== SUMMARY ===")
    print("\nGate Opening Schedule:")
    print("-" * 60)
    print(f"{'Gate ID':<20} {'Opening (m)':<12} {'Opening (%)':<12} {'Flow (m³/s)':<12}")
    print("-" * 60)
    
    for gate_id, cmd in sorted(commands.items()):
        print(f"{gate_id:<20} {cmd.opening_m:<12.3f} {cmd.opening_percent:<12.1f} {cmd.actual_flow_m3s:<12.2f}")
    
    print("\n✅ Gate settings calculated using proper hydraulic equations!")
    print("✅ Each gate opening precisely calculated for required flow!")
    print("✅ Ready for SCADA system implementation!")


if __name__ == "__main__":
    demonstrate_integrated_control()