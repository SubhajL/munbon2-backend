#!/usr/bin/env python3
"""
Test script to verify mock server integration with BFF Water Planning service
"""

import asyncio
import httpx
import sys
from datetime import datetime, timedelta

# Test configuration
MOCK_SERVER_URL = "http://localhost:3099"
BFF_URL = "http://localhost:3022"


async def test_mock_server_health():
    """Test if mock server is running"""
    print("\n1. Testing Mock Server Health...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MOCK_SERVER_URL}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Mock server is healthy: {data['service']}")
                print(f"  Available services: {', '.join(data['services'].keys())}")
                return True
            else:
                print(f"✗ Mock server returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Failed to connect to mock server: {e}")
        return False


async def test_mock_endpoints():
    """Test individual mock service endpoints"""
    print("\n2. Testing Individual Mock Service Endpoints...")
    
    endpoints = [
        ("ROS", f"{MOCK_SERVER_URL}/ros/api/v1/water-demand/calculate", "POST", {
            "crop_type": "rice",
            "week": 10,
            "area_rai": 100,
            "effective_rainfall": 50
        }),
        ("GIS", f"{MOCK_SERVER_URL}/gis/api/v1/plots/parcel-A001", "GET", None),
        ("AWD", f"{MOCK_SERVER_URL}/awd/api/v1/awd/plots/P001/status", "GET", None),
        ("Sensor Data", f"{MOCK_SERVER_URL}/sensor/api/v1/water-levels/S1?date=2024-03-15", "GET", None),
        ("Flow Monitoring", f"{MOCK_SERVER_URL}/flow/api/v1/flow/current?section_id=S1", "GET", None),
        ("Scheduler", f"{MOCK_SERVER_URL}/scheduler/api/v1/schedules?section_id=S1", "GET", None),
        ("Weather", f"{MOCK_SERVER_URL}/weather/api/v1/weather/current?location=munbon", "GET", None)
    ]
    
    async with httpx.AsyncClient() as client:
        for service, url, method, json_data in endpoints:
            try:
                if method == "GET":
                    response = await client.get(url)
                else:
                    response = await client.post(url, json=json_data)
                
                if response.status_code == 200:
                    print(f"  ✓ {service}: {response.status_code} OK")
                else:
                    print(f"  ✗ {service}: {response.status_code}")
            except Exception as e:
                print(f"  ✗ {service}: Failed - {e}")


async def test_bff_graphql():
    """Test BFF GraphQL endpoint"""
    print("\n3. Testing BFF GraphQL Endpoint...")
    
    # Test query for water demand
    query = """
    query TestWaterDemand {
        getDailyWaterDemand(
            sectionId: "S1"
            date: "2024-03-15"
        ) {
            sectionId
            date
            totalDemandM3
            plotDemands {
                plotId
                demandM3
                priorityScore
            }
        }
    }
    """
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BFF_URL}/graphql",
                json={"query": query},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    print(f"  ✗ GraphQL returned errors: {data['errors']}")
                else:
                    print("  ✓ GraphQL query successful")
                    if "data" in data and data["data"]:
                        print(f"    Response: {data['data']}")
            else:
                print(f"  ✗ GraphQL returned status {response.status_code}")
                print(f"    Response: {response.text}")
    except Exception as e:
        print(f"  ✗ Failed to connect to BFF service: {e}")
        print("    Make sure the BFF service is running on port 3022")


async def test_service_integration():
    """Test service integration through BFF"""
    print("\n4. Testing Service Integration through BFF...")
    
    # Test mutation that uses multiple services
    mutation = """
    mutation TestIntegration {
        updateAWDStatus(
            plotId: "P001"
            status: true
        ) {
            success
            message
            updatedPlot {
                plotId
                awdStatus
                lastUpdated
            }
        }
    }
    """
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BFF_URL}/graphql",
                json={"query": mutation},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    print(f"  ✗ Integration test returned errors: {data['errors']}")
                else:
                    print("  ✓ Integration test successful")
                    if "data" in data and data["data"]:
                        print(f"    Response: {data['data']}")
            else:
                print(f"  ✗ Integration test returned status {response.status_code}")
    except Exception as e:
        print(f"  ✗ Integration test failed: {e}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Mock Server Integration Test Suite")
    print("=" * 60)
    
    # Check if mock server is running
    mock_server_healthy = await test_mock_server_health()
    if not mock_server_healthy:
        print("\n⚠️  Mock server is not running!")
        print("Please start the mock server first:")
        print("  cd services/mock-server")
        print("  python src/main.py")
        return
    
    # Test mock endpoints
    await test_mock_endpoints()
    
    # Test BFF GraphQL
    await test_bff_graphql()
    
    # Test service integration
    await test_service_integration()
    
    print("\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())