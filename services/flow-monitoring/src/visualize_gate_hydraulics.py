#!/usr/bin/env python3
"""
Visualization of Gate-Specific Hydraulics in Munbon Network
Shows how different gate types and water levels affect flow
"""

from water_gate_controller_enhanced import WaterGateControllerEnhanced
from gate_hydraulics import GateType
import json

def create_gate_hydraulics_visualization():
    """Create visualization of gate hydraulics across the network"""
    
    # Initialize enhanced controller
    controller = WaterGateControllerEnhanced(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== GATE-SPECIFIC HYDRAULICS ANALYSIS ===\n")
    
    # Analyze key gates
    key_gates = [
        ('M(0,0)', 'Main Outlet', 'Source'),
        ('M(0,1)', 'RMC Branch', 'Major Branch'),
        ('M(0,2)', 'LMC Start', 'Main Canal'),
        ('M(0,3)', '9R Branch', 'Zone 3 Supply'),
        ('M(0,12)', '38R Branch', 'Zone 4/5 Supply'),
        ('M (0,1; 1,1)', '4L-RMC', 'Lateral'),
        ('M(0,1; 1,1; 1,2; 1,0)', 'FTO337', 'Farm Turnout')
    ]
    
    # Test scenarios
    scenarios = [
        ('Normal Operation', {'upstream': 221.0, 'downstream': 219.0}),
        ('High Water Level', {'upstream': 223.0, 'downstream': 221.0}),
        ('Low Water Level', {'upstream': 219.0, 'downstream': 217.5})
    ]
    
    results = {}
    
    for scenario_name, levels in scenarios:
        print(f"\n{'='*60}")
        print(f"SCENARIO: {scenario_name}")
        print(f"Upstream Level: {levels['upstream']} m, Downstream Level: {levels['downstream']} m")
        print(f"{'='*60}")
        
        scenario_results = {}
        
        for gate_id, desc, gate_class in key_gates:
            if gate_id not in controller.gate_properties:
                continue
                
            gate = controller.gate_properties[gate_id]
            
            print(f"\n{desc} ({gate_id}) - {gate.gate_type.value}")
            print(f"Dimensions: {gate.width_m}m × {gate.height_m}m")
            print("-" * 50)
            
            # Test different openings
            openings = [25, 50, 75, 100]
            gate_results = []
            
            print(f"{'Opening':<10} {'Flow (m³/s)':<12} {'Velocity':<10} {'Regime':<15} {'Froude':<8}")
            print("-" * 60)
            
            for opening_pct in openings:
                result = controller.open_gate_realistic(
                    gate_id, opening_pct,
                    upstream_level=levels['upstream'],
                    downstream_level=levels['downstream']
                )
                
                gate_results.append({
                    'opening_percent': opening_pct,
                    'flow_rate': result['flow_rate_m3s'],
                    'velocity': result['velocity_ms'],
                    'regime': result['flow_regime']
                })
                
                # Calculate Froude number
                if 'opening_m' in result and result['opening_m'] > 0:
                    froude = result['velocity_ms'] / (9.81 * result['opening_m'])**0.5
                else:
                    froude = 0
                
                print(f"{opening_pct:>3d}%      {result['flow_rate_m3s']:>8.2f}     "
                      f"{result['velocity_ms']:>6.2f}     {result['flow_regime']:<15} {froude:>5.2f}")
            
            scenario_results[gate_id] = gate_results
        
        results[scenario_name] = scenario_results
    
    # Create HTML visualization
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Munbon Irrigation - Gate Hydraulics Analysis</title>
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
        h1 { color: #333; text-align: center; }
        h2 { color: #666; margin-top: 30px; }
        .gate-info {
            background: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .gate-specs {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .gate-card {
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 5px;
            background: #f9f9f9;
        }
        .gate-type-sluice { border-left: 4px solid #FF6B6B; }
        .gate-type-radial { border-left: 4px solid #4ECDC4; }
        .gate-type-butterfly { border-left: 4px solid #45B7D1; }
        .warning { color: #d32f2f; font-weight: bold; }
        .chart { margin: 30px 0; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Gate-Specific Hydraulics Analysis</h1>
        
        <div class="gate-info">
            <h3>Gate Types in Network</h3>
            <ul>
                <li><strong>Sluice Gates:</strong> Vertical lift gates - most common type</li>
                <li><strong>Radial Gates:</strong> Curved gates - used in main canals</li>
                <li><strong>Butterfly Valves:</strong> Rotating disc - used for farm turnouts</li>
            </ul>
        </div>
        
        <h2>Gate Specifications</h2>
        <div class="gate-specs">
"""
    
    # Add gate specification cards
    specs = controller.export_gate_specifications()
    for gate_id in ['M(0,0)', 'M(0,1)', 'M(0,3)', 'M(0,12)', 'M(0,1; 1,1; 1,2; 1,0)']:
        if gate_id in specs['gates']:
            gate_info = specs['gates'][gate_id]
            gate_type_class = gate_info['type'].replace('_', '-')
            
            html_content += f"""
            <div class="gate-card gate-type-{gate_type_class}">
                <h4>{gate_id}</h4>
                <p><strong>Type:</strong> {gate_info['type']}</p>
                <p><strong>Size:</strong> {gate_info['dimensions']['width_m']}m × {gate_info['dimensions']['height_m']}m</p>
                <p><strong>Location:</strong> {gate_info['location']['canal']}</p>
                <p><strong>Capacity:</strong> {gate_info['capacity']['q_max_m3s']:.1f} m³/s</p>
            </div>
"""
    
    html_content += """
        </div>
        
        <h2>Flow Characteristics by Water Level</h2>
        <div id="flowChart" class="chart"></div>
        
        <h2>Gate Performance Curves</h2>
        <div id="performanceChart" class="chart"></div>
        
        <h2>Hydraulic Analysis Summary</h2>
        <table>
            <tr>
                <th>Gate</th>
                <th>Type</th>
                <th>Normal Flow @ 50%</th>
                <th>Max Velocity</th>
                <th>Flow Regime</th>
                <th>Operational Notes</th>
            </tr>
"""
    
    # Add summary table
    for gate_id, desc, _ in key_gates[:5]:
        if gate_id in controller.gate_properties:
            gate = controller.gate_properties[gate_id]
            normal_result = results['Normal Operation'].get(gate_id, [{}])[1] if gate_id in results['Normal Operation'] else {}
            max_velocity = max([r['velocity'] for r in results['Normal Operation'].get(gate_id, [{'velocity': 0}])], default=0)
            
            operational_note = ""
            if max_velocity > 3.0:
                operational_note = '<span class="warning">⚠️ High velocity risk</span>'
            elif gate.gate_type == GateType.BUTTERFLY_VALVE:
                operational_note = "Good for flow control"
            elif gate.gate_type == GateType.RADIAL_GATE:
                operational_note = "Efficient for large flows"
            else:
                operational_note = "Standard operation"
            
            html_content += f"""
            <tr>
                <td>{gate_id}</td>
                <td>{gate.gate_type.value}</td>
                <td>{normal_result.get('flow_rate', 0):.1f} m³/s</td>
                <td>{max_velocity:.2f} m/s</td>
                <td>{normal_result.get('regime', 'N/A')}</td>
                <td>{operational_note}</td>
            </tr>
"""
    
    html_content += """
        </table>
        
        <script>
            // Flow chart data
            var flowData = [];
            
"""
    
    # Add JavaScript data for charts
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    for i, (scenario_name, _) in enumerate(scenarios):
        x_vals = []
        y_vals = []
        text_vals = []
        
        for gate_id, desc, _ in key_gates[:5]:
            if gate_id in results[scenario_name]:
                gate_results = results[scenario_name][gate_id]
                for r in gate_results:
                    if r['opening_percent'] == 50:  # 50% opening
                        x_vals.append(desc)
                        y_vals.append(r['flow_rate'])
                        text_vals.append(f"{r['velocity']:.1f} m/s")
        
        html_content += f"""
            flowData.push({{
                x: {json.dumps(x_vals)},
                y: {json.dumps(y_vals)},
                text: {json.dumps(text_vals)},
                name: '{scenario_name}',
                type: 'bar',
                marker: {{ color: '{colors[i]}' }}
            }});
"""
    
    html_content += """
            var layout1 = {
                title: 'Flow Rate at 50% Gate Opening',
                xaxis: { title: 'Gate Location' },
                yaxis: { title: 'Flow Rate (m³/s)' },
                barmode: 'group'
            };
            
            Plotly.newPlot('flowChart', flowData, layout1);
            
            // Performance curves
            var performanceData = [];
            var openings = [25, 50, 75, 100];
            
"""
    
    # Add performance curve data for main gates
    for gate_id, desc, _ in [('M(0,0)', 'Main Outlet', 'Source'), 
                              ('M(0,3)', '9R Branch', 'Zone 3'),
                              ('M(0,12)', '38R Branch', 'Zone 4/5')]:
        if gate_id in results['Normal Operation']:
            flows = [r['flow_rate'] for r in results['Normal Operation'][gate_id]]
            
            html_content += f"""
            performanceData.push({{
                x: {json.dumps(openings)},
                y: {json.dumps(flows)},
                name: '{desc}',
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ width: 3 }}
            }});
"""
    
    html_content += """
            var layout2 = {
                title: 'Gate Performance Curves (Normal Water Level)',
                xaxis: { title: 'Gate Opening (%)' },
                yaxis: { title: 'Flow Rate (m³/s)' },
                hovermode: 'x unified'
            };
            
            Plotly.newPlot('performanceChart', performanceData, layout2);
        </script>
        
        <div class="gate-info" style="margin-top: 30px;">
            <h3>Key Findings</h3>
            <ul>
                <li>Gate flow is highly dependent on upstream/downstream water levels</li>
                <li>Sluice gates show typical quadratic flow-opening relationship</li>
                <li>Radial gates maintain higher efficiency at partial openings</li>
                <li>Butterfly valves provide good flow control for farm turnouts</li>
                <li>Most gates operate in free flow regime under normal conditions</li>
                <li>Submerged flow occurs during high downstream water levels</li>
            </ul>
        </div>
    </div>
</body>
</html>"""
    
    # Save HTML file
    with open('gate_hydraulics_analysis.html', 'w') as f:
        f.write(html_content)
    
    print("\n\nVisualization saved to gate_hydraulics_analysis.html")
    
    # Save detailed results
    with open('gate_hydraulics_results.json', 'w') as f:
        json.dump({
            'gate_specifications': specs,
            'hydraulic_results': results
        }, f, indent=2)
    
    print("Detailed results saved to gate_hydraulics_results.json")

if __name__ == "__main__":
    create_gate_hydraulics_visualization()