"""
Test script for Gravity Flow Optimizer service
"""

import httpx
import asyncio
import json
from datetime import datetime

BASE_URL = "http://localhost:3025"

async def test_health():
    """Test health endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        print()

async def test_optimization():
    """Test gravity flow optimization"""
    request_data = {
        "target_deliveries": [
            {
                "section_id": "Zone_2_Section_A",
                "zone": 2,
                "required_flow_m3s": 2.5,
                "required_volume_m3": 50000,
                "target_elevation_m": 217.5,
                "priority": "high",
                "delivery_window_hours": 12,
                "crop_type": "rice",
                "growth_stage": "flowering"
            },
            {
                "section_id": "Zone_5_Section_B",
                "zone": 5,
                "required_flow_m3s": 1.8,
                "required_volume_m3": 30000,
                "target_elevation_m": 215.5,
                "priority": "medium",
                "delivery_window_hours": 24,
                "crop_type": "sugarcane",
                "growth_stage": "tillering"
            }
        ],
        "current_gate_states": {
            "Source->M(0,0)": {
                "gate_id": "Source->M(0,0)",
                "type": "automated",
                "current_opening_m": 1.5,
                "max_opening_m": 3.0,
                "width_m": 4.0,
                "sill_elevation_m": 220.5,
                "calibration_k1": 0.61
            },
            "M(0,0)->M(0,2)": {
                "gate_id": "M(0,0)->M(0,2)",
                "type": "manual",
                "current_opening_m": 1.0,
                "max_opening_m": 2.5,
                "width_m": 3.5,
                "sill_elevation_m": 220.0,
                "calibration_k1": 0.60
            },
            "M(0,0)->M(0,5)": {
                "gate_id": "M(0,0)->M(0,5)",
                "type": "manual",
                "current_opening_m": 0.8,
                "max_opening_m": 2.0,
                "width_m": 3.0,
                "sill_elevation_m": 220.0,
                "calibration_k1": 0.59
            }
        },
        "network_topology": {},
        "source_elevation": 221.0
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/gravity/optimize-flow",
            json=request_data
        )
        print(f"Optimization Request: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("\nOptimal Gate Settings:")
            for gate_id, settings in result.get("optimal_gate_settings", {}).items():
                print(f"  {gate_id}:")
                print(f"    Opening: {settings['optimal_opening_m']:.2f} m")
                print(f"    Flow: {settings['flow_m3s']:.2f} m³/s")
                print(f"    Head Loss: {settings['head_loss_m']:.3f} m")
            
            print(f"\nTotal Head Loss: {result.get('total_head_loss', 0):.3f} m")
            print("\nDelivery Times:")
            for section, time in result.get("delivery_times", {}).items():
                print(f"  {section}: {time:.1f} hours")
        else:
            print(f"Error: {response.text}")
        print()

async def test_energy_profile():
    """Test energy profile calculation"""
    path = "Source->M(0,0)->M(0,2)->Zone_2"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/gravity/energy-profile/{path}")
        print(f"Energy Profile for {path}: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Total Head Loss: {result['total_head_loss']:.3f} m")
            print(f"Minimum Pressure Head: {result['minimum_pressure_head']:.3f} m")
            print(f"Critical Points: {result.get('critical_points', [])}")
        else:
            print(f"Error: {response.text}")
        print()

async def test_feasibility():
    """Test feasibility check"""
    request_data = {
        "source_node": "Source",
        "target_section": "Zone_5",
        "target_elevation": 215.5,
        "required_flow_m3s": 2.0,
        "path_nodes": ["Source", "M(0,0)", "M(0,5)", "Zone_5"],
        "check_depth_requirements": True
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/gravity/verify-feasibility",
            json=request_data
        )
        print(f"Feasibility Check: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Feasible: {result['feasible']}")
            print(f"Required Upstream Level: {result['required_upstream_level']:.2f} m")
            print(f"Available Head: {result['available_head']:.2f} m")
            print(f"Total Losses: {result['total_losses']:.3f} m")
            if result.get('recommendations'):
                print("Recommendations:")
                for rec in result['recommendations']:
                    print(f"  - {rec}")
        else:
            print(f"Error: {response.text}")
        print()

async def test_friction_losses():
    """Test friction loss calculation"""
    canal_id = "M(0,0)->M(0,2)"
    flow = 3.5
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/gravity/friction-losses/{canal_id}",
            params={"flow_m3s": flow}
        )
        print(f"Friction Losses for {canal_id}: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Flow: {result['flow_m3s']:.2f} m³/s")
            print(f"Friction Loss: {result['friction_loss_m']:.4f} m")
            print(f"Velocity: {result['velocity_ms']:.2f} m/s")
            print(f"Flow Regime: {result['flow_regime']}")
            print(f"Manning's n: {result['manning_n']}")
        else:
            print(f"Error: {response.text}")
        print()

async def main():
    """Run all tests"""
    print("Testing Gravity Flow Optimizer Service")
    print("=" * 50)
    
    await test_health()
    await test_optimization()
    await test_energy_profile()
    await test_feasibility()
    await test_friction_losses()

if __name__ == "__main__":
    asyncio.run(main())