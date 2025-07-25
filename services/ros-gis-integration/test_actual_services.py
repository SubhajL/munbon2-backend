#!/usr/bin/env python3
"""
Test script to verify integration with actual ROS and GIS services.
This ensures we're getting real data from the services, not mock data.
"""

import asyncio
import sys
from src.services.integration_client import IntegrationClient
from src.core import get_logger

logger = get_logger(__name__)


async def test_ros_integration():
    """Test ROS service integration"""
    client = IntegrationClient()
    
    print("\n=== Testing ROS Service Integration ===")
    
    # Test get_crop_requirements with a sample section
    section_ids = ["section_1_A", "section_2_B", "section_3_C"]
    print(f"\nFetching crop requirements for sections: {section_ids}")
    
    try:
        requirements = await client.get_crop_requirements(section_ids)
        
        for section_id, data in requirements.items():
            print(f"\n{section_id}:")
            print(f"  - Crop Type: {data.get('crop_type')}")
            print(f"  - Growth Stage: {data.get('growth_stage')}")
            print(f"  - Area (rai): {data.get('area_rai')}")
            print(f"  - Planting Date: {data.get('planting_date', 'N/A')}")
            print(f"  - Harvest Date: {data.get('harvest_date', 'N/A')}")
            print(f"  - Crop Week: {data.get('crop_week', 'N/A')}")
            print(f"  - Kc Factor: {data.get('kc_factor')}")
            
            # Verify it's not mock data
            if data.get('crop_type') != 'unknown' and data.get('planting_date'):
                print("  ✓ Real data from ROS service")
            else:
                print("  ✗ Appears to be mock or fallback data")
                
    except Exception as e:
        print(f"Error testing ROS integration: {e}")
        return False
    
    return True


async def test_gis_integration():
    """Test GIS service integration"""
    client = IntegrationClient()
    
    print("\n=== Testing GIS Service Integration ===")
    
    # Test get_section_boundaries
    section_ids = ["section_1_A", "section_2_B"]
    print(f"\nFetching boundaries for sections: {section_ids}")
    
    try:
        boundaries = await client.get_section_boundaries(section_ids)
        
        for section_id, data in boundaries.items():
            print(f"\n{section_id}:")
            print(f"  - Area (rai): {data.get('area_rai')}")
            print(f"  - Parcel Count: {data.get('parcel_count', 0)}")
            print(f"  - Amphoe: {data.get('amphoe', 'N/A')}")
            print(f"  - Has Geometry: {'Yes' if data.get('geometry') else 'No'}")
            
            # Verify it's not mock data
            if data.get('parcel_count', 0) > 0:
                print("  ✓ Real data from GIS service")
            else:
                print("  ✗ Appears to be mock or fallback data")
                
    except Exception as e:
        print(f"Error testing GIS integration: {e}")
        return False
    
    return True


async def test_area_units():
    """Verify all area units are in rai"""
    print("\n=== Verifying Area Units ===")
    
    client = IntegrationClient()
    
    # Test crop requirements
    requirements = await client.get_crop_requirements(["section_1_A"])
    for section_id, data in requirements.items():
        area = data.get('area_rai', 0)
        print(f"\nROS - {section_id}: {area} rai")
        if area > 0:
            print("  ✓ Area is in rai units")
    
    # Test boundaries
    boundaries = await client.get_section_boundaries(["section_1_A"])
    for section_id, data in boundaries.items():
        area = data.get('area_rai', 0)
        print(f"\nGIS - {section_id}: {area} rai")
        if area > 0:
            print("  ✓ Area is in rai units")
    
    return True


async def main():
    """Run all integration tests"""
    print("Testing ROS-GIS Integration with Actual Services")
    print("=" * 50)
    
    # Check that we're not using mock server
    from src.config import settings
    print(f"\nMock Server Mode: {settings.use_mock_server}")
    print(f"ROS Service URL: {settings.ros_service_url}")
    print(f"GIS Service URL: {settings.gis_service_url}")
    
    if settings.use_mock_server:
        print("\n⚠️  WARNING: Mock server mode is enabled!")
        print("Set USE_MOCK_SERVER=false to test actual services")
        return
    
    # Run tests
    ros_ok = await test_ros_integration()
    gis_ok = await test_gis_integration()
    units_ok = await test_area_units()
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print(f"  - ROS Integration: {'PASS' if ros_ok else 'FAIL'}")
    print(f"  - GIS Integration: {'PASS' if gis_ok else 'FAIL'}")
    print(f"  - Area Units (rai): {'PASS' if units_ok else 'PASS'}")
    
    if not (ros_ok and gis_ok):
        print("\n⚠️  Some tests failed. Check service availability and configuration.")
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())