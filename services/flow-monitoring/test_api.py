#!/usr/bin/env python3
"""
Test script for Flow Monitoring API endpoints
Tests against both mock server (3099) and actual service (3011)
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, Any

# Configuration
MOCK_SERVER_URL = "http://localhost:3099"
SERVICE_URL = "http://localhost:3011"


async def test_gates_state(base_url: str):
    """Test GET /api/v1/gates/state endpoint"""
    print(f"\n=== Testing GET /api/v1/gates/state on {base_url} ===")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/api/v1/gates/state")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Gates found: {len(data.get('gates', {}))}")
                
                # Print first gate details
                for gate_id, state in list(data.get('gates', {}).items())[:1]:
                    print(f"\nGate: {gate_id}")
                    print(f"  Type: {state.get('type')}")
                    print(f"  Opening: {state.get('opening_m')} m")
                    print(f"  Flow: {state.get('flow_m3s')} m³/s")
                    print(f"  Mode: {state.get('mode')}")
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Connection error: {e}")


async def test_verify_schedule(base_url: str):
    """Test POST /api/v1/hydraulics/verify-schedule endpoint"""
    print(f"\n=== Testing POST /api/v1/hydraulics/verify-schedule on {base_url} ===")
    
    # Test schedule
    schedule = {
        "deliveries": [
            {
                "node_id": "Zone_2",
                "flow_rate": 5.0,
                "duration_hours": 4
            },
            {
                "node_id": "Zone_5",
                "flow_rate": 3.5,
                "duration_hours": 4
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/api/v1/hydraulics/verify-schedule",
                json=schedule
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('data', {})
                print(f"Feasible: {result.get('is_feasible')}")
                print(f"Total demand: {result.get('total_demand')} m³/s")
                print(f"System utilization: {result.get('system_utilization', 0)*100:.1f}%")
                
                if not result.get('is_feasible'):
                    print(f"Reason: {result.get('reason')}")
                    print(f"Violations: {len(result.get('violations', []))}")
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Connection error: {e}")


async def test_manual_gate_update(base_url: str):
    """Test PUT /api/v1/gates/manual/{gate_id}/state endpoint"""
    print(f"\n=== Testing PUT /api/v1/gates/manual/{{gate_id}}/state on {base_url} ===")
    
    gate_id = "M(0,0)->M(0,2)"
    update_data = {
        "opening_percentage": 75.0,
        "operator_id": "OP-123",
        "notes": "Adjusting for increased demand in Zone 2"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(
                f"{base_url}/api/v1/gates/manual/{gate_id}/state",
                json=update_data
            )
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Success: {data.get('status')}")
                print(f"Message: {data.get('message')}")
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Connection error: {e}")


async def test_health(base_url: str):
    """Test health endpoint"""
    print(f"\n=== Testing /health on {base_url} ===")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Service status: {data.get('status')}")
                print(f"Service: {data.get('service')}")
                print(f"Version: {data.get('version')}")
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Connection error: {e}")


async def main():
    """Run all tests"""
    print("Flow Monitoring API Test Suite")
    print("=" * 50)
    
    # Test mock server first
    print("\n### Testing Mock Server (port 3099) ###")
    await test_health(MOCK_SERVER_URL)
    await test_gates_state(MOCK_SERVER_URL)
    await test_verify_schedule(MOCK_SERVER_URL)
    await test_manual_gate_update(MOCK_SERVER_URL)
    
    # Test actual service
    print("\n\n### Testing Actual Service (port 3011) ###")
    await test_health(SERVICE_URL)
    await test_gates_state(SERVICE_URL)
    await test_verify_schedule(SERVICE_URL)
    await test_manual_gate_update(SERVICE_URL)
    
    print("\n\nTest suite completed!")


if __name__ == "__main__":
    asyncio.run(main())