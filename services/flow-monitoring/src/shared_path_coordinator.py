#!/usr/bin/env python3
"""
Shared Path Coordinator - Handles coinciding paths in irrigation networks
Shows exactly how multiple zones sharing the same canals are managed
"""

import numpy as np
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class PathFlow:
    """Flow requirement along a path"""
    zone: str
    path: List[str]
    flow_rate: float
    volume: float
    duration_hours: float

class SharedPathCoordinator:
    """
    Manages irrigation when multiple zones share canal segments
    """
    
    def analyze_shared_paths(self, path_flows: List[PathFlow]):
        """
        Analyze path overlaps and calculate combined flows
        """
        
        print("\n=== SHARED PATH ANALYSIS ===\n")
        
        # Step 1: Show all paths
        print("1. Individual Paths:")
        for pf in path_flows:
            print(f"\n{pf.zone} (needs {pf.flow_rate} m³/s):")
            print(f"   {' → '.join(pf.path)}")
        
        # Step 2: Find shared segments
        print("\n2. Identifying Shared Segments:")
        
        # Build edge usage map
        edge_usage = {}  # edge -> list of (zone, flow)
        
        for pf in path_flows:
            for i in range(len(pf.path) - 1):
                edge = f"{pf.path[i]}->{pf.path[i+1]}"
                if edge not in edge_usage:
                    edge_usage[edge] = []
                edge_usage[edge].append((pf.zone, pf.flow_rate))
        
        # Show shared edges
        shared_edges = {edge: users for edge, users in edge_usage.items() if len(users) > 1}
        
        print("\nShared Canal Segments:")
        for edge, users in shared_edges.items():
            total_flow = sum(flow for _, flow in users)
            zones = [zone for zone, _ in users]
            print(f"\n   {edge}:")
            print(f"      Used by: {', '.join(zones)}")
            print(f"      Individual flows: {[f'{z}: {f:.1f}' for z, f in users]}")
            print(f"      COMBINED FLOW REQUIRED: {total_flow:.1f} m³/s")
        
        # Step 3: Calculate gate settings
        print("\n3. Gate Settings for Shared Segments:")
        
        gate_settings = {}
        for edge, users in edge_usage.items():
            total_flow = sum(flow for _, flow in users)
            # Assume 5 m³/s capacity per gate
            gate_capacity = 5.0
            opening_percent = min(100, (total_flow / gate_capacity) * 100)
            gate_settings[edge] = {
                'total_flow': total_flow,
                'opening_percent': opening_percent,
                'zones_served': [zone for zone, _ in users]
            }
        
        # Show critical gates
        print("\nGate Operations Required:")
        for edge, setting in sorted(gate_settings.items(), key=lambda x: x[1]['total_flow'], reverse=True):
            if setting['total_flow'] > 0:
                print(f"\n   {edge}:")
                print(f"      Flow: {setting['total_flow']:.1f} m³/s")
                print(f"      Opening: {setting['opening_percent']:.0f}%")
                print(f"      Serves: {', '.join(setting['zones_served'])}")
        
        return edge_usage, gate_settings
    
    def demonstrate_coinciding_paths(self):
        """
        Demonstrate handling of coinciding paths for Zones 2, 5, and 6
        """
        
        print("\n" + "="*70)
        print("HANDLING COINCIDING PATHS IN IRRIGATION NETWORK")
        print("="*70)
        
        # Define the three paths
        path_flows = [
            PathFlow(
                zone="Zone 2",
                path=["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "Zone2"],
                flow_rate=2.0,
                volume=10000,
                duration_hours=1.39
            ),
            PathFlow(
                zone="Zone 5", 
                path=["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "Zone5"],
                flow_rate=1.5,
                volume=7500,
                duration_hours=1.39
            ),
            PathFlow(
                zone="Zone 6",
                path=["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "M(0,14)", "Zone6"],
                flow_rate=1.0,
                volume=5000,
                duration_hours=1.39
            )
        ]
        
        # Analyze shared paths
        edge_usage, gate_settings = self.analyze_shared_paths(path_flows)
        
        # Show visual representation
        print("\n4. Visual Representation of Flow Distribution:")
        print("\n   Source")
        print("     │")
        print("     │ 4.5 m³/s (2.0 + 1.5 + 1.0)")
        print("     ↓")
        print("   M(0,0)")
        print("     │")
        print("     │ 4.5 m³/s (All zones)")
        print("     ↓")
        print("   M(0,2)")
        print("     │")
        print("     │ 4.5 m³/s (All zones)")
        print("     ↓")
        print("   M(0,3)")
        print("     │")
        print("     │ 4.5 m³/s (All zones)")
        print("     ↓")
        print("   M(0,5) ←── Here the flow splits!")
        print("     │ \\")
        print("     │  \\ 2.5 m³/s (Zone 5: 1.5 + Zone 6: 1.0)")
        print("     │   \\")
        print("     │    M(0,12)")
        print("     │      │ \\")
        print("     │      │  \\ 1.0 m³/s")
        print("     │      │   \\")
        print("     │      │    M(0,14) → Zone 6")
        print("     │      │")
        print("     │      ↓ 1.5 m³/s")
        print("     │     Zone 5")
        print("     │")
        print("     ↓ 2.0 m³/s")
        print("   Zone 2")
        
        # Show timing coordination
        print("\n5. Temporal Coordination for Shared Paths:")
        print("\nSince all zones need water simultaneously:")
        print("- Shared gates MUST handle combined flow")
        print("- Gates open ONCE for all zones (not separately)")
        print("- Gates close only after ALL zones served by that segment are complete")
        
        print("\nExample Gate Timeline:")
        print("\n06:00 - Open Source→M(0,0) at 90% (for 4.5 m³/s total)")
        print("        NOT 3 separate operations of 40%, 30%, 20%!")
        print("\n09:00 - Cannot close M(0,3)→M(0,5) yet because:")
        print("        - Zone 2 finished ✓")
        print("        - Zone 5 still needs water ✗") 
        print("        - Zone 6 still needs water ✗")
        print("\n09:30 - NOW can close shared upstream gates because")
        print("        all zones have received their water")
        
        # Show what happens without coordination
        print("\n6. What Happens WITHOUT Shared Path Coordination:")
        print("\n❌ WRONG Approach (treating paths independently):")
        print("   - Open Source→M(0,0) to 40% for Zone 2")
        print("   - Open Source→M(0,0) to 30% for Zone 5")  
        print("   - Open Source→M(0,0) to 20% for Zone 6")
        print("   Result: Gate confusion! What should it actually be?")
        
        print("\n✅ CORRECT Approach (coordinated):")
        print("   - Open Source→M(0,0) to 90% for combined flow")
        print("   - Single operation serving all zones")
        
        return edge_usage, gate_settings

    def calculate_closing_times(self, path_flows: List[PathFlow], start_time: datetime):
        """
        Calculate when each gate can be closed based on all zones it serves
        """
        
        print("\n7. Gate Closing Coordination:")
        
        # Map each edge to all zones it serves and their completion times
        edge_completion = {}  # edge -> list of (zone, completion_time)
        
        for pf in path_flows:
            completion_time = start_time + timedelta(hours=pf.duration_hours)
            
            for i in range(len(pf.path) - 1):
                edge = f"{pf.path[i]}->{pf.path[i+1]}"
                if edge not in edge_completion:
                    edge_completion[edge] = []
                edge_completion[edge].append((pf.zone, completion_time))
        
        # Calculate earliest safe closing time for each gate
        gate_closing_times = {}
        
        for edge, completions in edge_completion.items():
            # Gate can only close after ALL zones are done
            latest_completion = max(time for _, time in completions)
            zones_served = [zone for zone, _ in completions]
            
            gate_closing_times[edge] = {
                'close_time': latest_completion,
                'zones': zones_served,
                'reason': f"All zones ({', '.join(zones_served)}) complete"
            }
        
        # Show results
        print("\nGate Closing Schedule:")
        for edge, info in sorted(gate_closing_times.items(), key=lambda x: x[1]['close_time']):
            print(f"\n{edge}:")
            print(f"   Can close at: {info['close_time'].strftime('%H:%M')}")
            print(f"   Reason: {info['reason']}")
        
        return gate_closing_times


def main():
    """Demonstrate shared path coordination"""
    
    coordinator = SharedPathCoordinator()
    
    # Run demonstration
    edge_usage, gate_settings = coordinator.demonstrate_coinciding_paths()
    
    # Calculate closing times
    start_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    path_flows = [
        PathFlow("Zone 2", ["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "Zone2"], 
                2.0, 10000, 1.39),
        PathFlow("Zone 5", ["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "Zone5"], 
                1.5, 7500, 1.39),
        PathFlow("Zone 6", ["Source", "M(0,0)", "M(0,2)", "M(0,3)", "M(0,5)", "M(0,12)", "M(0,14)", "Zone6"], 
                1.0, 5000, 1.39)
    ]
    
    coordinator.calculate_closing_times(path_flows, start_time)
    
    # Summary
    print("\n" + "="*70)
    print("KEY TAKEAWAY: Shared Path Coordination")
    print("="*70)
    print("\nThe system MUST handle coinciding paths by:")
    print("1. Identifying all shared canal segments")
    print("2. Calculating COMBINED flow requirements")
    print("3. Opening gates ONCE for the total flow")
    print("4. Closing gates only after ALL dependent zones are served")
    print("\nThis is ESSENTIAL for proper irrigation network operation!")


if __name__ == "__main__":
    main()