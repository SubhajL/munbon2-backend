#!/usr/bin/env python3
"""
Visualize Munbon Irrigation Network as a graph similar to the provided screenshot
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle
import numpy as np

def load_network():
    """Load the network structure"""
    with open('munbon_network_updated.json', 'r') as f:
        return json.load(f)

def create_network_visualization():
    """Create network visualization similar to the screenshot"""
    # Load network
    network = load_network()
    gates = network['gates']
    edges = network['edges']
    
    # Create figure
    fig, ax = plt.subplots(figsize=(20, 24))
    
    # Define positions for nodes - manual layout for clarity
    positions = {}
    
    # Source at top
    positions['S'] = (10, 24)
    
    # Outlet below source
    positions['M(0,0)'] = (10, 22)
    
    # M(0,1) branches left, M(0,2) continues down for LMC
    positions['M(0,1)'] = (4, 20)
    positions['M(0,2)'] = (10, 20)
    
    # Waste way branches right from outlet
    positions['M(0,0; 1,0)'] = (14, 21)
    
    # Main LMC line continues down
    y_lmc = 20
    for i in range(2, 15):  # M(0,2) through M(0,14)
        gate = f'M(0,{i})'
        if gate in gates:
            positions[gate] = (10, y_lmc)
            y_lmc -= 1.5
    
    # RMC branches from M(0,1) - spread horizontally
    rmc_gates = ['M (0,1; 1,0)', 'M (0,1; 1,1)', 'M (0,1; 1,2)', 'M (0,1; 1,3)', 'M (0,1; 1,4)']
    x_rmc = 0
    for i, gate in enumerate(rmc_gates):
        if gate in gates:
            positions[gate] = (x_rmc, 18 - i * 0.8)
    
    # FTO from RMC
    if 'M(0,1; 1,0; 1,0)' in gates:
        positions['M(0,1; 1,0; 1,0)'] = (-2, 16.5)
    
    # 4L-RMC branches from M(0,1; 1,1)
    fl_rmc_base = positions.get('M (0,1; 1,1)', (0, 17))
    fl_rmc_gates = ['M(0,1; 1,1; 1,0)', 'M(0,1; 1,1; 1,1)', 'M(0,1; 1,1; 1,2)', 
                    'M(0,1; 1,1; 1,3)', 'M(0,1; 1,1; 1,4)']
    for i, gate in enumerate(fl_rmc_gates):
        if gate in gates:
            positions[gate] = (fl_rmc_base[0] - 3 - i * 0.7, fl_rmc_base[1] - 1 - i * 0.5)
    
    # FTO337 from 4L-RMC
    if 'M(0,1; 1,1; 1,2; 1,0)' in gates:
        positions['M(0,1; 1,1; 1,2; 1,0)'] = (positions['M(0,1; 1,1; 1,2)'][0] - 1.5, 
                                               positions['M(0,1; 1,1; 1,2)'][1] - 0.8)
    
    # 9R-LMC branches from M(0,3) - to the right
    if 'M(0,3)' in positions:
        base_9r = positions['M(0,3)']
        nr_gates = ['M (0,3; 1,0)', 'M (0,3; 1,1)', 'M (0,3; 1,2)', 'M (0,3; 1,3)']
        for i, gate in enumerate(nr_gates):
            if gate in gates:
                positions[gate] = (base_9r[0] + 4 + i * 1.2, base_9r[1] - i * 0.5)
        
        # 7R and 7L branches
        if 'M (0,3; 1,1)' in positions:
            sub_base = positions['M (0,3; 1,1)']
            positions['M (0,3; 1,1; 1,0)'] = (sub_base[0] + 1, sub_base[1] - 1.5)
            positions['M (0,3; 1,1; 1,1)'] = (sub_base[0] + 2, sub_base[1] - 1.5)
            positions['M (0,3; 1,1; 2,0)'] = (sub_base[0] + 1, sub_base[1] - 2.5)
            positions['M (0,3; 1,1; 2,1)'] = (sub_base[0] + 2, sub_base[1] - 2.5)
    
    # 38R-LMC branches from M(0,12) - complex branching to the right
    if 'M(0,12)' in positions:
        base_38r = positions['M(0,12)']
        # Main 38R branches
        positions['M (0,12; 1,0)'] = (base_38r[0] + 4, base_38r[1])
        positions['M (0,12; 1,1)'] = (base_38r[0] + 4, base_38r[1] - 1)
        positions['M (0,12; 1,2)'] = (base_38r[0] + 4, base_38r[1] - 2)
        positions['M (0,12; 1,3)'] = (base_38r[0] + 4, base_38r[1] - 3)
        positions['M (0,12; 1,4)'] = (base_38r[0] + 4, base_38r[1] - 4)
        positions['M (0,12; 1,5)'] = (base_38r[0] + 4, base_38r[1] - 5)
        
        # Sub-branches
        # 1R-38R
        positions['M (0,12; 1,0; 1,0)'] = (base_38r[0] + 7, base_38r[1] + 0.3)
        positions['M (0,12; 1,0; 1,1)'] = (base_38r[0] + 7, base_38r[1] - 0.3)
        
        # 2R-38R and sub-branches
        positions['M (0,12; 1,1; 1,0)'] = (base_38r[0] + 7, base_38r[1] - 0.7)
        positions['M (0,12; 1,1; 1,1)'] = (base_38r[0] + 7, base_38r[1] - 1)
        positions['M (0,12; 1,1; 1,2)'] = (base_38r[0] + 7, base_38r[1] - 1.3)
        
        # 1R-2R-38R
        positions['M (0,12; 1,1; 1,0; 1,0)'] = (base_38r[0] + 10, base_38r[1] - 0.5)
        positions['M (0,12; 1,1; 1,0; 1,1)'] = (base_38r[0] + 10, base_38r[1] - 0.7)
        positions['M (0,12; 1,1; 1,0; 1,2)'] = (base_38r[0] + 10, base_38r[1] - 0.9)
        
        # 4L-38R
        positions['M (0,12; 1,2; 1,0)'] = (base_38r[0] + 7, base_38r[1] - 1.7)
        positions['M (0,12; 1,2; 1,1)'] = (base_38r[0] + 7, base_38r[1] - 2)
        positions['M (0,12; 1,2; 1,2)'] = (base_38r[0] + 7, base_38r[1] - 2.3)
        
        # 5R-4L
        positions['M (0,12; 1,2; 1,0; 1,0)'] = (base_38r[0] + 10, base_38r[1] - 1.5)
        positions['M (0,12; 1,2; 1,0; 1,1)'] = (base_38r[0] + 10, base_38r[1] - 1.9)
        
        # 6R-38R
        positions['M (0,12; 1,3; 1,0)'] = (base_38r[0] + 7, base_38r[1] - 2.7)
        positions['M (0,12; 1,3; 1,1)'] = (base_38r[0] + 7, base_38r[1] - 3.3)
        
        # 8R-38R
        positions['M (0,12; 1,4; 1,0)'] = (base_38r[0] + 7, base_38r[1] - 3.7)
        positions['M (0,12; 1,4; 1,1)'] = (base_38r[0] + 7, base_38r[1] - 4.3)
    
    # Draw edges
    for edge in edges:
        if edge[0] in positions and edge[1] in positions:
            x1, y1 = positions[edge[0]]
            x2, y2 = positions[edge[1]]
            
            # Draw arrow
            ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                       arrowprops=dict(arrowstyle='->', lw=1.5, color='gray', alpha=0.7))
    
    # Draw nodes
    for node, (x, y) in positions.items():
        if node == 'S':
            # Source node - green
            circle = Circle((x, y), 0.3, color='darkgreen', zorder=10)
            ax.add_patch(circle)
            ax.text(x, y, 'S', ha='center', va='center', fontsize=12, 
                   fontweight='bold', color='white', zorder=11)
        else:
            # Gate information
            info = gates.get(node, {})
            
            # Determine color by zone
            zone = info.get('zone', 0)
            colors = {
                1: '#FF6B6B',  # Red
                2: '#4ECDC4',  # Teal  
                3: '#45B7D1',  # Blue
                4: '#96CEB4',  # Green
                5: '#FECA57',  # Yellow
                6: '#DDA0DD',  # Plum
                0: '#95A5A6'   # Gray
            }
            node_color = colors.get(zone, '#95A5A6')
            
            # Draw node circle
            circle = Circle((x, y), 0.25, color=node_color, ec='black', 
                          linewidth=1, zorder=10)
            ax.add_patch(circle)
            
            # Add label below node
            ax.text(x, y - 0.4, node, ha='center', va='top', fontsize=8)
            
            # Add zone label if exists
            if zone > 0:
                ax.text(x + 0.3, y + 0.3, f'Z{zone}', ha='left', va='bottom', 
                       fontsize=7, style='italic', color='darkgray')
    
    # Create legend
    legend_elements = []
    zone_names = {
        1: 'Zone 1',
        2: 'Zone 2', 
        3: 'Zone 3',
        4: 'Zone 4',
        5: 'Zone 5',
        6: 'Zone 6'
    }
    
    colors_map = {
        1: '#FF6B6B',
        2: '#4ECDC4',
        3: '#45B7D1',
        4: '#96CEB4',
        5: '#FECA57',
        6: '#DDA0DD'
    }
    
    for zone, color in sorted(colors_map.items()):
        legend_elements.append(mpatches.Patch(color=color, label=zone_names[zone]))
    
    legend_elements.append(mpatches.Patch(color='darkgreen', label='Source'))
    
    ax.legend(handles=legend_elements, loc='upper left', fontsize=10)
    
    # Set title
    ax.set_title('Munbon Irrigation Network Structure\n(Updated from SCADA 2025-07-13)', 
                fontsize=16, fontweight='bold', pad=20)
    
    # Set axis properties
    ax.set_xlim(-8, 22)
    ax.set_ylim(-5, 25)
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Add grid for reference
    ax.grid(True, alpha=0.1)
    
    # Save figure
    plt.tight_layout()
    plt.savefig('munbon_network_graph.png', dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.show()

if __name__ == "__main__":
    print("Creating network visualization...")
    create_network_visualization()
    print("Network graph saved as munbon_network_graph.png")