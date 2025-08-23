#!/usr/bin/env python3
"""
Test script for ROS/GIS Integration Service
Tests GraphQL API and integration with mock server
"""

import asyncio
import httpx
import json
from datetime import datetime


async def test_graphql_api():
    """Test GraphQL endpoints"""
    base_url = "http://localhost:3022"
    
    print("Testing ROS/GIS Integration Service...")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Test health endpoint
        print("\n1. Testing health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test GraphQL query - Get section details
        print("\n2. Testing GraphQL query - Section details...")
        query = """
        query GetSection {
          section(id: "Zone_2_Section_A") {
            sectionId
            zone
            areaHectares
            cropType
            deliveryGate
          }
        }
        """
        
        response = await client.post(
            f"{base_url}/graphql",
            json={"query": query}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test GraphQL query - Section performance
        print("\n3. Testing GraphQL query - Section performance...")
        query = """
        query GetPerformance {
          sectionPerformance(sectionId: "Zone_2_Section_A", weeks: 4) {
            week
            plannedM3
            deliveredM3
            efficiency
            deficitM3
          }
        }
        """
        
        response = await client.post(
            f"{base_url}/graphql",
            json={"query": query}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test GraphQL mutation - Submit demands
        print("\n4. Testing GraphQL mutation - Submit demands...")
        current_week = datetime.utcnow().strftime("%Y-W%V")
        mutation = """
        mutation SubmitDemands($input: WeeklyDemandInput!) {
          submitDemands(input: $input) {
            scheduleId
            status
            conflicts
            totalSections
            totalVolumeM3
          }
        }
        """
        
        variables = {
            "input": {
                "week": current_week,
                "demands": [
                    {
                        "sectionId": "Zone_2_Section_A",
                        "volumeM3": 15000,
                        "priority": "critical"
                    },
                    {
                        "sectionId": "Zone_2_Section_B",
                        "volumeM3": 12000,
                        "priority": "high"
                    },
                    {
                        "sectionId": "Zone_5_Section_A",
                        "volumeM3": 18000,
                        "priority": "high"
                    }
                ],
                "weatherAdjustment": 0.95,
                "rainfallForecastMm": 5
            }
        }
        
        response = await client.post(
            f"{base_url}/graphql",
            json={"query": mutation, "variables": variables}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test GraphQL query - Delivery points
        print("\n5. Testing GraphQL query - Delivery points...")
        query = """
        query GetDeliveryPoints {
          deliveryPoints {
            gateId
            locationLat
            locationLon
            sectionsServed
            maxFlowM3s
            currentFlowM3s
          }
        }
        """
        
        response = await client.post(
            f"{base_url}/graphql",
            json={"query": query}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test GraphQL query - Gate mappings
        print("\n6. Testing GraphQL query - Gate mappings...")
        query = """
        query GetGateMappings {
          gateMappings {
            gateId
            gateType
            sectionsCount
            totalAreaHectares
            utilizationPercent
            isOverloaded
            hasCapacity
          }
        }
        """
        
        response = await client.post(
            f"{base_url}/graphql",
            json={"query": query}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test REST endpoint
        print("\n7. Testing REST endpoint - Zone sections...")
        response = await client.get(f"{base_url}/api/v1/zones/2/sections")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")


async def test_mock_server_integration():
    """Test integration with mock server"""
    mock_url = "http://localhost:3099"
    
    print("\n\nTesting Mock Server Integration...")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Check mock server health
        print("\n1. Checking mock server health...")
        response = await client.get(f"{mock_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        # Test scheduler demands endpoint
        print("\n2. Testing scheduler demands submission...")
        demands = {
            "week": "2024-W03",
            "demands": [
                {
                    "gate_id": "M(0,2)->Zone_2",
                    "volume_m3": 27000,
                    "priority": 8.5,
                    "sections": ["Zone_2_Section_A", "Zone_2_Section_B"]
                }
            ]
        }
        
        response = await client.post(
            f"{mock_url}/api/v1/scheduler/demands",
            json=demands
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")


if __name__ == "__main__":
    print("ROS/GIS Integration Service Test")
    print("================================")
    print("Make sure both services are running:")
    print("1. Mock server on port 3099")
    print("2. ROS/GIS Integration on port 3022")
    print()
    
    asyncio.run(test_graphql_api())
    asyncio.run(test_mock_server_integration())