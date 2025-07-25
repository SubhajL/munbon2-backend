#!/usr/bin/env python3
"""
Build complete network graph from SCADA Excel with proper connections
"""

import pandas as pd
import json

def build_network_from_scada(scada_file):
    """Build complete network structure from SCADA file"""
    
    # Read the main sheet
    df = pd.read_excel(scada_file, sheet_name=0, header=1)
    
    gates = {}
    edges = []
    
    # First pass: collect all gates
    for idx, row in df.iterrows():
        if pd.notna(row.get('Gate Valve')):
            gate_id = str(row['Gate Valve']).strip()
            
            gates[gate_id] = {
                'canal': row.get('Canal Name', ''),
                'zone': int(row.get('Zone', 0)) if pd.notna(row.get('Zone')) else 0,
                'km': row.get('km', 0),
                'q_max': row.get('q_max (m^3/s)', 0),
                'area_rai': row.get('Area (Rais)', 0),
                'row_index': idx,  # Keep track of order
                'indices': {
                    'i': int(row.get('i', 0)) if pd.notna(row.get('i')) else 0,
                    'j': int(row.get('j', 0)) if pd.notna(row.get('j')) else 0,
                    'k': int(row.get('k')) if pd.notna(row.get('k')) else None,
                    'l': int(row.get('l')) if pd.notna(row.get('l')) else None,
                    'm': int(row.get('m')) if pd.notna(row.get('m')) else None,
                    'n': int(row.get('n')) if pd.notna(row.get('n')) else None,
                }
            }
    
    # Build connections based on indices and canal types
    
    # 1. Main LMC canal progression (based on j index)
    lmc_gates = [(g, info) for g, info in gates.items() if info['canal'] == 'LMC']
    lmc_gates.sort(key=lambda x: x[1]['indices']['j'])
    
    for i in range(len(lmc_gates) - 1):
        edges.append((lmc_gates[i][0], lmc_gates[i+1][0]))
    
    # 2. Connect branches based on indices
    for gate_id, info in gates.items():
        # Skip if it's the main LMC line
        if info['canal'] == 'LMC':
            continue
            
        # Determine parent based on indices
        indices = info['indices']
        
        # Handle different levels of branching
        if indices['n'] is not None:  # 6 levels deep
            parent_candidates = [
                f"M({indices['i']},{indices['j']}; {indices['k']},{indices['l']}; {indices['m']})",
                f"M({indices['i']},{indices['j']}; {indices['k']},{indices['l']}; {indices['m']})"
            ]
        elif indices['m'] is not None:  # 5 levels deep
            parent_candidates = [
                f"M({indices['i']},{indices['j']}; {indices['k']},{indices['l']})",
                f"M({indices['i']},{indices['j']}; {indices['k']},{indices['l']})"
            ]
        elif indices['l'] is not None:  # 4 levels deep
            parent_candidates = [
                f"M({indices['i']},{indices['j']}; {indices['k']})",
                f"M ({indices['i']},{indices['j']}; {indices['k']})"  # With space
            ]
        elif indices['k'] is not None:  # 3 levels deep (branch from main)
            parent_candidates = [
                f"M({indices['i']},{indices['j']})",
                f"M ({indices['i']},{indices['j']})"  # With space
            ]
        else:
            continue
        
        # Find parent
        parent_found = False
        for parent in parent_candidates:
            if parent in gates:
                edges.append((parent, gate_id))
                parent_found = True
                break
        
        # If no direct parent found, try sequential connection within same canal
        if not parent_found and info['canal']:
            # Find previous gate in same canal
            same_canal_gates = [
                (g, gi) for g, gi in gates.items() 
                if gi['canal'] == info['canal'] and gi['row_index'] < info['row_index']
            ]
            if same_canal_gates:
                # Get the closest previous gate
                same_canal_gates.sort(key=lambda x: x[1]['row_index'])
                prev_gate = same_canal_gates[-1][0]
                edges.append((prev_gate, gate_id))
    
    # 3. Add source connection
    edges.append(('S', 'M(0,0)'))
    
    # Remove duplicate edges
    edges = list(set(edges))
    
    return gates, edges

def print_network_tree(gates, edges, output_file='network_tree.txt'):
    """Print network as a hierarchical tree"""
    
    # Build adjacency list
    children = {}
    for parent, child in edges:
        if parent not in children:
            children[parent] = []
        children[parent].append(child)
    
    # Sort children for consistent display
    for parent in children:
        children[parent].sort(key=lambda x: (
            gates.get(x, {}).get('canal', ''),
            gates.get(x, {}).get('indices', {}).get('j', 0),
            gates.get(x, {}).get('indices', {}).get('k', 0) or 0,
            gates.get(x, {}).get('indices', {}).get('l', 0) or 0,
        ))
    
    output_lines = []
    
    def build_tree(node, prefix="", is_last=True, depth=0):
        # Get node info
        info = gates.get(node, {})
        
        # Format node display
        display = f"{node}"
        if info:
            display += f" [{info['canal']}]" if info['canal'] else ""
            display += f" Zone {info['zone']}" if info['zone'] else ""
            if info.get('q_max') and pd.notna(info['q_max']):
                display += f" (Q: {info['q_max']:.2f} m³/s)"
            if info.get('area_rai') and pd.notna(info['area_rai']):
                display += f" ({info['area_rai']:.0f} rai)"
        
        # Add tree connector
        if depth > 0:
            connector = "└── " if is_last else "├── "
            output_lines.append(prefix + connector + display)
        else:
            output_lines.append(display)
        
        # Process children
        if node in children:
            child_count = len(children[node])
            for i, child in enumerate(children[node]):
                is_last_child = (i == child_count - 1)
                if depth > 0:
                    extension = "    " if is_last else "│   "
                    build_tree(child, prefix + extension, is_last_child, depth + 1)
                else:
                    build_tree(child, prefix, is_last_child, depth + 1)
    
    # Build tree starting from source
    build_tree('S')
    
    # Write to file and print
    tree_content = '\n'.join(output_lines)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(tree_content)
    
    print(tree_content)
    
    return tree_content

def generate_network_summary(gates, edges):
    """Generate network summary statistics"""
    
    print("\n" + "="*70)
    print("NETWORK SUMMARY")
    print("="*70)
    
    # Count nodes by canal
    canal_counts = {}
    for gate, info in gates.items():
        canal = info['canal'] or 'Unknown'
        canal_counts[canal] = canal_counts.get(canal, 0) + 1
    
    print("\nGates by Canal:")
    for canal, count in sorted(canal_counts.items()):
        gates_list = [g for g, i in gates.items() if i['canal'] == canal]
        print(f"\n{canal} ({count} gates):")
        if count <= 10:
            print(f"  {', '.join(gates_list)}")
        else:
            print(f"  {', '.join(gates_list[:5])} ... {', '.join(gates_list[-3:])}")
    
    # Count by zone
    zone_counts = {}
    zone_gates = {}
    for gate, info in gates.items():
        zone = info['zone']
        if zone > 0:
            zone_counts[zone] = zone_counts.get(zone, 0) + 1
            if zone not in zone_gates:
                zone_gates[zone] = []
            zone_gates[zone].append(gate)
    
    print("\n\nGates by Zone:")
    for zone in sorted(zone_counts.keys()):
        count = zone_counts[zone]
        area_total = sum(gates[g].get('area_rai', 0) or 0 for g in zone_gates[zone])
        print(f"\nZone {zone} ({count} gates, {area_total:.0f} rai total):")
        if count <= 8:
            print(f"  {', '.join(zone_gates[zone])}")
        else:
            print(f"  {', '.join(zone_gates[zone][:4])} ... {', '.join(zone_gates[zone][-2:])}")
    
    # Overall statistics
    total_area = sum(info.get('area_rai', 0) or 0 for info in gates.values())
    total_flow_capacity = sum(info.get('q_max', 0) or 0 for info in gates.values() if pd.notna(info.get('q_max')))
    
    print(f"\n\nOverall Statistics:")
    print(f"  Total Gates: {len(gates)}")
    print(f"  Total Connections: {len(edges)}")
    print(f"  Total Irrigated Area: {total_area:,.0f} rai")
    print(f"  Total Flow Capacity: {total_flow_capacity:.2f} m³/s")
    
    # Find terminal nodes (no children)
    has_children = set(e[0] for e in edges)
    all_nodes = set(gates.keys())
    terminal_nodes = all_nodes - has_children
    
    print(f"\n  Terminal Gates (endpoints): {len(terminal_nodes)}")
    terminal_by_zone = {}
    for node in terminal_nodes:
        zone = gates.get(node, {}).get('zone', 0)
        if zone > 0:
            if zone not in terminal_by_zone:
                terminal_by_zone[zone] = []
            terminal_by_zone[zone].append(node)
    
    for zone, nodes in sorted(terminal_by_zone.items()):
        print(f"    Zone {zone}: {len(nodes)} endpoints")

# Main execution
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print("Building network from SCADA file...")
    gates, edges = build_network_from_scada(scada_file)
    
    print(f"\nNetwork built with {len(gates)} gates and {len(edges)} connections")
    
    # Print tree structure
    print("\n" + "="*70)
    print("MUNBON IRRIGATION NETWORK TREE STRUCTURE")
    print("(Updated from SCADA 2025-07-13 V0.95)")
    print("="*70 + "\n")
    
    tree_content = print_network_tree(gates, edges)
    
    # Generate summary
    generate_network_summary(gates, edges)
    
    # Save to JSON
    network_data = {
        'gates': gates,
        'edges': edges,
        'metadata': {
            'source': 'SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx',
            'total_gates': len(gates),
            'total_connections': len(edges)
        }
    }
    
    with open('munbon_network_structure.json', 'w') as f:
        json.dump(network_data, f, indent=2)
    
    print("\n\nNetwork structure saved to:")
    print("  - munbon_network_structure.json (complete data)")
    print("  - network_tree.txt (tree visualization)")