#!/usr/bin/env python3
"""Test script for Sensor Network Management Service"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:3023"

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✓ Health check passed")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Health check error: {e}")

def test_sensor_status():
    """Test sensor status endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/sensors/mobile/status")
        if response.status_code == 200:
            print("✓ Sensor status endpoint working")
            sensors = response.json()
            print(f"  Found {len(sensors)} sensors")
        else:
            print(f"✗ Sensor status failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Sensor status error: {e}")

def test_interpolation():
    """Test interpolation endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/interpolation/section/RMC-01")
        if response.status_code == 200:
            print("✓ Interpolation endpoint working")
            data = response.json()
            print(f"  Water level: {data['value']} {data['unit']}")
            print(f"  Confidence: {data['confidence']['overall']:.2%}")
            print(f"  Method: {data['method']}")
        else:
            print(f"✗ Interpolation failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Interpolation error: {e}")

def test_placement_recommendations():
    """Test placement recommendations"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/placement/recommendations")
        if response.status_code == 200:
            print("✓ Placement recommendations working")
            recommendations = response.json()
            print(f"  Found {len(recommendations)} recommendations")
            if recommendations:
                print(f"  Top priority: {recommendations[0]['section_id']} ({recommendations[0]['priority']})")
        else:
            print(f"✗ Placement recommendations failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Placement recommendations error: {e}")

def test_optimization():
    """Test placement optimization"""
    try:
        request_data = {
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "include_irrigation_schedule": True,
            "include_historical_data": True,
            "include_weather_forecast": True,
            "max_movements_per_week": 7,
            "minimize_travel_distance": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/placement/optimize",
            json=request_data
        )
        
        if response.status_code == 200:
            print("✓ Placement optimization working")
            result = response.json()
            print(f"  Total movements: {result['total_movements']}")
            print(f"  Total distance: {result['total_travel_distance_km']:.1f} km")
            print(f"  Coverage score: {result['coverage_score']:.2%}")
        else:
            print(f"✗ Placement optimization failed: {response.status_code}")
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"✗ Placement optimization error: {e}")

def test_movement_schedule():
    """Test movement schedule"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/movement/schedule/current")
        if response.status_code == 200:
            print("✓ Movement schedule working")
            schedule = response.json()
            print(f"  Week: {schedule['week_start']} to {schedule['week_end']}")
            print(f"  Tasks: {schedule['total_movements']}")
            print(f"  Teams required: {schedule['teams_required']}")
        else:
            print(f"✗ Movement schedule failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Movement schedule error: {e}")

def main():
    """Run all tests"""
    print("Testing Sensor Network Management Service...")
    print(f"Base URL: {BASE_URL}")
    print("-" * 50)
    
    test_health()
    print()
    test_sensor_status()
    print()
    test_interpolation()
    print()
    test_placement_recommendations()
    print()
    test_optimization()
    print()
    test_movement_schedule()
    
    print("-" * 50)
    print("Testing complete!")

if __name__ == "__main__":
    main()