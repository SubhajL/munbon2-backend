#!/usr/bin/env python3
"""
Test ROS API endpoints against Excel validation data
"""

import requests
import json
from datetime import datetime

# API base URL
BASE_URL = "http://localhost:3007/api"

def test_eto_endpoint():
    """Test ETo endpoint"""
    print("=== Testing ETo Endpoint ===")
    
    try:
        response = requests.get(f"{BASE_URL}/eto/nakhon-ratchasima")
        if response.status_code == 200:
            data = response.json()
            print(f"Status: SUCCESS")
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Compare with Excel data
            print("\nComparison with Excel data:")
            print(f"Expected May ETo: 145.08 mm")
            print(f"Expected Annual Average: 124.25 mm")
        else:
            print(f"Status: FAILED - {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def test_kc_endpoint():
    """Test Kc endpoint"""
    print("\n=== Testing Kc Endpoint ===")
    
    try:
        response = requests.get(f"{BASE_URL}/kc/rice")
        if response.status_code == 200:
            data = response.json()
            print(f"Status: SUCCESS")
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Compare with Excel data
            print("\nComparison with Excel data:")
            print(f"Expected Average Kc: 1.239")
            print(f"Expected Max Kc: 1.500")
        else:
            print(f"Status: FAILED - {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def test_etc_calculation():
    """Test ETc calculation"""
    print("\n=== Testing ETc Calculation ===")
    
    payload = {
        "location": "nakhon-ratchasima",
        "cropType": "rice",
        "plantingDate": "2025-05-01",
        "area": 45731
    }
    
    try:
        response = requests.post(f"{BASE_URL}/etc/calculate", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"Status: SUCCESS")
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Compare with Excel data
            print("\nComparison with Excel data:")
            print(f"Expected daily ETc (average): 5.80 mm/day")
            print(f"Expected weekly ETc: 40.60 mm/week")
        else:
            print(f"Status: FAILED - {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def test_water_requirements():
    """Test water requirements calculation"""
    print("\n=== Testing Water Requirements ===")
    
    payload = {
        "cropType": "rice",
        "area": 45731,
        "location": "nakhon-ratchasima",
        "plantingDate": "2025-05-01",
        "includeSeepage": True
    }
    
    try:
        response = requests.post(f"{BASE_URL}/water-requirements", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"Status: SUCCESS")
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Compare with Excel data
            print("\nComparison with Excel data:")
            print(f"Expected weekly requirement (with seepage): 54.60 mm/week")
            print(f"Expected weekly volume: 3,994,883 m³")
            print(f"Expected daily volume: 570,698 m³")
        else:
            print(f"Status: FAILED - {response.status_code}")
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    print(f"Testing ROS API at {BASE_URL}")
    print(f"Test Date: {datetime.now().isoformat()}")
    print("=" * 50)
    
    # Load validation data for reference
    with open('ros_validation_summary.json', 'r') as f:
        validation_data = json.load(f)
    
    print("\nExpected values from Excel:")
    print(f"- Annual Average ETo: {validation_data['eto_annual_average']:.2f} mm")
    print(f"- Rice Average Kc: {validation_data['rice_kc_average']:.3f}")
    print(f"- Seepage Rate: {validation_data['seepage_rate']} mm/week")
    print(f"- Rice Area: {validation_data['rice_area']:.0f} rai")
    print("=" * 50)
    
    # Run tests
    test_eto_endpoint()
    test_kc_endpoint()
    test_etc_calculation()
    test_water_requirements()
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("- Check if ROS API values match Excel calculations")
    print("- Acceptable variance: ±5% for most calculations")
    print("- Key metrics to verify:")
    print("  1. ETo monthly values")
    print("  2. Kc growth stage values")
    print("  3. ETc calculations")
    print("  4. Water volume calculations")

if __name__ == "__main__":
    main()