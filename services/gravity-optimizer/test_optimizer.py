#!/usr/bin/env python3
"""Test script for gravity optimizer service"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.optimization import ZoneDeliveryRequest, OptimizationObjective
from utils.mock_network import create_mock_network
from services.gravity_optimizer import GravityOptimizer


async def test_gravity_optimizer():
    """Test the gravity optimizer with sample data"""
    print("Creating mock network topology...")
    network = create_mock_network()
    print(f"Network has {len(network.nodes)} nodes, {len(network.channels)} channels, {len(network.gates)} gates")
    
    print("\nInitializing gravity optimizer...")
    optimizer = GravityOptimizer(network)
    
    print("\nCreating zone delivery requests...")
    zone_requests = [
        ZoneDeliveryRequest(
            zone_id="zone_1",
            required_volume=50000,  # 50,000 m³
            required_flow_rate=15.0,  # 15 m³/s
            priority=1
        ),
        ZoneDeliveryRequest(
            zone_id="zone_2",
            required_volume=40000,
            required_flow_rate=12.0,
            priority=1
        ),
        ZoneDeliveryRequest(
            zone_id="zone_3",
            required_volume=30000,
            required_flow_rate=10.0,
            priority=2
        ),
        ZoneDeliveryRequest(
            zone_id="zone_4",
            required_volume=35000,
            required_flow_rate=11.0,
            priority=2
        ),
        ZoneDeliveryRequest(
            zone_id="zone_5",
            required_volume=25000,
            required_flow_rate=8.0,
            priority=3
        ),
        ZoneDeliveryRequest(
            zone_id="zone_6",
            required_volume=20000,
            required_flow_rate=6.0,
            priority=3
        )
    ]
    
    print(f"\nTotal requested flow: {sum(r.required_flow_rate for r in zone_requests):.1f} m³/s")
    
    print("\nRunning optimization...")
    try:
        result = await optimizer.optimize_delivery(
            zone_requests=zone_requests,
            source_water_level=222.0,  # 1m above ground
            objective=OptimizationObjective.BALANCED,
            include_contingency=True,
            include_energy_recovery=True
        )
        
        print("\n=== OPTIMIZATION RESULTS ===")
        print(f"Request ID: {result.request_id}")
        print(f"Overall Efficiency: {result.overall_efficiency:.1%}")
        print(f"Total Delivery Time: {result.total_delivery_time:.1f} hours")
        
        print("\n--- Feasibility Results ---")
        for feas in result.feasibility_results:
            status = "✓" if feas.is_feasible else "✗"
            print(f"{status} {feas.zone_id}: Min source level needed: {feas.min_required_source_level:.1f}m, "
                  f"Head loss: {feas.total_head_loss:.2f}m")
            if feas.warnings:
                for warning in feas.warnings:
                    print(f"   ⚠ {warning}")
        
        print("\n--- Flow Distribution ---")
        for zone_id, flow in result.flow_splits.zone_allocations.items():
            requested = next(r.required_flow_rate for r in zone_requests if r.zone_id == zone_id)
            satisfaction = flow / requested * 100 if requested > 0 else 0
            print(f"{zone_id}: {flow:.1f} m³/s ({satisfaction:.0f}% of requested)")
        
        print("\n--- Delivery Sequence ---")
        for seq in result.delivery_sequence:
            print(f"{seq.order}. {seq.zone_id}: "
                  f"Travel time: {seq.expected_travel_time:.0f} min, "
                  f"Head loss: {seq.total_head_loss:.1f}m")
        
        if result.energy_recovery:
            print("\n--- Energy Recovery Potential ---")
            total_power = sum(site.potential_power for site in result.energy_recovery)
            print(f"Total potential: {total_power:.0f} kW from {len(result.energy_recovery)} sites")
            for site in result.energy_recovery[:3]:  # Top 3 sites
                print(f"  {site.location_id}: {site.potential_power:.0f} kW "
                      f"({site.installation_feasibility})")
        
        if result.warnings:
            print("\n--- Warnings ---")
            for warning in result.warnings:
                print(f"⚠ {warning}")
        
        print("\n=== OPTIMIZATION COMPLETE ===")
        
    except Exception as e:
        print(f"\nError during optimization: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Gravity Flow Optimizer Test")
    print("===========================")
    asyncio.run(test_gravity_optimizer())