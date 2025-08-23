#!/usr/bin/env python3
"""
Complete integration test for ROS-GIS consolidation.
Tests the full flow from ROS sync to GIS query.
"""

import asyncio
import httpx
import sys
from datetime import datetime
import json

# Service URLs
ROS_GIS_URL = "http://localhost:3022"
GIS_URL = "http://localhost:3007"
ROS_URL = "http://localhost:3047"

# Test configuration
TEST_SECTIONS = ["section_1_A", "section_2_B", "section_3_C"]
AUTH_TOKEN = "Bearer mock-token"  # Replace with actual token


async def test_full_integration():
    """Test the complete ROS-GIS consolidation flow"""
    
    print("ROS-GIS Consolidation Integration Test")
    print("=" * 60)
    
    all_passed = True
    
    # Test 1: Check service availability
    print("\n1. Checking service availability...")
    services = [
        ("ROS-GIS Integration", ROS_GIS_URL, "/health"),
        ("GIS Service", GIS_URL, "/health"),
        ("ROS Service", ROS_URL, "/health")
    ]
    
    for name, url, endpoint in services:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}{endpoint}")
                if response.status_code == 200:
                    print(f"   ✓ {name} is running at {url}")
                else:
                    print(f"   ✗ {name} returned {response.status_code}")
                    all_passed = False
        except Exception as e:
            print(f"   ✗ {name} is not accessible: {e}")
            all_passed = False
    
    if not all_passed:
        print("\n❌ Some services are not available. Please start all services first.")
        return False
    
    # Test 2: Trigger ROS sync
    print("\n2. Triggering ROS sync for test sections...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ROS_GIS_URL}/api/v1/sync/trigger",
                json=TEST_SECTIONS
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✓ Sync triggered successfully")
                print(f"   - Success: {result.get('success')}")
                print(f"   - Synced count: {result.get('synced_count', 0)}")
                
                if not result.get('success'):
                    print(f"   ⚠️  Sync reported failure: {result.get('error')}")
                    all_passed = False
            else:
                print(f"   ✗ Sync failed with status {response.status_code}")
                all_passed = False
                
    except Exception as e:
        print(f"   ✗ Error triggering sync: {e}")
        all_passed = False
    
    # Wait for sync to propagate
    print("\n   Waiting for data to propagate...")
    await asyncio.sleep(3)
    
    # Test 3: Query consolidated data from GIS
    print("\n3. Querying consolidated data from GIS...")
    current_week = datetime.now().isocalendar()[1]
    current_year = datetime.now().year
    
    found_count = 0
    for section_id in TEST_SECTIONS:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GIS_URL}/api/v1/ros-demands",
                    params={
                        "sectionId": section_id,
                        "calendarWeek": current_week,
                        "calendarYear": current_year,
                        "latest": "true"
                    },
                    headers={"Authorization": AUTH_TOKEN}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data') and len(data['data']) > 0:
                        demand = data['data'][0]
                        print(f"\n   ✓ {section_id}:")
                        print(f"     - Crop: {demand.get('crop_type')}")
                        print(f"     - Growth Stage: {demand.get('growth_stage')}")
                        print(f"     - Area (rai): {demand.get('area_rai')}")
                        print(f"     - Net Demand (m³): {demand.get('net_demand_m3')}")
                        print(f"     - Week: {demand.get('calendar_week')}")
                        found_count += 1
                    else:
                        print(f"\n   ⚠️  {section_id}: No data found in GIS")
                else:
                    print(f"\n   ✗ {section_id}: GIS query failed ({response.status_code})")
                    all_passed = False
                    
        except Exception as e:
            print(f"\n   ✗ {section_id}: Error querying GIS: {e}")
            all_passed = False
    
    if found_count == 0:
        print("\n   ⚠️  No ROS data found in GIS database")
        all_passed = False
    
    # Test 4: Check weekly summary
    print("\n4. Checking weekly demand summary...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GIS_URL}/api/v1/ros-demands/summary",
                params={
                    "year": current_year,
                    "week": current_week
                },
                headers={"Authorization": AUTH_TOKEN}
            )
            
            if response.status_code == 200:
                data = response.json()
                summaries = data.get('data', [])
                
                if summaries:
                    print(f"   ✓ Weekly summary available:")
                    total_demand = sum(s.get('total_net_demand_m3', 0) for s in summaries)
                    total_area = sum(s.get('total_area_rai', 0) for s in summaries)
                    print(f"     - Total entries: {len(summaries)}")
                    print(f"     - Total demand: {total_demand:,.0f} m³")
                    print(f"     - Total area: {total_area:,.0f} rai")
                else:
                    print("   ⚠️  No summary data available")
            else:
                print(f"   ✗ Summary query failed ({response.status_code})")
                all_passed = False
                
    except Exception as e:
        print(f"   ✗ Error querying summary: {e}")
        all_passed = False
    
    # Test 5: Check sync status
    print("\n5. Checking sync service status...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ROS_GIS_URL}/api/v1/sync/status")
            
            if response.status_code == 200:
                status = response.json()
                print(f"   ✓ Sync service status:")
                print(f"     - Running: {status.get('is_running')}")
                print(f"     - Interval: {status.get('sync_interval_seconds', 0) / 60:.0f} minutes")
                print(f"     - Synced parcels: {status.get('synced_parcels', 0)}")
            else:
                print(f"   ✗ Status query failed ({response.status_code})")
                all_passed = False
                
    except Exception as e:
        print(f"   ✗ Error checking status: {e}")
        all_passed = False
    
    # Final report
    print("\n" + "=" * 60)
    if all_passed and found_count > 0:
        print("✅ All tests passed! ROS-GIS consolidation is working.")
        print(f"   - Successfully synced {found_count}/{len(TEST_SECTIONS)} sections")
        print("   - Data is being stored in GIS database")
        print("   - Weekly summaries are being generated")
        return True
    else:
        print("❌ Some tests failed. Please check:")
        print("   1. All services are running")
        print("   2. Database migration has been executed")
        print("   3. Services can communicate with each other")
        print("   4. ROS service has data for test sections")
        return False


async def main():
    """Main test runner"""
    try:
        success = await test_full_integration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("Starting ROS-GIS Consolidation Integration Test")
    print("Make sure all services are running:")
    print("  - ROS Service on port 3047")
    print("  - GIS Service on port 3007")  
    print("  - ROS-GIS Integration on port 3022")
    print("")
    
    asyncio.run(main())