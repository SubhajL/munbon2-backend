#!/usr/bin/env python3
"""
Update network graph from SCADA Excel and visualize
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import colors
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
    
    for idx, row in df.iterrows():
        if pd.notna(row.get('Gate Valve')):
            gate_id = row['Gate Valve']
            canal = row.get('Canal Name', '')
            
            # Store gate info
            gates[gate_id] = {
                'canal': canal,
                'zone': row.get('Zone', 0),
                'km': row.get('km', 0),
                'q_max': row.get('q_max (m^3/s)', 0),
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
    
    # Add source connection
    edges.append(('S', 'M(0,0)'))
    
    return gates, edges

def visualize_network(gates, edges, output_file='updated_network.png'):
    """Visualize the network with manual layout"""
    
    # Create figure
    fig, ax = plt.subplots(figsize=(24, 18))
    
    # Define positions manually for better layout
    positions = {}
    
    # Source
    positions['S'] = (0, 10)
    
    # Main LMC canal - horizontal progression
    lmc_gates = [g for g, info in gates.items() if info['canal'] == 'LMC']
    lmc_gates.sort(key=lambda x: gates[x]['indices']['j'])
    
    x_start = 2
    y_lmc = 10
    x_spacing = 3
    
    for i, gate in enumerate(lmc_gates):
        positions[gate] = (x_start + i * x_spacing, y_lmc)
    
    # RMC branch - goes down from M(0,1)
    rmc_gates = [g for g, info in gates.items() if 'RMC' in info['canal'] and '4L' not in info['canal']]
    y_rmc_start = 7
    for i, gate in enumerate(rmc_gates):
        positions[gate] = (positions.get('M(0,1)', (5, 10))[0] + i * 2, y_rmc_start - i * 0.5)
    
    # 4L-RMC sub-branch
    fl_rmc_gates = [g for g, info in gates.items() if '4L-RMC' in info['canal']]
    if 'M(0,1; 1,1)' in positions:
        x_base, y_base = positions['M(0,1; 1,1)']
        for i, gate in enumerate(fl_rmc_gates):
            positions[gate] = (x_base + 1 + i * 1.5, y_base - 2 - i * 0.3)
    
    # 9R-LMC branch
    nr_lmc_gates = [g for g, info in gates.items() if '9R-LMC' in info['canal']]
    if 'M(0,3)' in positions:
        x_base, y_base = positions['M(0,3)']
        for i, gate in enumerate(nr_lmc_gates):
            positions[gate] = (x_base + i * 1.5, y_base - 3 - i * 0.5)
    
    # 38R-LMC branch - largest branch
    tr_lmc_gates = [g for g, info in gates.items() if '38R-LMC' in info['canal']]
    if 'M(0,12)' in positions:
        x_base, y_base = positions['M(0,12)']
        # Main 38R-LMC line
        main_38r = [g for g in tr_lmc_gates if g.count(';') == 1]
        for i, gate in enumerate(main_38r):
            positions[gate] = (x_base + i * 2, y_base - 3)
        
        # Sub-branches of 38R-LMC
        for gate in tr_lmc_gates:
            if gate.count(';') > 1 and gate not in positions:
                # Find parent position
                parts = gate.split(';')
                parent_pattern = ';'.join(parts[:-1]) + ')'
                parent = [g for g in gates if parent_pattern in g]
                if parent and parent[0] in positions:
                    px, py = positions[parent[0]]
                    positions[gate] = (px + 0.5, py - 1)
    
    # Handle any remaining gates
    for gate in gates:
        if gate not in positions:
            # Try to position based on parent
            parent = None
            for edge in edges:
                if edge[1] == gate:
                    parent = edge[0]
                    break
            
            if parent and parent in positions:
                px, py = positions[parent]
                # Offset from parent
                positions[gate] = (px + 1, py - 1.5)
            else:
                # Default position
                positions[gate] = (15, 5)
    
    # Define colors by zone
    zone_colors = {
        1: '#FF6B6B',  # Red
        2: '#4ECDC4',  # Teal
        3: '#45B7D1',  # Blue
        4: '#96CEB4',  # Green
        5: '#FECA57',  # Yellow
        6: '#DDA0DD',  # Plum
        0: '#95A5A6',  # Gray
        'S': '#2ECC71', # Source - Green
    }
    
    # Draw edges
    for edge in edges:
        if edge[0] in positions and edge[1] in positions:
            x1, y1 = positions[edge[0]]
            x2, y2 = positions[edge[1]]
            ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                       arrowprops=dict(arrowstyle='->', lw=1.5, color='gray'))
    
    # Draw nodes
    for gate, pos in positions.items():
        if gate == 'S':
            color = zone_colors['S']
            size = 500
        else:
            zone = gates.get(gate, {}).get('zone', 0)
            color = zone_colors.get(zone, '#95A5A6')
            size = 300
        
        ax.scatter(pos[0], pos[1], c=color, s=size, zorder=5, edgecolors='black', linewidth=1)
        
        # Add labels
        fontsize = 8 if gate != 'S' else 10
        ax.text(pos[0], pos[1]-0.5, gate, ha='center', va='top', fontsize=fontsize)
    
    # Create legend
    legend_elements = []
    for zone, color in sorted(zone_colors.items()):
        if zone == 'S':
            legend_elements.append(mpatches.Patch(color=color, label='Source'))
        elif isinstance(zone, int) and zone > 0:
            legend_elements.append(mpatches.Patch(color=color, label=f'Zone {zone}'))
    
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    # Set title and clean up
    ax.set_title('Munbon Irrigation Network - Updated Structure\n(Based on SCADA 2025-07-13 V0.95)', 
                fontsize=16, fontweight='bold')
    ax.set_xlim(-2, max(p[0] for p in positions.values()) + 2)
    ax.set_ylim(min(p[1] for p in positions.values()) - 2, 12)
    ax.axis('off')
    
    # Add canal labels
    ax.text(positions['M(0,0)'][0], positions['M(0,0)'][1] + 1, 'LMC (Main Canal)', 
           fontsize=12, fontweight='bold', ha='left')
    
    if 'M(0,1; 1,0)' in positions:
        ax.text(positions['M(0,1; 1,0)'][0], positions['M(0,1; 1,0)'][1] + 0.5, 'RMC', 
               fontsize=10, fontweight='bold')
    
    if 'M(0,3; 1,0)' in positions:
        ax.text(positions['M(0,3; 1,0)'][0], positions['M(0,3; 1,0)'][1] + 0.5, '9R-LMC', 
               fontsize=10, fontweight='bold')
    
    if 'M(0,12; 1,0)' in positions:
        ax.text(positions['M(0,12; 1,0)'][0], positions['M(0,12; 1,0)'][1] + 0.5, '38R-LMC', 
               fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.show()
    
    return positions

def save_network_structure(gates, edges, output_file='network_structure_updated.json'):
    """Save network structure to JSON"""
    
    network_data = {
        'gates': gates,
        'edges': edges,
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
        zone = str(info['zone'])
        if zone != '0' and zone != 'nan':
            if zone not in network_data['summary']['gates_by_zone']:
                network_data['summary']['gates_by_zone'][zone] = []
            network_data['summary']['gates_by_zone'][zone].append(gate)
    
    with open(output_file, 'w') as f:
        json.dump(network_data, f, indent=2)
    
    print(f"\nNetwork structure saved to {output_file}")

# Main execution
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    
    print("Loading network from SCADA file...")
    gates, edges = load_network_from_scada(scada_file)
    
    print(f"\nNetwork Summary:")
    print(f"Total gates: {len(gates)}")
    print(f"Total connections: {len(edges)}")
    
    # Count by canal
    canals = {}
    for gate, info in gates.items():
        canal = info['canal']
        canals[canal] = canals.get(canal, 0) + 1
    
    print("\nGates by canal:")
    for canal, count in sorted(canals.items()):
        print(f"  {canal}: {count} gates")
    
    # Visualize
    print("\nGenerating network visualization...")
    positions = visualize_network(gates, edges)
    
    # Save structure
    save_network_structure(gates, edges)
    
    print("\nNetwork update complete!")