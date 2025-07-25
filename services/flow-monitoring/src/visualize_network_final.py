#!/usr/bin/env python3
"""
Final network visualization with correct connections based on gate naming patterns
"""

import pandas as pd
import json
import re

def parse_gate_id(gate_id):
    """Parse gate ID to extract indices"""
    # Remove M and spaces, handle both M(x,y) and M (x,y) formats
    gate_str = gate_id.replace('M', '').replace(' ', '').strip()
    
    # Split by semicolon for multi-level gates
    parts = gate_str.strip('()').split(';')
    
    indices = []
    for part in parts:
        # Extract numbers from each part
        nums = [int(x) for x in part.split(',')]
        indices.extend(nums)
    
    return indices

def build_complete_network(scada_file):
    """Build network with all connections"""
    
    # Read data
    df = pd.read_excel(scada_file, sheet_name=0, header=1)
    
    gates = {}
    edges = set()  # Use set to avoid duplicates
    
    # Collect all gates
    for idx, row in df.iterrows():
        if pd.notna(row.get('Gate Valve')):
            gate_id = str(row['Gate Valve']).strip()
            gates[gate_id] = {
                'canal': row.get('Canal Name', ''),
                'zone': int(row.get('Zone', 0)) if pd.notna(row.get('Zone')) else 0,
                'indices': parse_gate_id(gate_id),
                'order': idx
            }
    
    # Connect based on patterns
    
    # 1. Source to outlet
    edges.add(('S', 'M(0,0)'))
    
    # 2. Main LMC progression
    lmc_gates = []
    for g, info in gates.items():
        if info['canal'] == 'LMC' and ';' not in g:
            # Extract the second number from M(0,X)
            match = re.match(r'M\(0,(\d+)\)', g)
            if match:
                num = int(match.group(1))
                lmc_gates.append((num, g))
    
    lmc_gates.sort()
    for i in range(len(lmc_gates) - 1):
        edges.add((lmc_gates[i][1], lmc_gates[i+1][1]))
    
    # 3. Connect branches based on gate patterns
    for gate_id in gates:
        if ';' in gate_id:  # This is a branch
            # Find parent by removing last index level
            parts = gate_id.split(';')
            
            if len(parts) == 2:
                # First level branch - connect to main canal
                # E.g., M(0,1; 1,0) connects to M(0,1)
                base = parts[0].strip() + ')'
                base = base.replace('M ', 'M')  # Handle space variations
                if base in gates:
                    edges.add((base, gate_id))
                else:
                    # Try without closing parenthesis
                    base2 = parts[0].strip()
                    base2 = base2.replace('M ', 'M')
                    for g in gates:
                        if g.startswith(base2) and ';' not in g:
                            edges.add((g, gate_id))
                            break
            
            elif len(parts) > 2:
                # Multi-level branch - connect to immediate parent
                # E.g., M(0,1; 1,1; 1,0) connects to M(0,1; 1,1)
                parent_parts = parts[:-1]
                parent = ';'.join(parent_parts).strip() + ')'
                parent = parent.replace('M ', 'M')
                
                # Try exact match first
                if parent in gates:
                    edges.add((parent, gate_id))
                else:
                    # Try with space variations
                    parent2 = parent.replace('M(', 'M (')
                    if parent2 in gates:
                        edges.add((parent2, gate_id))
                    else:
                        # Find closest match
                        for g in gates:
                            if ';'.join(parent_parts) in g and g != gate_id:
                                if g.count(';') == len(parent_parts) - 1:
                                    edges.add((g, gate_id))
                                    break
    
    # 4. Sequential connections within same canal
    canal_groups = {}
    for g, info in gates.items():
        canal = info['canal']
        if canal and canal != 'LMC':  # Skip LMC as we handled it
            if canal not in canal_groups:
                canal_groups[canal] = []
            canal_groups[canal].append((info['order'], g))
    
    for canal, gate_list in canal_groups.items():
        gate_list.sort()
        for i in range(len(gate_list) - 1):
            # Only connect if not already connected via hierarchy
            edge = (gate_list[i][1], gate_list[i+1][1])
            if not any(e[1] == edge[1] for e in edges):
                edges.add(edge)
    
    return gates, list(edges)

def print_full_tree(gates, edges):
    """Print complete tree structure"""
    
    # Build children map
    children = {}
    for parent, child in edges:
        if parent not in children:
            children[parent] = []
        if child not in children[parent]:
            children[parent].append(child)
    
    # Sort children
    for parent in children:
        children[parent].sort()
    
    visited = set()
    
    def print_node(node, indent=0, prefix=""):
        if node in visited:
            return
        visited.add(node)
        
        # Node info
        info = gates.get(node, {})
        display = node
        if info:
            if info.get('canal'):
                display += f" [{info['canal']}]"
            if info.get('zone'):
                display += f" Zone {info['zone']}"
        
        # Print with tree structure
        if indent == 0:
            print(display)
        else:
            print(prefix[:-4] + "└── " + display)
        
        # Print children
        if node in children:
            for i, child in enumerate(children[node]):
                is_last = (i == len(children[node]) - 1)
                child_prefix = prefix + ("    " if is_last else "│   ")
                print_node(child, indent + 1, child_prefix)
    
    print("\nMUNBON IRRIGATION NETWORK - COMPLETE STRUCTURE")
    print("=" * 60)
    print_node('S')
    
    # Check for disconnected nodes
    all_nodes = set(gates.keys()) | {'S'}
    connected = visited
    disconnected = all_nodes - connected
    
    if disconnected:
        print("\n\nDISCONNECTED GATES (need connection):")
        print("=" * 60)
        for node in sorted(disconnected):
            info = gates.get(node, {})
            print(f"{node} [{info.get('canal', 'Unknown')}]")

# Main
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print("Building complete network...")
    gates, edges = build_complete_network(scada_file)
    
    print(f"Built network with {len(gates)} gates and {len(edges)} connections\n")
    
    # Print tree
    print_full_tree(gates, edges)
    
    # Save complete structure
    network = {
        'gates': gates,
        'edges': edges,
        'statistics': {
            'total_gates': len(gates),
            'total_connections': len(edges),
            'gates_by_zone': {}
        }
    }
    
    # Group by zone
    for g, info in gates.items():
        zone = str(info.get('zone', 0))
        if zone != '0':
            if zone not in network['statistics']['gates_by_zone']:
                network['statistics']['gates_by_zone'][zone] = []
            network['statistics']['gates_by_zone'][zone].append(g)
    
    with open('munbon_network_complete.json', 'w') as f:
        json.dump(network, f, indent=2)
    
    print(f"\n\nSaved complete network to munbon_network_complete.json")