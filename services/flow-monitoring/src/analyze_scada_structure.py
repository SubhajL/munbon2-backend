#!/usr/bin/env python3
"""
Analyze SCADA structure to understand network changes
"""

import pandas as pd
import json

def analyze_scada_structure(filename):
    """Analyze the SCADA Excel to understand gate structure"""
    
    # Read main sheet with proper header
    df = pd.read_excel(filename, sheet_name=0, header=1)
    
    print("=== SCADA Structure Analysis ===")
    print(f"Total rows: {len(df)}")
    
    # Extract gates
    gates = []
    network_edges = []
    
    prev_lmc_gate = None
    
    for idx, row in df.iterrows():
        if pd.notna(row.get('Gate Valve')):
            gate = row['Gate Valve']
            
            gate_info = {
                'gate': gate,
                'canal': row.get('Canal Name', ''),
                'km': row.get('km', ''),
                'zone': row.get('Zone', ''),
                'area_rai': row.get('Area (Rais)', 0),
                'q_max': row.get('q_max (m^3/s)', 0),
                'required_volume': row.get('Required Daily Volume (m3)', 0),
                'indices': {
                    'i': row.get('i', ''),
                    'j': row.get('j', ''),
                    'k': row.get('k', ''),
                    'l': row.get('l', ''),
                    'm': row.get('m', ''),
                    'n': row.get('n', '')
                }
            }
            
            gates.append(gate_info)
            
            # Determine connections
            # LMC progression
            if row.get('Canal Name') == 'LMC' and prev_lmc_gate:
                network_edges.append({
                    'from': prev_lmc_gate,
                    'to': gate,
                    'type': 'main_canal'
                })
            
            # Branch connections based on indices
            if pd.notna(row.get('k')):  # Has branch index
                i = str(row.get('i', '')).replace('.0', '')
                j = str(row.get('j', '')).replace('.0', '')
                parent = f"M({i},{j})"
                
                network_edges.append({
                    'from': parent,
                    'to': gate,
                    'type': 'branch'
                })
            
            if row.get('Canal Name') == 'LMC':
                prev_lmc_gate = gate
    
    # Print summary
    print(f"\nTotal gates found: {len(gates)}")
    
    # Gates by canal
    canals = {}
    for g in gates:
        canal = g['canal']
        if canal not in canals:
            canals[canal] = []
        canals[canal].append(g['gate'])
    
    print("\nGates by canal:")
    for canal, gate_list in canals.items():
        print(f"  {canal}: {len(gate_list)} gates")
        if len(gate_list) <= 10:
            print(f"    Gates: {', '.join(gate_list)}")
        else:
            print(f"    Gates: {', '.join(gate_list[:5])} ... {', '.join(gate_list[-5:])}")
    
    # Gates by zone
    zones = {}
    for g in gates:
        zone = str(g['zone'])
        if zone and zone != 'nan':
            if zone not in zones:
                zones[zone] = []
            zones[zone].append(g['gate'])
    
    print("\nGates by zone:")
    for zone, gate_list in zones.items():
        print(f"  Zone {zone}: {len(gate_list)} gates")
    
    # Check for renamed/modified gates
    print("\n=== Checking for Index Pattern Changes ===")
    
    # Look for gates with complex indices (branches)
    branch_gates = [g for g in gates if pd.notna(g['indices']['k'])]
    print(f"\nBranch gates (with k index): {len(branch_gates)}")
    
    # Save results
    results = {
        'gates': gates,
        'network_edges': network_edges,
        'summary': {
            'total_gates': len(gates),
            'canals': {k: len(v) for k, v in canals.items()},
            'zones': {k: len(v) for k, v in zones.items()}
        }
    }
    
    with open('scada_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nAnalysis saved to scada_analysis.json")
    
    # Also save simplified network for visualization
    simple_network = {
        'nodes': [g['gate'] for g in gates],
        'edges': [[e['from'], e['to']] for e in network_edges]
    }
    
    with open('network_simple.json', 'w') as f:
        json.dump(simple_network, f, indent=2)
    
    print("Network structure saved to network_simple.json")
    
    return gates, network_edges

# Main execution
if __name__ == "__main__":
    scada_file = "/Users/subhajlimanond/dev/munbon2-backend/SCADA Section Detailed Information 2025-07-13 V0.95 SL.xlsx"
    gates, edges = analyze_scada_structure(scada_file)