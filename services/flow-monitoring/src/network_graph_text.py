#!/usr/bin/env python3
"""
Create a text-based network graph representation
"""

import json

def load_network():
    """Load the network structure"""
    with open('munbon_network_updated.json', 'r') as f:
        return json.load(f)

def create_text_graph():
    """Create text-based graph visualization"""
    network = load_network()
    gates = network['gates']
    edges = network['edges']
    
    # Build adjacency list
    children = {}
    for parent, child in edges:
        if parent not in children:
            children[parent] = []
        children[parent].append(child)
    
    # Create the graph representation
    print("\nMUNBON IRRIGATION NETWORK GRAPH")
    print("=" * 80)
    print("\nLegend: [Zone X] = Gate in Zone X")
    print("        → = Water flow direction")
    print("=" * 80)
    print()
    
    # Source level
    print(" " * 40 + "S")
    print(" " * 40 + "|")
    print(" " * 40 + "↓")
    
    # Outlet level
    print(" " * 40 + "M(0,0) [Zone 1]")
    print(" " * 40 + "|")
    print(" " * 20 + "─" * 40)
    print(" " * 20 + "|" + " " * 38 + "|")
    print(" " * 20 + "↓" + " " * 38 + "↓")
    
    # Split to M(0,1) and M(0,2)
    print(" " * 15 + "M(0,1) [RMC]" + " " * 23 + "M(0,2) [LMC Start] [Zone 1]")
    print(" " * 20 + "|" + " " * 38 + "|")
    print(" " * 20 + "↓" + " " * 38 + "↓")
    
    # Show RMC branch structure
    print("\n" + "=" * 30 + " RMC BRANCH (Zone 6) " + "=" * 29)
    print("From M(0,1):")
    print("  ├── M(0,1; 1,0) → M(0,1; 1,0; 1,0) [FTO 2+450]")
    print("  ├── M(0,1; 1,1)")
    print("  │   ├── M(0,1; 1,1; 1,0) [4L-RMC]")
    print("  │   ├── M(0,1; 1,1; 1,1) [4L-RMC]") 
    print("  │   ├── M(0,1; 1,1; 1,2) [4L-RMC] → M(0,1; 1,1; 1,2; 1,0) [FTO337]")
    print("  │   ├── M(0,1; 1,1; 1,3) [4L-RMC]")
    print("  │   └── M(0,1; 1,1; 1,4) [4L-RMC]")
    print("  ├── M(0,1; 1,2)")
    print("  ├── M(0,1; 1,3)")
    print("  └── M(0,1; 1,4)")
    
    # Show main LMC progression
    print("\n" + "=" * 30 + " MAIN LMC CANAL " + "=" * 34)
    print("M(0,2) → M(0,3) → M(0,4) → M(0,5) → M(0,6) → M(0,7) → M(0,8) → M(0,9) →")
    print("         [Z1]      [Z1]      [Z1]      [Z2]      [Z2]      [Z2]      [Z2]")
    print("          |")
    print("          ├── 9R-LMC Branch (Zone 3)")
    print("          └── (continues below)")
    print()
    print("→ M(0,10) → M(0,11) → M(0,12) → M(0,13) → M(0,14)")
    print("   [Z2]      [Z2]       [Z2]      [Z2]       [Z2]")
    print("                         |")
    print("                         └── 38R-LMC Branch (Zones 4 & 5)")
    
    # Show 9R-LMC branch
    print("\n" + "=" * 25 + " 9R-LMC BRANCH FROM M(0,3) (Zone 3) " + "=" * 18)
    print("M(0,3):")
    print("  ├── M(0,3; 1,0) [9R-LMC]")
    print("  ├── M(0,3; 1,1) [9R-LMC]")
    print("  │   ├── M(0,3; 1,1; 1,0) [7R-9R-LMC]")
    print("  │   ├── M(0,3; 1,1; 1,1) [7R-9R-LMC]")
    print("  │   ├── M(0,3; 1,1; 2,0) [7L-9R-LMC]")
    print("  │   └── M(0,3; 1,1; 2,1) [7L-9R-LMC]")
    print("  ├── M(0,3; 1,2) [9R-LMC]")
    print("  └── M(0,3; 1,3) [9R-LMC]")
    
    # Show 38R-LMC branch
    print("\n" + "=" * 20 + " 38R-LMC BRANCH FROM M(0,12) (Zones 4 & 5) " + "=" * 17)
    print("M(0,12):")
    print("  ├── M(0,12; 1,0) [38R-LMC] [Zone 4]")
    print("  │   ├── M(0,12; 1,0; 1,0) [1R-38R-LMC]")
    print("  │   └── M(0,12; 1,0; 1,1) [1R-38R-LMC]")
    print("  ├── M(0,12; 1,1) [38R-LMC] [Zone 4]")
    print("  │   ├── M(0,12; 1,1; 1,0) [2R-38R-LMC]")
    print("  │   │   ├── M(0,12; 1,1; 1,0; 1,0) [1R-2R-38R-LMC]")
    print("  │   │   ├── M(0,12; 1,1; 1,0; 1,1) [1R-2R-38R-LMC]")
    print("  │   │   └── M(0,12; 1,1; 1,0; 1,2) [1R-2R-38R-LMC]")
    print("  │   ├── M(0,12; 1,1; 1,1) [2R-38R-LMC]")
    print("  │   └── M(0,12; 1,1; 1,2) [2R-38R-LMC]")
    print("  ├── M(0,12; 1,2) [38R-LMC] [Zone 4]")
    print("  │   ├── M(0,12; 1,2; 1,0) [4L-38R-LMC] [Zone 5]")
    print("  │   │   ├── M(0,12; 1,2; 1,0; 1,0) [5R-4L-38R-LMC]")
    print("  │   │   └── M(0,12; 1,2; 1,0; 1,1) [5R-4L-38R-LMC]")
    print("  │   ├── M(0,12; 1,2; 1,1) [4L-38R-LMC] [Zone 5]")
    print("  │   └── M(0,12; 1,2; 1,2) [4L-38R-LMC] [Zone 5]")
    print("  ├── M(0,12; 1,3) [38R-LMC] [Zone 5]")
    print("  │   ├── M(0,12; 1,3; 1,0) [6R-38R-LMC]")
    print("  │   └── M(0,12; 1,3; 1,1) [6R-38R-LMC]")
    print("  ├── M(0,12; 1,4) [38R-LMC] [Zone 5]")
    print("  │   ├── M(0,12; 1,4; 1,0) [8R-38R-LMC]")
    print("  │   └── M(0,12; 1,4; 1,1) [8R-38R-LMC]")
    print("  └── M(0,12; 1,5) [38R-LMC] [Zone 5]")
    
    # Also show waste way
    print("\n" + "=" * 30 + " WASTE WAY " + "=" * 39)
    print("From M(0,0):")
    print("  └── M(0,0; 1,0) [Waste Way] [Zone 1]")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("NETWORK SUMMARY:")
    zones = {}
    for gate, info in gates.items():
        zone = info.get('zone', 0)
        if zone > 0:
            zones[zone] = zones.get(zone, 0) + 1
    
    print(f"Total Gates: {len(gates)}")
    print(f"Total Connections: {len(edges)}")
    print("\nGates by Zone:")
    for zone in sorted(zones.keys()):
        print(f"  Zone {zone}: {zones[zone]} gates")
    
    # Flow capacity summary
    print("\nMain Flow Capacities:")
    key_gates = [
        ('M(0,0)', 'Outlet'),
        ('M(0,2)', 'LMC Start'),
        ('M(0,3)', 'LMC + 9R Branch'),
        ('M(0,12)', 'LMC + 38R Branch'),
        ('M(0,1; 1,0)', 'RMC Start')
    ]
    
    for gate_id, desc in key_gates:
        if gate_id in gates:
            q_max = gates[gate_id].get('q_max', 0)
            if q_max and q_max > 0:
                print(f"  {gate_id} ({desc}): {q_max:.1f} m³/s")

if __name__ == "__main__":
    create_text_graph()