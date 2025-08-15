#!/usr/bin/env python3
"""
Simple API test script for Water Accounting Service
"""

import httpx
import asyncio
from datetime import datetime, timedelta
import json

BASE_URL = "http://localhost:3024"

async def test_health():
    """Test health endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code}")
        print(f"Response: {response.json()}\n")

async def test_section_accounting():
    """Test section accounting endpoint"""
    async with httpx.AsyncClient() as client:
        section_id = "SEC-101"
        response = await client.get(f"{BASE_URL}/api/v1/accounting/section/{section_id}")
        print(f"Section Accounting ({section_id}): {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}\n")
        else:
            print(f"Error: {response.text}\n")

async def test_sections_list():
    """Test sections list endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/accounting/sections?has_deficit=true")
        print(f"Sections List (with deficit): {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Total sections: {data.get('total_sections')}")
            print(f"Sections with deficit: {data.get('sections_with_deficit')}\n")
        else:
            print(f"Error: {response.text}\n")

async def test_water_balance():
    """Test water balance endpoint"""
    async with httpx.AsyncClient() as client:
        section_id = "SEC-101"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
        
        response = await client.get(
            f"{BASE_URL}/api/v1/accounting/balance/{section_id}",
            params=params
        )
        print(f"Water Balance ({section_id}): {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}\n")
        else:
            print(f"Error: {response.text}\n")

async def test_delivery_completion():
    """Test delivery completion endpoint"""
    async with httpx.AsyncClient() as client:
        delivery_data = {
            "delivery_id": "DEL-TEST-001",
            "section_id": "SEC-101",
            "scheduled_start": (datetime.now() - timedelta(hours=4)).isoformat(),
            "scheduled_end": datetime.now().isoformat(),
            "scheduled_volume_m3": 5000,
            "actual_start": (datetime.now() - timedelta(hours=4)).isoformat(),
            "actual_end": datetime.now().isoformat(),
            "flow_readings": [
                {
                    "timestamp": (datetime.now() - timedelta(hours=4)).isoformat(),
                    "flow_rate_m3s": 0.5,
                    "gate_id": "GATE-001"
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
                    "flow_rate_m3s": 0.8,
                    "gate_id": "GATE-001"
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "flow_rate_m3s": 0.7,
                    "gate_id": "GATE-001"
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                    "flow_rate_m3s": 0.4,
                    "gate_id": "GATE-001"
                },
                {
                    "timestamp": datetime.now().isoformat(),
                    "flow_rate_m3s": 0.0,
                    "gate_id": "GATE-001"
                }
            ],
            "environmental_conditions": {
                "temperature_c": 32,
                "humidity_percent": 65,
                "wind_speed_ms": 2.5
            }
        }
        
        response = await client.post(
            f"{BASE_URL}/api/v1/delivery/complete",
            json=delivery_data
        )
        print(f"Delivery Completion: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}\n")
        else:
            print(f"Error: {response.text}\n")

async def test_efficiency_report():
    """Test efficiency report endpoint"""
    async with httpx.AsyncClient() as client:
        params = {
            "report_type": "weekly",
            "zone_id": "ZONE-A"
        }
        
        response = await client.get(
            f"{BASE_URL}/api/v1/efficiency/report",
            params=params
        )
        print(f"Efficiency Report: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Report ID: {data.get('report_id')}")
            print(f"Total sections: {data.get('total_sections')}")
            if 'summary_statistics' in data:
                stats = data['summary_statistics']
                print(f"Average delivery efficiency: {stats.get('avg_delivery_efficiency')}%")
                print(f"Average overall efficiency: {stats.get('avg_overall_efficiency')}%\n")
        else:
            print(f"Error: {response.text}\n")

async def test_weekly_deficits():
    """Test weekly deficits endpoint"""
    async with httpx.AsyncClient() as client:
        # Get current week
        now = datetime.now()
        week = now.isocalendar().week
        year = now.year
        
        response = await client.get(f"{BASE_URL}/api/v1/deficits/week/{week}/{year}")
        print(f"Weekly Deficits (Week {week}, {year}): {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}\n")
        else:
            print(f"Error: {response.text}\n")

async def test_calculate_losses():
    """Test loss calculation endpoint"""
    async with httpx.AsyncClient() as client:
        loss_data = {
            "flow_data": {
                "flow_rate_m3s": 0.5,
                "transit_time_hours": 2.0,
                "volume_m3": 3600
            },
            "canal_characteristics": {
                "type": "lined",
                "length_km": 5.0,
                "width_m": 3.0,
                "water_depth_m": 1.0
            },
            "environmental_conditions": {
                "temperature_c": 30,
                "humidity_percent": 60,
                "wind_speed_ms": 2,
                "solar_radiation_wm2": 250
            }
        }
        
        response = await client.post(
            f"{BASE_URL}/api/v1/efficiency/calculate-losses",
            json=loss_data
        )
        print(f"Calculate Losses: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}\n")
        else:
            print(f"Error: {response.text}\n")

async def main():
    """Run all tests"""
    print("=" * 60)
    print("Water Accounting Service API Tests")
    print("=" * 60)
    print()
    
    # Run tests
    await test_health()
    await test_section_accounting()
    await test_sections_list()
    await test_water_balance()
    await test_delivery_completion()
    await test_efficiency_report()
    await test_weekly_deficits()
    await test_calculate_losses()
    
    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())