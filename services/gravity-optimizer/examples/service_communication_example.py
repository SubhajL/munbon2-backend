#!/usr/bin/env python3
"""
Example demonstrating inter-service communication for Gravity Optimizer

This example shows how the Gravity Optimizer communicates with other microservices:
- GIS Service: Get spatial data and network topology
- ROS Service: Get water allocations and report delivery results
- SCADA Service: Control gates and get real-time status
- Weather Service: Check irrigation conditions
- Sensor Data Service: Get real-time measurements
"""

import asyncio
import sys
from datetime import datetime, date
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from clients import (
    GISClient, ROSClient, SCADAClient,
    WeatherClient, SensorDataClient, ServiceRegistry
)
from models.optimization import ZoneDeliveryRequest, OptimizationObjective
from services.integrated_optimizer import IntegratedGravityOptimizer


async def demonstrate_service_communication():
    """Demonstrate how services communicate"""
    
    print("=== Gravity Optimizer Service Communication Demo ===\n")
    
    # Initialize service registry
    registry = ServiceRegistry()
    await registry.connect()
    
    print("1. Service Discovery")
    print("-" * 50)
    
    # Discover available services
    services = await registry.discover_all()
    print(f"Found {len(services)} services:")
    for service in services:
        print(f"  - {service.name}: {service.url} (v{service.version})")
    print()
    
    # Initialize clients
    gis_client = GISClient()
    ros_client = ROSClient()
    scada_client = SCADAClient()
    weather_client = WeatherClient()
    sensor_client = SensorDataClient()
    
    # Connect all clients
    await asyncio.gather(
        gis_client.connect(),
        ros_client.connect(),
        scada_client.connect(),
        weather_client.connect(),
        sensor_client.connect()
    )
    
    print("2. GIS Service Communication")
    print("-" * 50)
    
    # Get zone boundaries
    try:
        zones = await gis_client.get_zone_boundaries()
        print(f"Retrieved {len(zones)} zone boundaries:")
        for zone_id, zone in list(zones.items())[:3]:
            print(f"  - {zone.name}: {zone.area_hectares:.1f} hectares, "
                  f"elevation {zone.elevation_range[0]:.1f}-{zone.elevation_range[1]:.1f}m")
    except Exception as e:
        print(f"  GIS Service not available: {e}")
    print()
    
    print("3. ROS Service Communication")
    print("-" * 50)
    
    # Get current water allocations
    try:
        allocations = await ros_client.get_current_allocations()
        print(f"Retrieved {len(allocations)} water allocations:")
        for alloc in allocations[:3]:
            print(f"  - Zone {alloc.zone_id}: {alloc.allocated_volume:.0f}m³ "
                  f"at {alloc.required_flow_rate:.1f}m³/s (priority {alloc.priority})")
    except Exception as e:
        print(f"  ROS Service not available: {e}")
    
    # Get irrigation schedules
    try:
        schedules = await ros_client.get_irrigation_schedule(date=date.today())
        print(f"\nToday's irrigation schedules: {len(schedules)}")
        for sched in schedules[:2]:
            print(f"  - {sched.zone_id}: {sched.start_time.strftime('%H:%M')} "
                  f"for {sched.duration_hours:.1f} hours")
    except Exception as e:
        print(f"  Failed to get schedules: {e}")
    print()
    
    print("4. SCADA Service Communication")
    print("-" * 50)
    
    # Get gate status
    try:
        gates = await scada_client.get_all_gates_status()
        print(f"Retrieved status for {len(gates)} gates:")
        for gate in gates[:3]:
            print(f"  - Gate {gate.gate_id}: {gate.current_opening*100:.0f}% open, "
                  f"status: {gate.status}")
    except Exception as e:
        print(f"  SCADA Service not available: {e}")
    
    # Demonstrate gate control (dry run)
    print("\nGate control capability:")
    print("  - Can control 20 automated gates")
    print("  - Supports batch operations")
    print("  - Real-time position verification")
    print()
    
    print("5. Weather Service Communication")
    print("-" * 50)
    
    # Get current weather
    try:
        weather = await weather_client.get_current_weather()
        print(f"Current weather conditions:")
        print(f"  - Temperature: {weather.temperature:.1f}°C")
        print(f"  - Humidity: {weather.humidity:.0f}%")
        print(f"  - Rainfall: {weather.rainfall:.1f}mm")
        print(f"  - ET: {weather.evapotranspiration:.1f}mm/day")
    except Exception as e:
        print(f"  Weather Service not available: {e}")
    
    # Check irrigation conditions
    try:
        conditions = await weather_client.check_irrigation_conditions()
        print(f"\nIrrigation conditions: {'Suitable' if conditions.get('suitable') else 'Not suitable'}")
        if not conditions.get('suitable'):
            print(f"  Reason: {conditions.get('reason')}")
    except Exception as e:
        print(f"  Failed to check conditions: {e}")
    print()
    
    print("6. Sensor Data Service Communication")
    print("-" * 50)
    
    # Get water levels
    try:
        water_levels = await sensor_client.get_water_levels()
        print(f"Retrieved {len(water_levels)} water level readings:")
        for reading in water_levels[:3]:
            print(f"  - {reading.sensor_id} at channel {reading.channel_id}: "
                  f"{reading.water_level:.2f}m")
    except Exception as e:
        print(f"  Sensor Service not available: {e}")
    
    # Get flow rates
    try:
        flow_rates = await sensor_client.get_flow_rates()
        print(f"\nRetrieved {len(flow_rates)} flow meter readings:")
        for reading in flow_rates[:3]:
            print(f"  - {reading.sensor_id}: {reading.flow_rate:.2f}m³/s")
    except Exception as e:
        print(f"  Failed to get flow rates: {e}")
    print()
    
    print("7. Integrated Optimization Example")
    print("-" * 50)
    
    # Create optimization request
    zone_requests = [
        ZoneDeliveryRequest(
            zone_id="zone_1",
            required_volume=20000,
            required_flow_rate=15.0,
            priority=1
        ),
        ZoneDeliveryRequest(
            zone_id="zone_2", 
            required_volume=15000,
            required_flow_rate=12.0,
            priority=1
        ),
        ZoneDeliveryRequest(
            zone_id="zone_3",
            required_volume=10000,
            required_flow_rate=8.0,
            priority=2
        )
    ]
    
    print("Optimization request:")
    for req in zone_requests:
        print(f"  - {req.zone_id}: {req.required_volume}m³ at {req.required_flow_rate}m³/s")
    
    print("\nIntegrated optimization would:")
    print("  1. Fetch real-time allocations from ROS")
    print("  2. Check weather conditions")
    print("  3. Get current sensor readings")
    print("  4. Retrieve gate positions from SCADA")
    print("  5. Load network topology from GIS")
    print("  6. Run hydraulic optimization")
    print("  7. Execute gate controls via SCADA")
    print("  8. Report results back to ROS")
    print("  9. Monitor delivery progress")
    print()
    
    print("8. Service Communication Benefits")
    print("-" * 50)
    print("✓ Real-time data integration")
    print("✓ Coordinated control actions")
    print("✓ Automatic failover with circuit breakers")
    print("✓ Centralized monitoring and alerting")
    print("✓ Consistent water delivery tracking")
    print()
    
    # Cleanup
    await asyncio.gather(
        gis_client.disconnect(),
        ros_client.disconnect(),
        scada_client.disconnect(),
        weather_client.disconnect(),
        sensor_client.disconnect()
    )
    
    await registry.disconnect()
    
    print("Demo completed!")


if __name__ == "__main__":
    asyncio.run(demonstrate_service_communication())