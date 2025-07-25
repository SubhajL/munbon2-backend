#!/usr/bin/env python3
"""
Build network from gate valve naming patterns
"""

import pandas as pd
import json
import re

def parse_gate_name(gate_name):
    """Extract indices from gate name like M(0,3) or M(0,12; 1,1; 1,0)"""
    # Remove M and any spaces
    clean = gate_name.replace('M', '').replace(' ', '').strip()
    
    # Parse the hierarchical structure
    if ';' in clean:
        # Multi-level gate
        parts = clean.strip('()').split(';')
        levels = []
        for part in parts:
            nums = [int(x) for x in part.split(',')]
            levels.append(nums)
        return levels
    else:
        # Single level gate
        nums = [int(x) for x in clean.strip('()').split(',')]
        return [nums]

def build_network_from_names(scada_file):
    """Build network based on gate valve naming patterns"""
    
    df = pd.read_excel(scada_file, sheet_name=0, header=1)
    
    gates = {}
    edges = []
    
    # Collect all gates
    for idx, row in df.iterrows():
        if pd.notna(row.get('Gate Valve')):
            gate_id = str(row['Gate Valve']).strip()
            gates[gate_id] = {
                'canal': row.get('Canal Name', ''),
                'zone': int(row.get('Zone', 0)) if pd.notna(row.get('Zone')) else 0,
                'parsed': parse_gate_name(gate_id),
                'order': idx,
                'q_max': row.get('q_max (m^3/s)', 0),
                'area': row.get('Area (Rais)', 0),
                'km': row.get('km', '')
            }
    
    # Build connections
    
    # 1. Source to outlet, outlet to M(0,1), and outlet to first LMC gate M(0,2)
    edges.append(('S', 'M(0,0)'))
    edges.append(('M(0,0)', 'M(0,1)'))  # M(0,1) branches from outlet
    edges.append(('M(0,0)', 'M(0,2)'))  # M(0,2) is start of LMC
    
    # 2. Main LMC progression - M(0,X) gates
    lmc_main_gates = []
    for g, info in gates.items():
        if info['canal'] == 'LMC' and len(info['parsed']) == 1 and len(info['parsed'][0]) == 2:
            # This is a main LMC gate like M(0,2), M(0,3), etc.
            # Skip M(0,1) as it's not part of main LMC
            if g != 'M(0,1)':
                lmc_main_gates.append((info['parsed'][0][1], g))  # Sort by second number
    
    lmc_main_gates.sort()
    for i in range(len(lmc_main_gates) - 1):
        edges.append((lmc_main_gates[i][1], lmc_main_gates[i+1][1]))
    
    # 3. Connect branches based on hierarchical structure
    for gate_id, info in gates.items():
        parsed = info['parsed']
        
        if len(parsed) > 1:  # This is a branch
            # Build parent ID by removing last level
            if len(parsed) == 2:
                # E.g., M(0,3; 1,0) -> parent is M(0,3)
                parent_id = f"M({parsed[0][0]},{parsed[0][1]})"
            elif len(parsed) == 3:
                # E.g., M(0,3; 1,1; 1,0) -> parent is M(0,3; 1,1)
                parent_id = f"M({parsed[0][0]},{parsed[0][1]}; {parsed[1][0]},{parsed[1][1]})"
                # Also try with space
                parent_id2 = f"M ({parsed[0][0]},{parsed[0][1]}; {parsed[1][0]},{parsed[1][1]})"
                if parent_id not in gates and parent_id2 in gates:
                    parent_id = parent_id2
            elif len(parsed) == 4:
                # E.g., M(0,12; 1,1; 1,0; 1,0) -> parent is M(0,12; 1,1; 1,0)
                parent_id = f"M({parsed[0][0]},{parsed[0][1]}; {parsed[1][0]},{parsed[1][1]}; {parsed[2][0]},{parsed[2][1]})"
                parent_id2 = f"M ({parsed[0][0]},{parsed[0][1]}; {parsed[1][0]},{parsed[1][1]}; {parsed[2][0]},{parsed[2][1]})"
                if parent_id not in gates and parent_id2 in gates:
                    parent_id = parent_id2
            
            if parent_id in gates:
                edges.append((parent_id, gate_id))
            else:
                # Try to find parent with sequential connection in same canal
                same_canal = [(g, gi) for g, gi in gates.items() 
                             if gi['canal'] == info['canal'] and gi['order'] < info['order']]
                if same_canal:
                    # Check for the most likely parent (same structure level)
                    candidates = []
                    for g, gi in same_canal:
                        if len(gi['parsed']) == len(parsed) - 1:
                            # Could be parent
                            match = True
                            for i in range(len(gi['parsed'])):
                                if gi['parsed'][i] != parsed[i]:
                                    match = False
                                    break
                            if match:
                                candidates.append((gi['order'], g))
                    
                    if candidates:
                        candidates.sort(reverse=True)
                        edges.append((candidates[0][1], gate_id))
                    else:
                        # Sequential connection within canal
                        same_canal.sort(key=lambda x: x[1]['order'], reverse=True)
                        edges.append((same_canal[0][0], gate_id))
    
    return gates, edges

def print_network_tree(gates, edges):
    """Print the network as a tree"""
    
    # Build adjacency
    children = {}
    for parent, child in edges:
        if parent not in children:
            children[parent] = []
        children[parent].append(child)
    
    # Sort children
    for parent in children:
        children[parent].sort(key=lambda x: (
            len(gates.get(x, {}).get('parsed', [[]])),  # Level depth
            gates.get(x, {}).get('parsed', [[0,0]])[0][1] if gates.get(x, {}).get('parsed') else 0  # Second index
        ))
    
    visited = set()
    
    def print_node(node, depth=0, prefix="", is_last=True):
        if node in visited:
            return
        visited.add(node)
        
        # Format node
        info = gates.get(node, {})
        display = node
        
        if info:
            parts = []
            if info.get('canal'):
                parts.append(info['canal'])
            if info.get('zone'):
                parts.append(f"Zone {info['zone']}")
            if info.get('q_max') and pd.notna(info['q_max']):
                parts.append(f"{info['q_max']:.1f} m³/s")
            if info.get('area') and pd.notna(info['area']) and info['area'] > 0:
                parts.append(f"{int(info['area'])} rai")
            
            if parts:
                display += f" [{', '.join(parts)}]"
        
        # Print with tree structure
        if depth == 0:
            print(display)
        else:
            connector = "└── " if is_last else "├── "
            print(prefix + connector + display)
        
        # Print children
        if node in children:
            for i, child in enumerate(children[node]):
                is_last_child = (i == len(children[node]) - 1)
                if depth == 0:
                    print_node(child, depth + 1, "", is_last_child)
                else:
                    extension = "    " if is_last else "│   "
                    print_node(child, depth + 1, prefix + extension, is_last_child)
    
    print("\nMUNBON IRRIGATION NETWORK - FINAL STRUCTURE")
    print("="*80)
    print_node('S')
    
    # Statistics
    all_gates = set(gates.keys())
    connected = visited - {'S'}
    disconnected = all_gates - connected
    
    print(f"\n{'='*80}")
    print(f"Network Statistics:")
    print(f"  Total gates: {len(all_gates)}")
    print(f"  Connected gates: {len(connected)}")
    print(f"  Connections: {len(edges)}")
    
    if disconnected:
        print(f"\n  Warning: {len(disconnected)} gates are not connected to the network")

# Main
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    gates, edges = build_network_from_names(scada_file)
    
    print(f"Built network with {len(gates)} gates and {len(edges)} connections\n")
    
    print_network_tree(gates, edges)
    
    # Save final network
    network = {
        'metadata': {
            'source': 'SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx',
            'description': 'Munbon Irrigation Network - Updated Structure',
            'total_gates': len(gates),
            'total_connections': len(edges)
        },
        'gates': gates,
        'edges': edges
    }
    
    with open('munbon_network_updated.json', 'w') as f:
        json.dump(network, f, indent=2)
    
    print(f"\nNetwork saved to munbon_network_updated.json")