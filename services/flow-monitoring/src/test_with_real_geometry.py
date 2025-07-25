#!/usr/bin/env python3
"""
Test Water Gate Controller with Real Canal Geometry
Demonstrates accurate travel time calculations
"""

from water_gate_controller_integrated import WaterGateControllerIntegrated
import json

def test_real_geometry():
    """Test with actual canal geometry data"""
    
    # Initialize with real geometry
    controller = WaterGateControllerIntegrated(
        network_file='munbon_network_updated.json',
        geometry_file='/Users/subhajlimanond/dev/munbon2-backend/canal_sections_6zones_final.json'
    )
    
    print("=== MUNBON WATER GATE CONTROLLER WITH REAL GEOMETRY ===")
    print(f"Total Gates: {len(controller.gates)}")
    print(f"Total Canal Sections Loaded: {len(controller.canal_sections)}")
    
    # Show loaded sections
    print("\nLoaded Canal Sections:")
    for i, (key, section) in enumerate(list(controller.canal_sections.items())[:10]):
        print(f"  {key}: {section.length_m}m, n={section.manning_n}, S={section.bed_slope}")
    print(f"  ... and {len(controller.canal_sections)-10} more sections")
    
    # Test 1: Main canal flow propagation
    print("\n=== TEST 1: Main Canal (LMC) Flow Propagation ===")
    print("Opening M(0,0) to 80% capacity...")
    
    result = controller.simulate_gate_operation('M(0,0)', opening=0.8, duration_hours=6)
    
    print(f"\nFlow rate: {result['flow_rate']:.2f} m³/s")
    print(f"Total volume over 6 hours: {result['total_volume']:.0f} m³")
    
    print("\nKey arrival times:")
    key_gates = ['M(0,2)', 'M(0,3)', 'M(0,5)', 'M(0,10)', 'M(0,12)']
    for event in result['timeline']:
        if event['gate'] in key_gates:
            hours = event['delay_minutes'] / 60
            print(f"  {event['gate']}: {event['delay_minutes']:.1f} min ({hours:.2f} hours)")
    
    # Test 2: RMC branch flow
    print("\n=== TEST 2: RMC Branch Flow Propagation ===")
    print("Opening M(0,1) gates for RMC system...")
    
    controller.open_gate('M(0,1)', 0.7)
    result_rmc = controller.simulate_gate_operation('M(0,1)', opening=0.7, duration_hours=4)
    
    print(f"\nRMC Flow rate: {result_rmc['flow_rate']:.2f} m³/s")
    
    rmc_gates = ['M (0,1; 1,0)', 'M (0,1; 1,1)', 'M(0,1; 1,1; 1,0)', 'M(0,1; 1,1; 1,2)']
    print("\nRMC arrival times:")
    for event in result_rmc['timeline']:
        if event['gate'] in rmc_gates:
            print(f"  {event['gate']}: {event['delay_minutes']:.1f} min")
    
    # Test 3: Zone 3 (9R-LMC) branch
    print("\n=== TEST 3: Zone 3 (9R-LMC) Branch Flow ===")
    
    # Find path to 9R-LMC
    path_to_9r = controller.find_path('M(0,0)', 'M (0,3; 1,1)')
    if path_to_9r:
        print(f"Path to 9R-LMC: {' -> '.join(path_to_9r[:5])}...")
        travel_time = controller.calculate_cumulative_travel_time(path_to_9r, flow_rate=5.0)
        print(f"Travel time from source: {travel_time/60:.1f} minutes ({travel_time/3600:.2f} hours)")
    
    # Test 4: Zone-by-zone analysis
    print("\n=== TEST 4: Zone-by-Zone Water Arrival Analysis ===")
    
    # Simulate opening main gate
    arrival_times = controller.propagate_flow_with_delay('M(0,0)', flow_rate=8.0)
    
    # Group by zones
    zone_arrivals = {}
    for gate, time_sec in arrival_times.items():
        gate_info = controller.gates.get(gate, {})
        zone = gate_info.get('zone', 0)
        
        if zone not in zone_arrivals:
            zone_arrivals[zone] = {
                'first_arrival': float('inf'),
                'last_arrival': 0,
                'gates': []
            }
        
        zone_arrivals[zone]['first_arrival'] = min(zone_arrivals[zone]['first_arrival'], time_sec)
        zone_arrivals[zone]['last_arrival'] = max(zone_arrivals[zone]['last_arrival'], time_sec)
        zone_arrivals[zone]['gates'].append((gate, time_sec))
    
    print("\nWater arrival by zone (from M(0,0) at 8.0 m³/s):")
    for zone in sorted(zone_arrivals.keys()):
        if zone > 0:  # Skip zone 0
            data = zone_arrivals[zone]
            first_hr = data['first_arrival'] / 3600
            last_hr = data['last_arrival'] / 3600
            print(f"\nZone {zone}:")
            print(f"  First arrival: {first_hr:.2f} hours")
            print(f"  Last arrival: {last_hr:.2f} hours")
            print(f"  Total gates: {len(data['gates'])}")
    
    # Test 5: Velocity calculations
    print("\n=== TEST 5: Flow Velocity Analysis ===")
    
    test_sections = [
        ('M(0,0)', 'M(0,1)', 8.0),
        ('M(0,2)', 'M(0,3)', 6.0),
        ('M(0,3)', 'M(0,4)', 5.0),
        ('M(0,12)', 'M(0,13)', 3.0)
    ]
    
    print("\nVelocity calculations for key sections:")
    for from_node, to_node, flow in test_sections:
        key = f"{from_node}->{to_node}"
        if key in controller.canal_sections:
            section = controller.canal_sections[key]
            velocity = controller.calculate_velocity(flow, section)
            travel_time = section.length_m / velocity if velocity > 0 else 0
            
            print(f"\n{from_node} -> {to_node}:")
            print(f"  Distance: {section.length_m}m")
            print(f"  Flow: {flow:.2f} m³/s")
            print(f"  Velocity: {velocity:.2f} m/s")
            print(f"  Travel time: {travel_time/60:.1f} minutes")
    
    # Save detailed results
    results = {
        'geometry_loaded': len(controller.canal_sections),
        'main_canal_test': {
            'flow_rate': result['flow_rate'],
            'volume_6hr': result['total_volume'],
            'key_arrivals': {
                gate: event['delay_minutes'] 
                for event in result['timeline'] 
                if event['gate'] in key_gates
            }
        },
        'zone_arrivals': {
            f"zone_{zone}": {
                'first_arrival_hours': data['first_arrival'] / 3600,
                'last_arrival_hours': data['last_arrival'] / 3600,
                'gate_count': len(data['gates'])
            }
            for zone, data in zone_arrivals.items() if zone > 0
        }
    }
    
    with open('real_geometry_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n\nResults saved to real_geometry_test_results.json")
    
    return controller


if __name__ == "__main__":
    controller = test_real_geometry()