#!/usr/bin/env python3
"""
Extract and display network structure from SCADA Excel
"""

import pandas as pd
import json

def load_network_from_scada(scada_file):
    """Load network structure from updated SCADA file"""
    
    # Read the main sheet with gate information
    df = pd.read_excel(scada_file, sheet_name=0, header=1)
    
    # Extract gates and build network
    gates = {}
    edges = []
    
    # Track previous gates for main canals
    prev_gates = {
        'LMC': None,
        'RMC': None,
        '4L-RMC': None,
        '9R-LMC': None,
        '38R-LMC': None
    }
    
    # Process gates in order from the Excel
    for idx, row in df.iterrows():
        if pd.notna(row.get('Gate Valve')):
            gate_id = row['Gate Valve']
            canal = row.get('Canal Name', '')
            
            # Store gate info
            gates[gate_id] = {
                'canal': canal,
                'zone': int(row.get('Zone', 0)) if pd.notna(row.get('Zone')) else 0,
                'km': row.get('km', 0),
                'q_max': row.get('q_max (m^3/s)', 0),
                'area_rai': row.get('Area (Rais)', 0),
                'indices': {
                    'i': int(row.get('i', 0)) if pd.notna(row.get('i')) else 0,
                    'j': int(row.get('j', 0)) if pd.notna(row.get('j')) else 0,
                    'k': int(row.get('k', 0)) if pd.notna(row.get('k')) else None,
                    'l': int(row.get('l', 0)) if pd.notna(row.get('l')) else None,
                }
            }
            
            # Build edges based on canal type and indices
            if canal == 'LMC':
                # Main canal progression
                if prev_gates['LMC']:
                    edges.append((prev_gates['LMC'], gate_id))
                prev_gates['LMC'] = gate_id
                
            elif canal == 'RMC':
                # RMC branches from M(0,1)
                if prev_gates['RMC'] is None:
                    edges.append(('M(0,1)', gate_id))
                else:
                    edges.append((prev_gates['RMC'], gate_id))
                prev_gates['RMC'] = gate_id
                
            elif '4L-RMC' in canal:
                # 4L-RMC branches from M(0,1; 1,1)
                if prev_gates['4L-RMC'] is None:
                    edges.append(('M(0,1; 1,1)', gate_id))
                else:
                    edges.append((prev_gates['4L-RMC'], gate_id))
                prev_gates['4L-RMC'] = gate_id
                
            elif '9R-LMC' in canal:
                # 9R-LMC branches from M(0,3)
                if prev_gates['9R-LMC'] is None:
                    edges.append(('M(0,3)', gate_id))
                else:
                    edges.append((prev_gates['9R-LMC'], gate_id))
                prev_gates['9R-LMC'] = gate_id
                
            elif '38R-LMC' in canal:
                # 38R-LMC branches from M(0,12)
                if prev_gates['38R-LMC'] is None:
                    edges.append(('M(0,12)', gate_id))
                else:
                    edges.append((prev_gates['38R-LMC'], gate_id))
                prev_gates['38R-LMC'] = gate_id
                
            # Handle sub-branches based on indices
            elif pd.notna(row.get('k')):
                # This is a branch - find parent based on indices
                i, j = gates[gate_id]['indices']['i'], gates[gate_id]['indices']['j']
                k = gates[gate_id]['indices']['k']
                
                # Determine parent
                if pd.notna(row.get('l')):  # 4-level deep
                    parent = f"M({i},{j}; {k})"
                else:  # 3-level deep
                    parent = f"M({i},{j})"
                
                if parent in gates:
                    edges.append((parent, gate_id))
                    
            # Handle special branches with complex naming
            if ';' in gate_id:
                # Try to find parent from gate name pattern
                parts = gate_id.replace('M', '').replace('(', '').replace(')', '').replace(' ', '').split(';')
                if len(parts) > 1:
                    # Build parent name
                    parent_parts = parts[:-1]
                    parent = 'M(' + '; '.join(parent_parts) + ')'
                    if parent in gates and (parent, gate_id) not in edges:
                        edges.append((parent, gate_id))
    
    # Add source connection
    edges.append(('S', 'M(0,0)'))
    
    return gates, edges

def create_text_visualization(gates, edges):
    """Create a text-based visualization of the network"""
    
    print("\n" + "="*60)
    print("MUNBON IRRIGATION NETWORK STRUCTURE")
    print("Updated from SCADA 2025-07-13 V0.95")
    print("="*60)
    
    # Build adjacency list
    adjacency = {}
    for parent, child in edges:
        if parent not in adjacency:
            adjacency[parent] = []
        adjacency[parent].append(child)
    
    # Recursive function to print tree
    def print_tree(node, prefix="", is_last=True):
        gate_info = gates.get(node, {})
        canal = gate_info.get('canal', '')
        zone = gate_info.get('zone', '')
        q_max = gate_info.get('q_max', 0)
        
        # Format node info
        node_str = f"{node}"
        if canal:
            node_str += f" [{canal}]"
        if zone:
            node_str += f" Zone {zone}"
        if q_max:
            node_str += f" (Q_max: {q_max} m³/s)"
        
        # Print with tree structure
        connector = "└── " if is_last else "├── "
        print(prefix + connector + node_str)
        
        # Get children
        children = adjacency.get(node, [])
        
        # Sort children by canal type for better organization
        def sort_key(child):
            child_canal = gates.get(child, {}).get('canal', '')
            if 'LMC' in child_canal and '9R' not in child_canal and '38R' not in child_canal:
                return (0, child)  # Main LMC first
            elif 'RMC' in child_canal:
                return (1, child)  # RMC second
            elif '9R' in child_canal:
                return (2, child)  # 9R branches
            elif '38R' in child_canal:
                return (3, child)  # 38R branches
            else:
                return (4, child)  # Others
        
        children.sort(key=sort_key)
        
        # Print children
        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            extension = "    " if is_last else "│   "
            print_tree(child, prefix + extension, is_last_child)
    
    # Start from source
    print_tree('S')
    
    # Print summary statistics
    print("\n" + "="*60)
    print("NETWORK SUMMARY")
    print("="*60)
    
    # Count by canal
    canals = {}
    for gate, info in gates.items():
        canal = info['canal']
        canals[canal] = canals.get(canal, 0) + 1
    
    print("\nGates by Canal:")
    for canal, count in sorted(canals.items()):
        print(f"  {canal:20} : {count:3} gates")
    
    # Count by zone
    zones = {}
    for gate, info in gates.items():
        zone = info['zone']
        if zone > 0:
            zones[zone] = zones.get(zone, 0) + 1
    
    print("\nGates by Zone:")
    for zone, count in sorted(zones.items()):
        print(f"  Zone {zone:15} : {count:3} gates")
    
    print(f"\nTotal Gates: {len(gates)}")
    print(f"Total Connections: {len(edges)}")

def save_network_structure(gates, edges):
    """Save network structure to JSON"""
    
    network_data = {
        'gates': gates,
        'edges': [(e[0], e[1]) for e in edges],  # Convert tuples to lists for JSON
        'summary': {
            'total_gates': len(gates),
            'gates_by_canal': {},
            'gates_by_zone': {}
        }
    }
    
    # Summarize by canal
    for gate, info in gates.items():
        canal = info['canal']
        if canal not in network_data['summary']['gates_by_canal']:
            network_data['summary']['gates_by_canal'][canal] = []
        network_data['summary']['gates_by_canal'][canal].append(gate)
    
    # Summarize by zone
    for gate, info in gates.items():
        zone = info['zone']
        if zone > 0:
            zone_str = str(zone)
            if zone_str not in network_data['summary']['gates_by_zone']:
                network_data['summary']['gates_by_zone'][zone_str] = []
            network_data['summary']['gates_by_zone'][zone_str].append(gate)
    
    with open('network_structure_updated.json', 'w') as f:
        json.dump(network_data, f, indent=2)
    
    print(f"\nNetwork structure saved to network_structure_updated.json")

# Main execution
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print("Loading network from SCADA file...")
    gates, edges = load_network_from_scada(scada_file)
    
    # Create text visualization
    create_text_visualization(gates, edges)
    
    # Save structure
    save_network_structure(gates, edges)