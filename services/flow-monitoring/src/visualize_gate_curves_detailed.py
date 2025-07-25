#!/usr/bin/env python3
"""
Detailed visualization of gate curves showing non-linear behavior
under different hydraulic conditions
"""

import numpy as np
from gate_hydraulics import GateHydraulics, GateProperties, HydraulicConditions, GateType
import json

def create_detailed_gate_curves():
    """Create detailed visualization showing how curves change with conditions"""
    
    hydraulics = GateHydraulics()
    
    # Define a standard gate for analysis
    gate = GateProperties(
        gate_id="M(0,0)",
        gate_type=GateType.SLUICE_GATE,
        width_m=2.5,
        height_m=1.5,
        sill_elevation_m=218.0,  # Actual sill elevation
        discharge_coefficient=0.61,
        contraction_coefficient=0.61,
        max_opening_m=1.2
    )
    
    print("=== DETAILED GATE CURVE ANALYSIS ===\n")
    print(f"Gate: {gate.gate_id}")
    print(f"Type: {gate.gate_type.value}")
    print(f"Dimensions: {gate.width_m}m × {gate.height_m}m")
    print(f"Sill Elevation: {gate.sill_elevation_m}m\n")
    
    # Different scenarios to show curve variations
    scenarios = [
        {
            "name": "High Submergence (Your Case)",
            "description": "Upstream 221m, Downstream 219m - Nearly linear",
            "upstream": 221.0,
            "downstream": 219.0
        },
        {
            "name": "Moderate Submergence",
            "description": "Upstream 221m, Downstream 218.5m - Some curvature",
            "upstream": 221.0,
            "downstream": 218.5
        },
        {
            "name": "Low Submergence",
            "description": "Upstream 221m, Downstream 218m - More curvature",
            "upstream": 221.0,
            "downstream": 218.0
        },
        {
            "name": "Free Flow",
            "description": "Upstream 221m, Downstream 217m - Maximum curvature",
            "upstream": 221.0,
            "downstream": 217.0
        },
        {
            "name": "Variable Head",
            "description": "Head decreases with flow - Realistic operation",
            "upstream": 221.0,
            "downstream": 218.0,
            "variable": True
        }
    ]
    
    # Calculate curves
    results = {}
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"{scenario['name']}")
        print(f"{scenario['description']}")
        print(f"{'='*60}")
        
        openings = np.linspace(0, 100, 21)  # 0 to 100% in 5% steps
        flows = []
        velocities = []
        regimes = []
        
        for opening_pct in openings:
            opening_m = gate.max_opening_m * (opening_pct / 100.0)
            
            # Handle variable head scenario
            if scenario.get('variable', False):
                # Simulate head loss with increased flow
                # Assume 0.5m drawdown at max flow
                head_loss = 0.5 * (opening_pct / 100.0)
                upstream = scenario['upstream'] - head_loss
                # Downstream rises slightly with flow
                downstream = scenario['downstream'] + 0.2 * (opening_pct / 100.0)
            else:
                upstream = scenario['upstream']
                downstream = scenario['downstream']
            
            conditions = HydraulicConditions(
                upstream_water_level_m=upstream,
                downstream_water_level_m=downstream,
                gate_opening_m=opening_m
            )
            
            result = hydraulics.calculate_gate_flow(gate, conditions)
            flows.append(result['flow_rate_m3s'])
            velocities.append(result['velocity_ms'])
            regimes.append(result['flow_regime'])
        
        results[scenario['name']] = {
            'openings': openings.tolist(),
            'flows': flows,
            'velocities': velocities,
            'regimes': regimes,
            'scenario': scenario
        }
        
        # Print sample points
        print(f"\n{'Opening':<10} {'Flow (m³/s)':<12} {'Velocity':<10} {'Regime':<20} {'dQ/da':<10}")
        print("-" * 70)
        
        for i in [0, 5, 10, 15, 20]:  # 0%, 25%, 50%, 75%, 100%
            if i > 0:
                dQ = flows[i] - flows[i-1]
                da = (openings[i] - openings[i-1]) / 100.0 * gate.max_opening_m
                dQ_da = dQ / da if da > 0 else 0
            else:
                dQ_da = 0
                
            print(f"{openings[i]:>3.0f}%      {flows[i]:>8.2f}     "
                  f"{velocities[i]:>6.2f}     {regimes[i]:<20} {dQ_da:>6.2f}")
    
    # Create enhanced HTML visualization
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Gate Performance Curves - Detailed Analysis</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
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
        .equation {
            background: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            text-align: center;
            font-size: 1.2em;
        }
        .explanation {
            background: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .chart { 
            margin: 30px 0; 
            min-height: 500px;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }
        .scenario-box {
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 5px;
        }
        .highlight {
            background: yellow;
            padding: 2px 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Understanding Gate Performance Curves</h1>
        
        <div class="equation">
            $$Q = C_d \\times b \\times a \\times \\sqrt{2g \\times h} \\times RF$$
            <p style="font-size: 0.9em; margin-top: 10px;">
            Where: RF = Reduction Factor for submerged flow = \\(\\sqrt{1 - (h_2/h_1)^2}\\)
            </p>
        </div>
        
        <div class="explanation">
            <h3>Why Gate Curves Can Be Linear or Non-Linear</h3>
            <p>The shape of gate performance curves depends on several factors:</p>
            <ul>
                <li><strong>Submergence Ratio (h₂/h₁):</strong> Higher submergence → More linear curves</li>
                <li><strong>Head Variation:</strong> Constant head → Linear; Variable head → Curved</li>
                <li><strong>Flow Regime:</strong> Transitions between free/submerged flow create sharp curves</li>
                <li><strong>Gate Type:</strong> Butterfly valves have inherently non-linear area changes</li>
            </ul>
        </div>
        
        <h2>1. Flow Rate vs Gate Opening - Different Conditions</h2>
        <div id="flowChart" class="chart"></div>
        
        <h2>2. Your Specific Case - Why Nearly Linear?</h2>
        <div class="grid">
            <div class="scenario-box">
                <h3>High Submergence Scenario</h3>
                <p><strong>Upstream:</strong> 221m</p>
                <p><strong>Downstream:</strong> 219m</p>
                <p><strong>Submergence Ratio:</strong> 219/221 = <span class="highlight">99.1%</span></p>
                <p><strong>Reduction Factor:</strong> √(1 - 0.991²) = <span class="highlight">0.134</span></p>
                <p><strong>Result:</strong> Flow is heavily restricted by downstream level, making it proportional mainly to gate opening (a).</p>
            </div>
            <div class="scenario-box">
                <h3>Mathematical Explanation</h3>
                <p>When RF is constant (high submergence):</p>
                <p style="text-align: center; font-size: 1.1em;">Q = <span class="highlight">k × a</span></p>
                <p>Where k = Cd × b × √(2gh) × RF = constant</p>
                <p>This creates a <strong>linear relationship</strong> between Q and a!</p>
            </div>
        </div>
        
        <h2>3. Velocity Profiles</h2>
        <div id="velocityChart" class="chart"></div>
        
        <h2>4. Flow Regime Transitions</h2>
        <div id="regimeChart" class="chart"></div>
        
        <h2>5. Derivative Analysis (dQ/da)</h2>
        <div id="derivativeChart" class="chart"></div>
        
        <script>
"""
    
    # Add JavaScript data
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57']
    
    # Flow curves
    html_content += "\n            // Flow curves data\n"
    html_content += "            var flowTraces = [];\n"
    
    for i, (name, data) in enumerate(results.items()):
        html_content += f"""
            flowTraces.push({{
                x: {json.dumps(data['openings'])},
                y: {json.dumps(data['flows'])},
                name: '{name}',
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ 
                    color: '{colors[i]}', 
                    width: 3,
                    shape: 'spline'
                }},
                marker: {{ size: 6 }}
            }});
"""
    
    html_content += """
            var flowLayout = {
                title: 'Gate Flow Curves Under Different Conditions',
                xaxis: { 
                    title: 'Gate Opening (%)',
                    gridcolor: '#eee'
                },
                yaxis: { 
                    title: 'Flow Rate (m³/s)',
                    gridcolor: '#eee'
                },
                hovermode: 'x unified',
                plot_bgcolor: '#fafafa',
                annotations: [{
                    x: 50,
                    y: 4.93,
                    text: 'Your case: Nearly linear due to 99% submergence',
                    showarrow: true,
                    arrowhead: 2,
                    ax: -50,
                    ay: -30
                }]
            };
            
            Plotly.newPlot('flowChart', flowTraces, flowLayout);
            
            // Velocity profiles
            var velocityTraces = [];
"""
    
    for i, (name, data) in enumerate(results.items()):
        html_content += f"""
            velocityTraces.push({{
                x: {json.dumps(data['openings'])},
                y: {json.dumps(data['velocities'])},
                name: '{name}',
                type: 'scatter',
                mode: 'lines',
                line: {{ color: '{colors[i]}', width: 2 }}
            }});
"""
    
    html_content += """
            var velocityLayout = {
                title: 'Velocity Through Gate',
                xaxis: { title: 'Gate Opening (%)' },
                yaxis: { title: 'Velocity (m/s)' },
                hovermode: 'x unified'
            };
            
            Plotly.newPlot('velocityChart', velocityTraces, velocityLayout);
            
            // Derivative chart
            var derivativeTraces = [];
"""
    
    # Calculate derivatives
    for i, (name, data) in enumerate(results.items()):
        openings = data['openings']
        flows = data['flows']
        derivatives = []
        
        for j in range(1, len(flows)):
            dQ = flows[j] - flows[j-1]
            da = (openings[j] - openings[j-1]) / 100.0 * gate.max_opening_m
            dQ_da = dQ / da if da > 0 else 0
            derivatives.append(dQ_da)
        
        html_content += f"""
            derivativeTraces.push({{
                x: {json.dumps(openings[1:])},
                y: {json.dumps(derivatives)},
                name: '{name}',
                type: 'scatter',
                mode: 'lines',
                line: {{ color: '{colors[i]}', width: 2 }}
            }});
"""
    
    html_content += """
            var derivativeLayout = {
                title: 'Rate of Flow Change (dQ/da) - Linearity Indicator',
                xaxis: { title: 'Gate Opening (%)' },
                yaxis: { title: 'dQ/da (m²/s)' },
                hovermode: 'x unified',
                annotations: [{
                    x: 50,
                    y: 8,
                    text: 'Constant dQ/da = Linear curve',
                    showarrow: false,
                    font: { size: 14, color: 'red' }
                }]
            };
            
            Plotly.newPlot('derivativeChart', derivativeTraces, derivativeLayout);
        </script>
        
        <div class="explanation" style="margin-top: 30px;">
            <h3>Key Insights from Analysis</h3>
            <ol>
                <li><strong>Your Case (Red Line):</strong> Nearly linear because submergence ratio is 99.1%, making the reduction factor nearly constant.</li>
                <li><strong>Free Flow (Green Line):</strong> Shows typical square root relationship - more curved.</li>
                <li><strong>Variable Head (Yellow):</strong> Most realistic - head decreases as flow increases, creating additional curvature.</li>
                <li><strong>Constant dQ/da:</strong> In the derivative chart, a horizontal line indicates linear Q vs a relationship.</li>
            </ol>
        </div>
        
        <div class="equation">
            <h3>Why High Submergence Creates Linear Curves</h3>
            <p>When h₂/h₁ → 1 (high submergence):</p>
            <p>$$RF = \\sqrt{1 - (h_2/h_1)^2} \\approx \\text{constant}$$</p>
            <p>Therefore: $$Q = \\underbrace{C_d \\times b \\times \\sqrt{2gh} \\times RF}_{\\text{constant}} \\times a$$</p>
            <p>Result: <strong>Q ∝ a</strong> (Linear relationship)</p>
        </div>
    </div>
</body>
</html>
"""
    
    # Save HTML file
    with open('gate_curves_detailed_analysis.html', 'w') as f:
        f.write(html_content)
    
    print("\n\nDetailed analysis saved to gate_curves_detailed_analysis.html")
    
    # Save numerical results
    with open('gate_curves_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("Numerical results saved to gate_curves_analysis.json")

if __name__ == "__main__":
    create_detailed_gate_curves()