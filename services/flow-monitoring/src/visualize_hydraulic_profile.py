#!/usr/bin/env python3
"""
Visualization of hydraulic profiles and water levels in the network
Shows actual water surface elevations before and after gates
"""

from hydraulic_network_model import HydraulicNetworkModel
import json
import numpy as np

def create_hydraulic_visualization():
    """Create comprehensive hydraulic visualization"""
    
    # Initialize model
    model = HydraulicNetworkModel(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== HYDRAULIC PROFILE VISUALIZATION ===\n")
    
    # Scenario 1: Normal operation
    print("Scenario 1: Normal Operation")
    print("-" * 60)
    
    # Set reservoir level
    model.update_node_levels('Source', 221.0)
    
    # Open gates in sequence
    gate_operations = [
        # Main outlet
        {'upstream': 'Source', 'downstream': 'M(0,0)', 'opening': 0.8},
        
        # Split to RMC and LMC
        {'upstream': 'M(0,0)', 'downstream': 'M(0,1)', 'opening': 0.4},  # RMC
        {'upstream': 'M(0,0)', 'downstream': 'M(0,2)', 'opening': 0.6},  # LMC
        
        # LMC progression
        {'upstream': 'M(0,2)', 'downstream': 'M(0,3)', 'opening': 0.5},
        {'upstream': 'M(0,3)', 'downstream': 'M(0,4)', 'opening': 0.5},
        {'upstream': 'M(0,4)', 'downstream': 'M(0,5)', 'opening': 0.5},
        
        # Branch to zones
        {'upstream': 'M(0,3)', 'downstream': 'M (0,3; 1,0)', 'opening': 0.3},  # 9R-LMC
        {'upstream': 'M(0,1)', 'downstream': 'M (0,1; 1,0)', 'opening': 0.3},  # RMC lateral
    ]
    
    # Simulate
    results = model.simulate_gate_operation(gate_operations)
    
    # Create visualization data
    viz_data = {
        'scenarios': {},
        'profiles': {},
        'gate_effects': []
    }
    
    # Collect gate effects (water level drop across gates)
    for op in results['operations']:
        gate = op['gate']
        parts = gate.split('->')
        if len(parts) == 2:
            up_node = parts[0]
            down_node = parts[1]
            
            up_data = results['node_levels'].get(up_node, {})
            down_data = results['node_levels'].get(down_node, {})
            
            gate_effect = {
                'gate': gate,
                'upstream_node': up_node,
                'downstream_node': down_node,
                'upstream_level': up_data.get('water_level', 0),
                'downstream_level': down_data.get('water_level', 0),
                'head_drop': op['head_diff'],
                'flow_rate': op['flow_rate'],
                'velocity': op['velocity'],
                'regime': op['regime']
            }
            
            viz_data['gate_effects'].append(gate_effect)
            
            print(f"\nGate: {gate}")
            print(f"  Upstream level: {gate_effect['upstream_level']:.2f}m")
            print(f"  Downstream level: {gate_effect['downstream_level']:.2f}m")
            print(f"  Head drop: {gate_effect['head_drop']:.2f}m")
            print(f"  Flow: {gate_effect['flow_rate']:.2f} m³/s")
    
    # Create profiles for main paths
    main_paths = {
        'LMC Main': ['Source', 'M(0,0)', 'M(0,2)', 'M(0,3)', 'M(0,5)', 'M(0,12)'],
        'RMC Branch': ['Source', 'M(0,0)', 'M(0,1)', 'M (0,1; 1,0)', 'M(0,1; 1,0; 1,0)'],
        '9R-LMC': ['M(0,0)', 'M(0,2)', 'M(0,3)', 'M (0,3; 1,0)', 'M (0,3; 1,1)']
    }
    
    for path_name, path in main_paths.items():
        # Filter valid nodes
        valid_path = [n for n in path if n in model.node_levels]
        if len(valid_path) > 1:
            profile = model.create_hydraulic_profile_plot(valid_path)
            viz_data['profiles'][path_name] = profile
    
    # Save scenario
    viz_data['scenarios']['Normal Operation'] = {
        'node_levels': results['node_levels'],
        'operations': results['operations'],
        'reach_hydraulics': results['reach_hydraulics']
    }
    
    # Create HTML visualization
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Munbon Irrigation - Hydraulic Profile Visualization</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1, h2 { color: #333; }
        .info-box {
            background: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .gate-effect {
            background: #fff3cd;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #ffc107;
        }
        .chart { 
            margin: 30px 0;
            min-height: 500px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        th {
            background: #4CAF50;
            color: white;
        }
        .level-drop { color: #d32f2f; font-weight: bold; }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Hydraulic Profile Analysis - Munbon Irrigation Network</h1>
        
        <div class="info-box">
            <h3>Understanding Water Levels in the Network</h3>
            <p>This visualization shows:</p>
            <ul>
                <li><strong>Water Surface Elevation:</strong> Actual water level (m MSL) at each node</li>
                <li><strong>Head Loss Across Gates:</strong> Water level drop due to gate restrictions</li>
                <li><strong>Canal Friction Losses:</strong> Gradual water level decrease along canals</li>
                <li><strong>Energy Grade Line:</strong> Total energy including velocity head</li>
            </ul>
        </div>
        
        <h2>1. Longitudinal Hydraulic Profiles</h2>
        <div id="profileChart" class="chart"></div>
        
        <h2>2. Water Level Changes Across Gates</h2>
        <div id="gateEffectChart" class="chart"></div>
        
        <h2>3. Gate Operation Summary</h2>
        <table>
            <tr>
                <th>Gate</th>
                <th>Upstream Level</th>
                <th>Downstream Level</th>
                <th>Head Drop</th>
                <th>Flow Rate</th>
                <th>Velocity</th>
                <th>Flow Regime</th>
            </tr>
"""
    
    # Add gate data to table
    for gate in viz_data['gate_effects']:
        html_content += f"""
            <tr>
                <td>{gate['gate']}</td>
                <td>{gate['upstream_level']:.2f} m</td>
                <td>{gate['downstream_level']:.2f} m</td>
                <td class="level-drop">{gate['head_drop']:.2f} m</td>
                <td>{gate['flow_rate']:.2f} m³/s</td>
                <td>{gate['velocity']:.2f} m/s</td>
                <td>{gate['regime']}</td>
            </tr>
"""
    
    html_content += """
        </table>
        
        <h2>4. Network-Wide Water Levels</h2>
        <div id="networkLevelChart" class="chart"></div>
        
        <div class="info-box" style="margin-top: 30px;">
            <h3>Key Observations</h3>
            <ul>
                <li><strong>Major Head Losses:</strong> Occur at gate restrictions (1-3m typical)</li>
                <li><strong>Friction Losses:</strong> Gradual decrease along canals (0.1-0.5m/km)</li>
                <li><strong>Backwater Effects:</strong> High downstream levels can reduce gate capacity</li>
                <li><strong>Energy Conservation:</strong> Total energy decreases downstream due to losses</li>
            </ul>
        </div>
        
        <script>
            // Profile data
"""
    
    # Add JavaScript data for profiles
    html_content += f"""
            var profileTraces = [];
            
            // Canal bottom profile
"""
    
    # Add profile traces for each path
    colors = {'LMC Main': '#FF6B6B', 'RMC Branch': '#4ECDC4', '9R-LMC': '#45B7D1'}
    
    for path_name, profile in viz_data['profiles'].items():
        if path_name in colors:
            # Convert distances to km
            distances_km = [d/1000 for d in profile['distance']]
            
            # Canal bottom
            html_content += f"""
            profileTraces.push({{
                x: {json.dumps(distances_km)},
                y: {json.dumps(profile['canal_bottom'])},
                name: '{path_name} - Bottom',
                type: 'scatter',
                mode: 'lines',
                line: {{ color: '{colors[path_name]}', width: 2, dash: 'dash' }},
                showlegend: false
            }});
            
            // Water surface
            profileTraces.push({{
                x: {json.dumps(distances_km)},
                y: {json.dumps(profile['water_surface'])},
                name: '{path_name} - Water',
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ color: '{colors[path_name]}', width: 3 }},
                marker: {{ size: 8 }}
            }});
            
            // Node annotations
"""
            for i, node in enumerate(profile['nodes']):
                if i % 2 == 0:  # Annotate every other node
                    html_content += f"""
            profileTraces.push({{
                x: [{distances_km[i]}],
                y: [{profile['water_surface'][i]}],
                mode: 'text',
                text: ['{node}'],
                textposition: 'top',
                showlegend: false
            }});
"""
    
    html_content += """
            var profileLayout = {
                title: 'Hydraulic Profiles Along Main Canals',
                xaxis: { 
                    title: 'Distance (km)',
                    gridcolor: '#eee'
                },
                yaxis: { 
                    title: 'Elevation (m MSL)',
                    gridcolor: '#eee',
                    range: [213, 222]
                },
                hovermode: 'x unified',
                plot_bgcolor: '#fafafa'
            };
            
            Plotly.newPlot('profileChart', profileTraces, profileLayout);
            
            // Gate effect visualization
            var gateNames = [];
            var upstreamLevels = [];
            var downstreamLevels = [];
            var headDrops = [];
            
"""
    
    # Add gate effect data
    gate_data = viz_data['gate_effects'][:10]  # First 10 gates
    gate_names = [g['gate'] for g in gate_data]
    upstream_levels = [g['upstream_level'] for g in gate_data]
    downstream_levels = [g['downstream_level'] for g in gate_data]
    head_drops = [g['head_drop'] for g in gate_data]
    
    html_content += f"""
            gateNames = {json.dumps(gate_names)};
            upstreamLevels = {json.dumps(upstream_levels)};
            downstreamLevels = {json.dumps(downstream_levels)};
            headDrops = {json.dumps(head_drops)};
            
            var trace1 = {{
                x: gateNames,
                y: upstreamLevels,
                name: 'Upstream Level',
                type: 'bar',
                marker: {{ color: '#4CAF50' }}
            }};
            
            var trace2 = {{
                x: gateNames,
                y: downstreamLevels,
                name: 'Downstream Level',
                type: 'bar',
                marker: {{ color: '#2196F3' }}
            }};
            
            var trace3 = {{
                x: gateNames,
                y: headDrops,
                name: 'Head Drop',
                type: 'scatter',
                mode: 'lines+markers',
                yaxis: 'y2',
                line: {{ color: '#FF5722', width: 3 }},
                marker: {{ size: 10 }}
            }};
            
            var gateData = [trace1, trace2, trace3];
            
            var gateLayout = {{
                title: 'Water Level Changes Across Gates',
                xaxis: {{ 
                    title: 'Gate',
                    tickangle: -45
                }},
                yaxis: {{ 
                    title: 'Water Level (m MSL)',
                    side: 'left'
                }},
                yaxis2: {{
                    title: 'Head Drop (m)',
                    side: 'right',
                    overlaying: 'y',
                    showgrid: false
                }},
                barmode: 'group',
                hovermode: 'x unified'
            }};
            
            Plotly.newPlot('gateEffectChart', gateData, gateLayout);
            
            // Network-wide level visualization
            var nodeLevels = [];
            var nodeNames = [];
            var nodeDepths = [];
            
"""
    
    # Add network level data
    node_data = []
    for node_id, data in results['node_levels'].items():
        if node_id != 'Source' and 'M(' in node_id:
            node_data.append({
                'id': node_id,
                'level': data['water_level'],
                'depth': data['water_depth'],
                'bottom': data['canal_bottom']
            })
    
    # Sort by water level
    node_data.sort(key=lambda x: x['level'], reverse=True)
    node_data = node_data[:20]  # Top 20 nodes
    
    node_names = [n['id'] for n in node_data]
    node_levels = [n['level'] for n in node_data]
    node_bottoms = [n['bottom'] for n in node_data]
    
    html_content += f"""
            nodeNames = {json.dumps(node_names)};
            nodeLevels = {json.dumps(node_levels)};
            nodeBottoms = {json.dumps(node_bottoms)};
            
            var networkTrace1 = {{
                x: nodeNames,
                y: nodeLevels,
                name: 'Water Surface',
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ color: '#2196F3', width: 3 }},
                marker: {{ size: 10 }}
            }};
            
            var networkTrace2 = {{
                x: nodeNames,
                y: nodeBottoms,
                name: 'Canal Bottom',
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ color: '#795548', width: 2, dash: 'dash' }},
                marker: {{ size: 6 }}
            }};
            
            // Add water depth bars
            var waterDepths = [];
            for (var i = 0; i < nodeLevels.length; i++) {{
                waterDepths.push(nodeLevels[i] - nodeBottoms[i]);
            }}
            
            var networkTrace3 = {{
                x: nodeNames,
                y: waterDepths,
                name: 'Water Depth',
                type: 'bar',
                yaxis: 'y2',
                marker: {{ color: 'rgba(33, 150, 243, 0.3)' }}
            }};
            
            var networkLayout = {{
                title: 'Water Levels Throughout Network',
                xaxis: {{ 
                    title: 'Network Node',
                    tickangle: -45
                }},
                yaxis: {{ 
                    title: 'Elevation (m MSL)',
                    side: 'left'
                }},
                yaxis2: {{
                    title: 'Water Depth (m)',
                    side: 'right',
                    overlaying: 'y',
                    showgrid: false,
                    range: [0, 5]
                }},
                hovermode: 'x unified'
            }};
            
            Plotly.newPlot('networkLevelChart', [networkTrace1, networkTrace2, networkTrace3], networkLayout);
        </script>
    </div>
</body>
</html>
"""
    
    # Save HTML
    with open('hydraulic_profile_visualization.html', 'w') as f:
        f.write(html_content)
    
    print("\n\nVisualization saved to hydraulic_profile_visualization.html")
    
    # Save data
    with open('hydraulic_profile_data.json', 'w') as f:
        json.dump(viz_data, f, indent=2, default=str)
    
    print("Data saved to hydraulic_profile_data.json")

if __name__ == "__main__":
    create_hydraulic_visualization()