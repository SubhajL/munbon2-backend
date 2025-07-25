#!/usr/bin/env python3
"""
Integration script for Flow Monitoring Service with Water Gate Controller
Demonstrates how the services work together
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List
import numpy as np

# Import our modules
from water_gate_controller_integrated import WaterGateControllerIntegrated

class FlowMonitoringIntegration:
    """Integrates flow monitoring with gate control and predictive analytics"""
    
    def __init__(self, network_file: str, geometry_file: str = None):
        # Initialize water gate controller
        self.controller = WaterGateControllerIntegrated(network_file, geometry_file)
        
        # Simulated sensor readings storage
        self.sensor_readings = {}
        self.flow_predictions = {}
        
    async def ingest_sensor_data(self, sensor_id: str, gate_id: str, 
                                measurement_type: str, value: float):
        """Simulate sensor data ingestion"""
        
        if gate_id not in self.sensor_readings:
            self.sensor_readings[gate_id] = {}
        
        self.sensor_readings[gate_id][measurement_type] = {
            'value': value,
            'sensor_id': sensor_id,
            'timestamp': datetime.now(),
            'quality': 'good'
        }
        
        # Update gate controller with sensor data
        if measurement_type == 'upstream_level':
            self.controller.gate_states[gate_id]['upstream_level'] = value
        elif measurement_type == 'downstream_level':
            self.controller.gate_states[gate_id]['downstream_level'] = value
        elif measurement_type == 'flow_rate':
            self.controller.gate_states[gate_id]['flow_rate'] = value
            self.controller.current_flows[gate_id] = value
    
    def calculate_flow_from_level(self, gate_id: str) -> float:
        """Calculate flow rate from water levels using hydraulic equations"""
        
        gate_state = self.controller.gate_states[gate_id]
        gate_info = self.controller.gates[gate_id]
        
        upstream_level = gate_state.get('upstream_level', 0)
        downstream_level = gate_state.get('downstream_level', 0)
        opening = gate_state.get('opening', 0)
        
        # Head difference
        head = upstream_level - downstream_level
        
        if head <= 0 or opening <= 0:
            return 0
        
        # Simplified gate equation: Q = Cd * A * sqrt(2 * g * h)
        # Cd = discharge coefficient (0.6 typical)
        # A = gate opening area
        # g = gravity (9.81 m/s²)
        # h = head difference
        
        Cd = 0.6
        g = 9.81
        
        # Get gate dimensions from q_max (assume proportional)
        q_max = gate_info.get('q_max', 0)
        if q_max and not np.isnan(q_max):
            # Estimate gate area from max flow
            max_area = q_max / (Cd * np.sqrt(2 * g * 3.0))  # Assume 3m design head
            actual_area = max_area * opening
            
            flow_rate = Cd * actual_area * np.sqrt(2 * g * head)
            return min(flow_rate, q_max)  # Cap at max capacity
        
        return 0
    
    async def predict_downstream_impacts(self, gate_id: str, 
                                       new_opening: float, 
                                       duration_hours: float) -> Dict:
        """Predict downstream impacts of gate operation"""
        
        # Simulate the operation
        result = self.controller.simulate_gate_operation(
            gate_id, new_opening, duration_hours
        )
        
        # Enhanced predictions with zone impacts
        zone_impacts = {}
        affected_gates = []
        
        for event in result['timeline']:
            gate = event['gate']
            gate_info = self.controller.gates.get(gate, {})
            zone = gate_info.get('zone', 0)
            
            if zone not in zone_impacts:
                zone_impacts[zone] = {
                    'gates_affected': [],
                    'total_additional_flow': 0,
                    'first_impact_time': None,
                    'area_served': 0
                }
            
            zone_impacts[zone]['gates_affected'].append(gate)
            zone_impacts[zone]['total_additional_flow'] += event['expected_flow']
            
            if zone_impacts[zone]['first_impact_time'] is None:
                zone_impacts[zone]['first_impact_time'] = event['delay_minutes']
            
            area = gate_info.get('area', 0)
            if area and not np.isnan(area):
                zone_impacts[zone]['area_served'] += area
            
            affected_gates.append({
                'gate': gate,
                'zone': zone,
                'delay_minutes': event['delay_minutes'],
                'canal': gate_info.get('canal', ''),
                'current_flow': self.controller.current_flows.get(gate, 0),
                'expected_flow': event['expected_flow']
            })
        
        # Calculate water distribution efficiency
        total_volume = result['total_volume']
        
        predictions = {
            'operation': {
                'gate': gate_id,
                'new_opening': new_opening,
                'duration_hours': duration_hours,
                'flow_rate': result['flow_rate'],
                'total_volume_m3': total_volume
            },
            'zone_impacts': zone_impacts,
            'affected_gates': affected_gates,
            'warnings': []
        }
        
        # Generate warnings
        for zone, impact in zone_impacts.items():
            if impact['total_additional_flow'] > 5.0:  # High flow threshold
                predictions['warnings'].append({
                    'type': 'high_flow',
                    'zone': zone,
                    'message': f"Zone {zone} will receive {impact['total_additional_flow']:.1f} m³/s additional flow"
                })
        
        return predictions
    
    async def optimize_water_distribution(self, demands: Dict[int, float]) -> List[Dict]:
        """Optimize water distribution to meet zone demands"""
        
        recommendations = self.controller.optimize_gate_operations(demands)
        
        # Enhanced recommendations with travel time considerations
        enhanced_recs = []
        
        for rec in recommendations:
            gate_id = rec['gate']
            
            # Find upstream path to source
            path = self.controller.find_path('S', gate_id)
            
            if path:
                # Calculate when water will arrive
                travel_time = self.controller.calculate_cumulative_travel_time(
                    path, rec['expected_flow']
                )
                
                enhanced_recs.append({
                    **rec,
                    'path_from_source': ' -> '.join(path),
                    'travel_time_minutes': travel_time / 60,
                    'recommended_start_time': (
                        datetime.now() - timedelta(seconds=travel_time)
                    ).isoformat()
                })
            else:
                enhanced_recs.append(rec)
        
        return enhanced_recs
    
    def detect_anomalies(self) -> List[Dict]:
        """Detect anomalies in flow patterns"""
        
        anomalies = []
        
        for gate_id, readings in self.sensor_readings.items():
            gate_info = self.controller.gates.get(gate_id, {})
            
            # Check flow vs opening mismatch
            if 'flow_rate' in readings and 'opening' in self.controller.gate_states[gate_id]:
                measured_flow = readings['flow_rate']['value']
                opening = self.controller.gate_states[gate_id]['opening']
                expected_flow = self.calculate_flow_from_level(gate_id)
                
                if opening > 0 and measured_flow < expected_flow * 0.5:
                    anomalies.append({
                        'gate': gate_id,
                        'type': 'flow_restriction',
                        'severity': 'high',
                        'message': f"Flow ({measured_flow:.2f} m³/s) is much lower than expected ({expected_flow:.2f} m³/s)",
                        'possible_causes': ['Gate blockage', 'Sensor error', 'Upstream restriction']
                    })
            
            # Check water balance
            downstream_gates = self.controller.get_downstream_gates(gate_id)
            if downstream_gates:
                inflow = self.controller.current_flows.get(gate_id, 0)
                outflow_sum = sum(self.controller.current_flows.get(g, 0) 
                                 for g in downstream_gates)
                
                loss_percent = ((inflow - outflow_sum) / inflow * 100) if inflow > 0 else 0
                
                if loss_percent > 15:  # 15% loss threshold
                    anomalies.append({
                        'gate': gate_id,
                        'type': 'excessive_loss',
                        'severity': 'medium',
                        'message': f"Water loss of {loss_percent:.1f}% detected",
                        'inflow': inflow,
                        'outflow': outflow_sum,
                        'possible_causes': ['Seepage', 'Illegal pumping', 'Measurement error']
                    })
        
        return anomalies
    
    async def generate_daily_report(self) -> Dict:
        """Generate daily operational report"""
        
        # Current state
        network_state = self.controller.export_network_state()
        
        # Water balance by zone
        zone_summary = {}
        for gate_id, gate_info in self.controller.gates.items():
            zone = gate_info.get('zone', 0)
            if zone not in zone_summary:
                zone_summary[zone] = {
                    'total_gates': 0,
                    'active_gates': 0,
                    'total_flow': 0,
                    'total_area': 0,
                    'efficiency': 0
                }
            
            zone_summary[zone]['total_gates'] += 1
            
            if self.controller.gate_states[gate_id]['opening'] > 0:
                zone_summary[zone]['active_gates'] += 1
                zone_summary[zone]['total_flow'] += self.controller.current_flows.get(gate_id, 0)
            
            area = gate_info.get('area', 0)
            if area and not np.isnan(area):
                zone_summary[zone]['total_area'] += area
        
        # Anomalies
        anomalies = self.detect_anomalies()
        
        report = {
            'report_date': datetime.now().isoformat(),
            'executive_summary': {
                'total_inflow': network_state['water_balance']['total_inflow'],
                'total_outflow': network_state['water_balance']['total_outflow'],
                'system_efficiency': network_state['water_balance']['efficiency'],
                'active_gates': sum(1 for g in self.controller.gate_states.values() 
                                  if g['opening'] > 0),
                'total_gates': len(self.controller.gates),
                'anomalies_detected': len(anomalies)
            },
            'zone_performance': zone_summary,
            'anomalies': anomalies,
            'recommendations': [],
            'network_state': network_state
        }
        
        # Generate recommendations
        if anomalies:
            report['recommendations'].append({
                'priority': 'high',
                'action': 'Investigate detected anomalies',
                'details': f"{len(anomalies)} anomalies require attention"
            })
        
        for zone, summary in zone_summary.items():
            if summary['active_gates'] == 0 and summary['total_gates'] > 0:
                report['recommendations'].append({
                    'priority': 'medium',
                    'action': f'Review water allocation for Zone {zone}',
                    'details': 'No active gates in this zone'
                })
        
        return report


# Example usage
async def main():
    # Initialize integration
    integration = FlowMonitoringIntegration(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== Munbon Flow Monitoring Integration Demo ===\n")
    
    # Simulate sensor data ingestion
    print("1. Ingesting sensor data...")
    await integration.ingest_sensor_data('WL-001', 'M(0,0)', 'upstream_level', 3.5)
    await integration.ingest_sensor_data('WL-002', 'M(0,0)', 'downstream_level', 3.2)
    await integration.ingest_sensor_data('FL-001', 'M(0,0)', 'flow_rate', 8.5)
    
    # Open some gates
    integration.controller.open_gate('M(0,0)', 0.8, upstream_level=3.5)
    integration.controller.open_gate('M(0,2)', 0.6)
    integration.controller.open_gate('M(0,3)', 0.5)
    
    # Predict downstream impacts
    print("\n2. Predicting downstream impacts...")
    predictions = await integration.predict_downstream_impacts('M(0,0)', 0.9, 6.0)
    
    print(f"   Operation: Open {predictions['operation']['gate']} to {predictions['operation']['new_opening']*100:.0f}%")
    print(f"   Flow rate: {predictions['operation']['flow_rate']:.2f} m³/s")
    print(f"   Total volume: {predictions['operation']['total_volume_m3']:.0f} m³")
    
    print("\n   Zone impacts:")
    for zone, impact in predictions['zone_impacts'].items():
        print(f"   - Zone {zone}: {len(impact['gates_affected'])} gates affected")
        print(f"     First impact in {impact['first_impact_time']:.1f} minutes")
        print(f"     Additional flow: {impact['total_additional_flow']:.2f} m³/s")
    
    # Optimize water distribution
    print("\n3. Optimizing water distribution...")
    demands = {1: 2.5, 2: 3.0, 3: 1.5, 4: 2.0, 5: 1.0, 6: 0.8}
    recommendations = await integration.optimize_water_distribution(demands)
    
    print("   Recommendations:")
    for rec in recommendations[:5]:  # Show first 5
        print(f"   - {rec['gate']}: Open to {rec['recommended_opening']*100:.0f}%")
        print(f"     Expected flow: {rec['expected_flow']:.2f} m³/s")
        print(f"     Travel time from source: {rec.get('travel_time_minutes', 0):.1f} minutes")
    
    # Detect anomalies
    print("\n4. Checking for anomalies...")
    anomalies = integration.detect_anomalies()
    if anomalies:
        print(f"   Found {len(anomalies)} anomalies:")
        for anomaly in anomalies:
            print(f"   - {anomaly['gate']}: {anomaly['type']} ({anomaly['severity']})")
            print(f"     {anomaly['message']}")
    else:
        print("   No anomalies detected")
    
    # Generate report
    print("\n5. Generating daily report...")
    report = await integration.generate_daily_report()
    
    print("\n   Executive Summary:")
    summary = report['executive_summary']
    print(f"   - Total inflow: {summary['total_inflow']:.2f} m³/s")
    print(f"   - Total outflow: {summary['total_outflow']:.2f} m³/s")
    print(f"   - System efficiency: {summary['system_efficiency']:.1f}%")
    print(f"   - Active gates: {summary['active_gates']}/{summary['total_gates']}")
    print(f"   - Anomalies: {summary['anomalies_detected']}")
    
    # Save report
    with open('daily_flow_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print("\n   Report saved to daily_flow_report.json")


if __name__ == "__main__":
    asyncio.run(main())