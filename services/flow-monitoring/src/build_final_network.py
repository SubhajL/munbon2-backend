#!/usr/bin/env python3
"""
Build final network with correct gate ID extraction from indices
"""

import pandas as pd
import json

def build_network_correctly(scada_file):
    """Build network using the indices from Excel"""
    
    # Read data
    df = pd.read_excel(scada_file, sheet_name=0, header=1)
    
    gates = {}
    edges = []
    
    # First, collect all gates with their actual indices
    for idx, row in df.iterrows():
        if pd.notna(row.get('Gate Valve')):
            gate_id = str(row['Gate Valve']).strip()
            
            # Get indices from Excel columns
            i = int(row.get('i', 0)) if pd.notna(row.get('i')) else 0
            j = int(row.get('j', 0)) if pd.notna(row.get('j')) else 0
            k = int(row.get('k')) if pd.notna(row.get('k')) else None
            l = int(row.get('l')) if pd.notna(row.get('l')) else None
            m = int(row.get('m')) if pd.notna(row.get('m')) else None
            n = int(row.get('n')) if pd.notna(row.get('n')) else None
            
            gates[gate_id] = {
                'canal': row.get('Canal Name', ''),
                'zone': int(row.get('Zone', 0)) if pd.notna(row.get('Zone')) else 0,
                'i': i, 'j': j, 'k': k, 'l': l, 'm': m, 'n': n,
                'order': idx,
                'q_max': row.get('q_max (m^3/s)', 0),
                'area': row.get('Area (Rais)', 0)
            }
    
    # Connect based on indices and patterns
    
    # 1. Source connection
    edges.append(('S', 'M(0,0)'))
    
    # 2. Main LMC canal - connect based on j index progression
    lmc_gates = [(g, info) for g, info in gates.items() 
                 if info['canal'] == 'LMC' and info['k'] is None]
    lmc_gates.sort(key=lambda x: x[1]['j'])
    
    for idx in range(len(lmc_gates) - 1):
        edges.append((lmc_gates[idx][0], lmc_gates[idx+1][0]))
    
    # 3. Connect branches based on indices
    for gate_id, info in gates.items():
        # Skip main LMC gates
        if info['canal'] == 'LMC' and info['k'] is None:
            continue
        
        # Find parent based on indices
        parent_found = False
        
        # For gates with k index (first level branches)
        if info['k'] is not None and info['l'] is None:
            # Parent should be M(i,j)
            parent_id = f"M({info['i']},{info['j']})"
            if parent_id in gates:
                edges.append((parent_id, gate_id))
                parent_found = True
        
        # For gates with l index (second level branches)
        elif info['l'] is not None and info['m'] is None:
            # Parent should be M(i,j; k) or similar
            # Try different formats
            parent_candidates = [
                f"M({info['i']},{info['j']}; {info['k']})",
                f"M ({info['i']},{info['j']}; {info['k']})",  # With space
                f"M({info['i']},{info['j']};{info['k']})"      # No spaces
            ]
            for parent in parent_candidates:
                if parent in gates:
                    edges.append((parent, gate_id))
                    parent_found = True
                    break
        
        # For deeper levels
        elif info['m'] is not None:
            # Build parent ID
            parent_candidates = [
                f"M({info['i']},{info['j']}; {info['k']},{info['l']})",
                f"M ({info['i']},{info['j']}; {info['k']},{info['l']})",
                f"M({info['i']},{info['j']};{info['k']},{info['l']})"
            ]
            for parent in parent_candidates:
                if parent in gates:
                    edges.append((parent, gate_id))
                    parent_found = True
                    break
        
        # If no parent found by indices, try sequential within canal
        if not parent_found and info['canal']:
            same_canal = [(g, gi) for g, gi in gates.items() 
                         if gi['canal'] == info['canal'] and gi['order'] < info['order']]
            if same_canal:
                # Get the closest previous gate in same canal
                same_canal.sort(key=lambda x: x[1]['order'], reverse=True)
                edges.append((same_canal[0][0], gate_id))
    
    return gates, edges

def create_visual_tree(gates, edges):
    """Create visual representation of the network"""
    
    # Build adjacency
    children = {}
    for parent, child in edges:
        if parent not in children:
            children[parent] = []
        children[parent].append(child)
    
    # Sort children for consistent display
    for parent in children:
        children[parent].sort()
    
    visited = set()
    tree_lines = []
    
    def build_tree(node, depth=0, prefix="", is_last=True):
        if node in visited:
            return
        visited.add(node)
        
        # Node display
        info = gates.get(node, {})
        display = node
        
        if info:
            details = []
            if info.get('canal'):
                details.append(info['canal'])
            if info.get('zone'):
                details.append(f"Zone {info['zone']}")
            if info.get('q_max') and pd.notna(info['q_max']):
                details.append(f"{info['q_max']:.1f} m³/s")
            if info.get('area') and pd.notna(info['area']):
                details.append(f"{int(info['area'])} rai")
            
            if details:
                display += f" [{', '.join(details)}]"
        
        # Tree formatting
        if depth == 0:
            tree_lines.append(display)
        else:
            connector = "└── " if is_last else "├── "
            tree_lines.append(prefix + connector + display)
        
        # Process children
        if node in children:
            child_count = len(children[node])
            for i, child in enumerate(children[node]):
                is_last_child = (i == child_count - 1)
                if depth == 0:
                    build_tree(child, depth + 1, "", is_last_child)
                else:
                    extension = "    " if is_last else "│   "
                    build_tree(child, depth + 1, prefix + extension, is_last_child)
    
    # Build tree
    build_tree('S')
    
    # Print tree
    print("\nMUNBON IRRIGATION NETWORK STRUCTURE")
    print("(Updated from SCADA 2025-07-13)")
    print("="*80)
    for line in tree_lines:
        print(line)
    
    # Check coverage
    all_gates = set(gates.keys())
    connected = visited - {'S'}
    disconnected = all_gates - connected
    
    print(f"\n{'='*80}")
    print(f"Network Statistics:")
    print(f"  Total gates: {len(all_gates)}")
    print(f"  Connected gates: {len(connected)}")
    print(f"  Disconnected gates: {len(disconnected)}")
    
    if disconnected:
        print(f"\nDisconnected gates requiring manual connection:")
        by_canal = {}
        for g in disconnected:
            canal = gates[g]['canal']
            if canal not in by_canal:
                by_canal[canal] = []
            by_canal[canal].append(g)
        
        for canal, gate_list in sorted(by_canal.items()):
            print(f"\n  {canal}: {len(gate_list)} gates")
            for g in sorted(gate_list)[:5]:
                print(f"    - {g}")
            if len(gate_list) > 5:
                print(f"    ... and {len(gate_list)-5} more")
    
    # Save visualization
    with open('network_visualization.txt', 'w', encoding='utf-8') as f:
        f.write("MUNBON IRRIGATION NETWORK STRUCTURE\n")
        f.write("(Updated from SCADA 2025-07-13)\n")
        f.write("="*80 + "\n")
        for line in tree_lines:
            f.write(line + "\n")
        f.write("\n" + "="*80 + "\n")
        f.write(f"Total gates: {len(all_gates)}\n")
        f.write(f"Connected gates: {len(connected)}\n")
        f.write(f"Disconnected gates: {len(disconnected)}\n")
    
    return tree_lines

# Main execution
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print("Building network from SCADA file...")
    gates, edges = build_network_correctly(scada_file)
    
    print(f"Built network with {len(gates)} gates and {len(edges)} connections")
    
    # Create visualization
    tree_lines = create_visual_tree(gates, edges)
    
    # Save complete network
    network_data = {
        'metadata': {
            'source': 'SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx',
            'total_gates': len(gates),
            'total_connections': len(edges),
            'description': 'Munbon Irrigation Network with updated indices'
        },
        'gates': gates,
        'edges': edges
    }
    
    with open('munbon_network_final.json', 'w') as f:
        json.dump(network_data, f, indent=2)
    
    print("\nFiles created:")
    print("  - munbon_network_final.json (complete network data)")
    print("  - network_visualization.txt (tree visualization)")