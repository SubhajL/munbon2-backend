#!/usr/bin/env python3
"""
Comprehensive testing suite for Water Accounting Service
Tests all endpoints with the mock server using built-in libraries
"""

import json
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import urllib.error
import time

BASE_URL = "http://localhost:3024/api/v1"
MOCK_URL = "http://localhost:3099/api/v1"

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_section(title):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def print_result(test_name, success, details=""):
    """Print test result"""
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if success else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"{test_name:.<50} {status} {details}")

def print_json(data, indent=2):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=indent, default=str))

def make_request(url, method="GET", data=None):
    """Make HTTP request and return response"""
    try:
        if method == "POST":
            if data:
                data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header('Content-Type', 'application/json')
        else:
            req = urllib.request.Request(url)
        
        with urllib.request.urlopen(req) as response:
            return {
                "status": response.status,
                "data": json.loads(response.read().decode('utf-8'))
            }
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "error": str(e),
            "data": None
        }
    except Exception as e:
        return {
            "status": 0,
            "error": str(e),
            "data": None
        }

def test_mock_server():
    """Test mock server endpoints"""
    print_section("Testing Mock Server Endpoints")
    
    # Test health endpoint
    response = make_request("http://localhost:3099/health")
    success = response["status"] == 200
    print_result("Mock Server Health Check", success, f"Status: {response['status']}")
    if success:
        print(f"{Colors.YELLOW}Mock services available:{Colors.END}")
        for service, status in response["data"]["services"].items():
            print(f"  • {service}: {status}")
    
    # Test water accounting endpoints
    print(f"\n{Colors.BOLD}Testing Water Accounting Mock Endpoints:{Colors.END}")
    
    tests = [
        ("Section Accounting", f"{MOCK_URL}/accounting/section/SEC-Z1-001"),
        ("List Sections", f"{MOCK_URL}/accounting/sections"),
        ("Water Balance", f"{MOCK_URL}/accounting/balance/SEC-Z1-001"),
        ("Efficiency Report", f"{MOCK_URL}/efficiency/report"),
        ("Weekly Deficits", f"{MOCK_URL}/deficits/week/33/2024"),
        ("Stress Assessment", f"{MOCK_URL}/deficits/stress-assessment"),
    ]
    
    for test_name, url in tests:
        response = make_request(url)
        success = response["status"] == 200
        print_result(test_name, success, f"Status: {response['status']}")
        
        if success and test_name == "Section Accounting":
            print(f"\n{Colors.YELLOW}Sample Section Data:{Colors.END}")
            data = response["data"]
            print(f"  Section ID: {data['section_id']}")
            print(f"  Period: {data['period']}")
            print(f"  Delivered: {data['delivered_m3']:,} m³")
            print(f"  Losses: {data['losses_m3']:,} m³")
            print(f"  Efficiency: {data['efficiency']:.1%}")
            print(f"  Deficit: {data['deficit_m3']:,} m³")
    
    return True

def test_delivery_workflow():
    """Test delivery completion workflow"""
    print_section("Testing Delivery Workflow")
    
    # Create sample delivery data
    delivery_data = {
        "section_id": "SEC-Z1-001",
        "flow_readings": []
    }
    
    # Generate 8 hours of flow readings
    base_time = datetime.now() - timedelta(hours=8)
    for i in range(8):
        timestamp = base_time + timedelta(hours=i)
        flow_rate = 2.5 + (i % 3) * 0.3  # Varying flow rate
        delivery_data["flow_readings"].append({
            "timestamp": timestamp.isoformat(),
            "flow_rate_m3s": flow_rate,
            "gate_id": "RG-1-1",
            "quality": 0.95
        })
    
    print(f"{Colors.BOLD}Submitting delivery with {len(delivery_data['flow_readings'])} flow readings...{Colors.END}")
    
    # Submit delivery
    response = make_request(f"{MOCK_URL}/delivery/complete", method="POST", data=delivery_data)
    success = response["status"] == 200
    print_result("Complete Delivery", success, f"Status: {response['status']}")
    
    if success:
        result = response["data"]
        print(f"\n{Colors.YELLOW}Delivery Summary:{Colors.END}")
        print(f"  Delivery ID: {result['delivery_id']}")
        print(f"  Section: {result['section_id']}")
        print(f"  Status: {result['status']}")
        print(f"  Total Volume: {result['summary']['total_volume_m3']:,} m³")
        print(f"  Delivered Volume: {result['summary']['delivered_volume_m3']:,} m³")
        print(f"  Transit Losses: {result['summary']['transit_losses_m3']:,} m³")
        print(f"  Efficiency: {result['summary']['efficiency']:.1%}")
        
        # Check delivery status
        delivery_id = result['delivery_id']
        time.sleep(1)
        
        response = make_request(f"{MOCK_URL}/delivery/status/{delivery_id}")
        success = response["status"] == 200
        print_result("Check Delivery Status", success, f"Status: {response['status']}")
        
        if success:
            status_data = response["data"]
            print(f"  Current Status: {status_data['status']}")
            print(f"  Progress: {status_data['progress_percentage']}%")
    
    return True

def test_efficiency_analysis():
    """Test efficiency analysis features"""
    print_section("Testing Efficiency Analysis")
    
    # Get efficiency report
    response = make_request(f"{MOCK_URL}/efficiency/report")
    success = response["status"] == 200
    print_result("Efficiency Report", success, f"Status: {response['status']}")
    
    if success:
        data = response["data"]
        print(f"\n{Colors.YELLOW}System Efficiency Report - {data['period']}:{Colors.END}")
        print(f"  System Average: {data['system_average']:.1%}")
        print(f"  Benchmark: {data['benchmark']:.1%}")
        print(f"  Total Sections: {len(data['sections'])}")
        
        # Show top performers
        excellent = [s for s in data['sections'] if s['classification'] == 'excellent']
        print(f"\n{Colors.GREEN}Top Performing Sections ({len(excellent)}):{Colors.END}")
        for section in excellent[:3]:
            print(f"  • {section['section_id']}: {section['efficiency']:.1%}")
        
        # Show recommendations
        print(f"\n{Colors.YELLOW}Recommendations:{Colors.END}")
        for rec in data['recommendations']:
            print(f"  • {rec}")
    
    # Calculate transit losses
    print(f"\n{Colors.BOLD}Testing Loss Calculations:{Colors.END}")
    
    loss_scenarios = [
        {"name": "Concrete Canal", "volume_m3": 10000, "distance_km": 5, "canal_type": "concrete"},
        {"name": "Earthen Canal", "volume_m3": 10000, "distance_km": 5, "canal_type": "earthen"},
    ]
    
    for scenario in loss_scenarios:
        loss_data = {
            "volume_m3": scenario["volume_m3"],
            "distance_km": scenario["distance_km"],
            "canal_type": scenario["canal_type"],
            "transit_hours": 4,
            "weather_conditions": {"temperature": 32, "humidity": 65}
        }
        
        response = make_request(f"{MOCK_URL}/efficiency/calculate-losses", method="POST", data=loss_data)
        success = response["status"] == 200
        print_result(f"Calculate Losses - {scenario['name']}", success, f"Status: {response['status']}")
        
        if success:
            result = response["data"]
            print(f"  Total Loss: {result['total_loss_m3']:,} m³ ({result['loss_percentage']:.1f}%)")
            print(f"  - Seepage: {result['breakdown']['seepage_m3']:,} m³")
            print(f"  - Evaporation: {result['breakdown']['evaporation_m3']:,} m³")
            print(f"  - Operational: {result['breakdown']['operational_m3']:,} m³")
    
    return True

def test_deficit_management():
    """Test deficit tracking and management"""
    print_section("Testing Deficit Management")
    
    # Get current week deficits
    current_week = datetime.now().isocalendar()[1]
    response = make_request(f"{MOCK_URL}/deficits/week/{current_week}/2024")
    success = response["status"] == 200
    print_result("Weekly Deficits", success, f"Status: {response['status']}")
    
    if success:
        data = response["data"]
        print(f"\n{Colors.YELLOW}Week {data['week']} Deficit Summary:{Colors.END}")
        print(f"  Total Deficit: {data['summary']['total_deficit_m3']:,} m³")
        print(f"  Sections Affected: {data['summary']['sections_affected']}")
        print(f"  Critical Sections: {data['summary']['critical_sections']}")
        
        # Show sections by stress level
        stress_levels = {}
        for deficit in data['deficits']:
            level = deficit['stress_level']
            if level not in stress_levels:
                stress_levels[level] = 0
            stress_levels[level] += 1
        
        print(f"\n{Colors.BOLD}Stress Level Distribution:{Colors.END}")
        for level in ['none', 'mild', 'moderate', 'severe']:
            count = stress_levels.get(level, 0)
            color = Colors.GREEN if level == 'none' else Colors.YELLOW if level == 'mild' else Colors.RED
            print(f"  {level.capitalize()}: {color}{count}{Colors.END} sections")
    
    # Test recovery planning
    print(f"\n{Colors.BOLD}Testing Recovery Planning:{Colors.END}")
    
    section_id = "SEC-Z3-001"
    
    # Get carry-forward status
    response = make_request(f"{MOCK_URL}/deficits/carry-forward/{section_id}")
    success = response["status"] == 200
    print_result(f"Carry-forward Status - {section_id}", success, f"Status: {response['status']}")
    
    if success:
        carry_data = response["data"]
        total_deficit = carry_data['total_carry_forward_m3']
        
        print(f"  Total Carry-forward: {total_deficit:,} m³")
        print(f"  Priority: {carry_data['recovery_priority']}")
        
        # Generate recovery plan
        recovery_data = {
            "section_id": section_id,
            "deficit_m3": total_deficit
        }
        
        response = make_request(f"{MOCK_URL}/deficits/recovery-plan", method="POST", data=recovery_data)
        success = response["status"] == 200
        print_result("Generate Recovery Plan", success, f"Status: {response['status']}")
        
        if success:
            plan = response["data"]["recovery_plan"]
            print(f"\n{Colors.YELLOW}Recovery Plan Details:{Colors.END}")
            print(f"  Daily Allocation: {plan['daily_allocation_m3']:,} m³")
            print(f"  Days Required: {plan['days_required']}")
            print(f"  Start Date: {plan['start_date']}")
            print(f"  End Date: {plan['end_date']}")
            print(f"  Strategy: {plan['strategy']}")
    
    # Get stress assessment
    response = make_request(f"{MOCK_URL}/deficits/stress-assessment")
    success = response["status"] == 200
    print_result("System Stress Assessment", success, f"Status: {response['status']}")
    
    if success:
        data = response["data"]
        print(f"\n{Colors.YELLOW}System-Wide Stress Summary:{Colors.END}")
        summary = data['system_summary']
        total_sections = sum(summary.values())
        for level, count in summary.items():
            percentage = (count / total_sections * 100) if total_sections > 0 else 0
            print(f"  {level.capitalize()}: {count} sections ({percentage:.1f}%)")
    
    return True

def test_water_balance():
    """Test water balance tracking"""
    print_section("Testing Water Balance Tracking")
    
    section_id = "SEC-Z2-001"
    
    # Get water balance for last 7 days
    start_date = (datetime.now() - timedelta(days=7)).isoformat()
    end_date = datetime.now().isoformat()
    
    url = f"{MOCK_URL}/accounting/balance/{section_id}?start_date={start_date}&end_date={end_date}"
    response = make_request(url)
    success = response["status"] == 200
    print_result(f"Water Balance - {section_id}", success, f"Status: {response['status']}")
    
    if success:
        data = response["data"]
        summary = data['summary']
        
        print(f"\n{Colors.YELLOW}7-Day Water Balance Summary:{Colors.END}")
        print(f"  Section: {data['section_id']}")
        print(f"  Period: {data['period']['start'][:10]} to {data['period']['end'][:10]}")
        print(f"  Total Inflow: {summary['total_inflow_m3']:,} m³")
        print(f"  Total Delivered: {summary['total_delivered_m3']:,} m³")
        print(f"  Total Losses: {summary['total_losses_m3']:,} m³")
        print(f"  Average Efficiency: {summary['average_efficiency']:.1%}")
        
        # Show daily trend
        print(f"\n{Colors.BOLD}Daily Efficiency Trend:{Colors.END}")
        for day in data['daily_balance'][-3:]:  # Last 3 days
            print(f"  {day['date']}: {day['efficiency']:.1%} ({day['delivered_m3']:,} m³)")
    
    return True

def main():
    """Run all tests"""
    print(f"{Colors.BOLD}{Colors.GREEN}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     Water Accounting Service - Comprehensive Testing     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    # Test 1: Mock Server
    test_mock_server()
    
    # Test 2: Delivery Workflow
    test_delivery_workflow()
    
    # Test 3: Efficiency Analysis
    test_efficiency_analysis()
    
    # Test 4: Deficit Management
    test_deficit_management()
    
    # Test 5: Water Balance
    test_water_balance()
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'All Tests Complete!':^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")
    
    print(f"\n{Colors.YELLOW}Note: This test uses the mock server on port 3099.{Colors.END}")
    print(f"{Colors.YELLOW}To test with the actual Water Accounting Service:{Colors.END}")
    print(f"  1. Start the service: cd services/water-accounting")
    print(f"  2. Run: python -m uvicorn src.main:app --reload --port 3024")

if __name__ == "__main__":
    main()