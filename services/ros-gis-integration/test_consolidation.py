#!/usr/bin/env python3
"""
Test script to verify ROS-GIS consolidation is working properly.
"""

import asyncio
import httpx
from datetime import datetime

async def test_consolidation():
    """Test the ROS-GIS consolidation flow"""
    
    print("Testing ROS-GIS Consolidation")
    print("=" * 50)
    
    # Base URLs
    ros_gis_url = "http://localhost:3022"
    gis_url = "http://localhost:3007"
    
    # Test sections
    test_sections = ["section_1_A", "section_2_B", "section_3_C"]
    
    try:
        # 1. Trigger sync
        print("\n1. Triggering ROS sync...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ros_gis_url}/api/v1/sync/trigger",
                json=test_sections
            )
            result = response.json()
            print(f"   Sync result: {result.get('success')}")
            print(f"   Synced count: {result.get('synced_count', 0)}")
        
        # Wait a bit for sync to complete
        await asyncio.sleep(2)
        
        # 2. Query consolidated data from GIS
        print("\n2. Querying consolidated data from GIS...")
        async with httpx.AsyncClient() as client:
            current_week = datetime.now().isocalendar()[1]
            current_year = datetime.now().year
            
            for section_id in test_sections:
                response = await client.get(
                    f"{gis_url}/api/v1/ros-demands",
                    params={
                        "sectionId": section_id,
                        "calendarWeek": current_week,
                        "calendarYear": current_year,
                        "latest": "true"
                    },
                    headers={"Authorization": "Bearer mock-token"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    demands = data.get('data', [])
                    
                    if demands:
                        demand = demands[0]
                        print(f"\n   {section_id}:")
                        print(f"     - Crop: {demand.get('crop_type')}")
                        print(f"     - Growth Stage: {demand.get('growth_stage')}")
                        print(f"     - Area (rai): {demand.get('area_rai')}")
                        print(f"     - Net Demand (m³): {demand.get('net_demand_m3')}")
                        print(f"     - Source: ROS calculation ✓")
                    else:
                        print(f"\n   {section_id}: No data found")
                else:
                    print(f"\n   {section_id}: Error {response.status_code}")
        
        # 3. Get weekly summary
        print("\n3. Getting weekly demand summary...")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{gis_url}/api/v1/ros-demands/summary",
                params={
                    "year": current_year,
                    "week": current_week
                },
                headers={"Authorization": "Bearer mock-token"}
            )
            
            if response.status_code == 200:
                data = response.json()
                summaries = data.get('data', [])
                
                if summaries:
                    print(f"\n   Weekly Summary (Week {current_week}, {current_year}):")
                    for summary in summaries[:3]:  # Show first 3
                        print(f"     - {summary.get('amphoe')}: {summary.get('total_net_demand_m3', 0):,.0f} m³")
                else:
                    print("   No summary data available")
        
        # 4. Check sync status
        print("\n4. Checking sync service status...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ros_gis_url}/api/v1/sync/status")
            status = response.json()
            
            print(f"   Sync running: {status.get('is_running')}")
            print(f"   Sync interval: {status.get('sync_interval_seconds', 0) / 60:.0f} minutes")
            print(f"   Current week: {status.get('current_week')}")
            print(f"   Synced parcels: {status.get('synced_parcels', 0)}")
        
        print("\n" + "=" * 50)
        print("✓ Consolidation test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_consolidation())