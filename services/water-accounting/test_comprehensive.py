#!/usr/bin/env python3
"""
Comprehensive testing suite for Water Accounting Service
Tests all endpoints with the mock server
"""

import asyncio
import json
from datetime import datetime, timedelta
import sys

# Use urllib instead of httpx to avoid dependency issues
import urllib.request
import urllib.parse
import urllib.error

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

async def test_mock_server():
    """Test mock server endpoints"""
    print_section("Testing Mock Server Endpoints")
    
    async with httpx.AsyncClient() as client:
        tests = [
            ("Health Check", "GET", f"{MOCK_URL}/../health", None),
            ("Section Accounting", "GET", f"{MOCK_URL}/accounting/section/SEC-Z1-001", None),
            ("List Sections", "GET", f"{MOCK_URL}/accounting/sections", None),
            ("List Sections (Zone 2)", "GET", f"{MOCK_URL}/accounting/sections?zone=2", None),
            ("Water Balance", "GET", f"{MOCK_URL}/accounting/balance/SEC-Z1-001", None),
            ("Efficiency Report", "GET", f"{MOCK_URL}/efficiency/report", None),
            ("Efficiency Trends", "GET", f"{MOCK_URL}/efficiency/trends/SEC-Z1-001", None),
            ("Efficiency Benchmarks", "GET", f"{MOCK_URL}/efficiency/benchmarks", None),
            ("Weekly Deficits", "GET", f"{MOCK_URL}/deficits/week/33/2024", None),
            ("Carry Forward Status", "GET", f"{MOCK_URL}/deficits/carry-forward/SEC-Z1-001", None),
            ("Stress Assessment", "GET", f"{MOCK_URL}/deficits/stress-assessment", None),
        ]
        
        results = []
        for test_name, method, url, data in tests:
            try:
                if method == "GET":
                    response = await client.get(url)
                else:
                    response = await client.post(url, json=data)
                
                success = response.status_code == 200
                details = f"Status: {response.status_code}"
                print_result(test_name, success, details)
                
                if success and test_name == "Section Accounting":
                    print(f"{Colors.YELLOW}Sample Response:{Colors.END}")
                    print_json(response.json())
                
                results.append((test_name, success))
            except Exception as e:
                print_result(test_name, False, f"Error: {str(e)}")
                results.append((test_name, False))
        
        # Test POST endpoints
        print(f"\n{Colors.BOLD}Testing POST Endpoints:{Colors.END}")
        
        # Complete Delivery
        delivery_data = {
            "section_id": "SEC-Z1-001",
            "flow_readings": [
                {"timestamp": (datetime.now() - timedelta(hours=i)).isoformat(), 
                 "flow_rate_m3s": 2.5 + (i % 3) * 0.2,
                 "gate_id": "RG-1-1",
                 "quality": 0.95}
                for i in range(6)
            ]
        }
        
        try:
            response = await client.post(f"{MOCK_URL}/delivery/complete", json=delivery_data)
            success = response.status_code == 200
            print_result("Complete Delivery", success, f"Status: {response.status_code}")
            if success:
                print(f"{Colors.YELLOW}Delivery Summary:{Colors.END}")
                print_json(response.json())
        except Exception as e:
            print_result("Complete Delivery", False, f"Error: {str(e)}")
        
        # Calculate Losses
        loss_data = {
            "volume_m3": 15000,
            "distance_km": 8,
            "canal_type": "earthen",
            "transit_hours": 4,
            "weather_conditions": {"temperature": 32, "humidity": 65}
        }
        
        try:
            response = await client.post(f"{MOCK_URL}/efficiency/calculate-losses", json=loss_data)
            success = response.status_code == 200
            print_result("Calculate Transit Losses", success, f"Status: {response.status_code}")
            if success:
                print(f"{Colors.YELLOW}Loss Calculation:{Colors.END}")
                print_json(response.json())
        except Exception as e:
            print_result("Calculate Transit Losses", False, f"Error: {str(e)}")
        
        return all(r[1] for r in results)

async def test_water_accounting_integration():
    """Test water accounting service with mock data"""
    print_section("Testing Water Accounting Service Integration")
    
    async with httpx.AsyncClient() as client:
        # Check if water accounting service is running
        try:
            response = await client.get("http://localhost:3024/health")
            if response.status_code != 200:
                print(f"{Colors.RED}Water Accounting Service not running on port 3024{Colors.END}")
                print("Please start the service with:")
                print("  cd services/water-accounting")
                print("  python -m uvicorn src.main:app --reload --port 3024")
                return False
        except:
            print(f"{Colors.RED}Cannot connect to Water Accounting Service on port 3024{Colors.END}")
            return False
        
        print(f"{Colors.GREEN}✓ Water Accounting Service is running{Colors.END}")
        
        # Test integration endpoints
        print(f"\n{Colors.BOLD}Testing Service Integration:{Colors.END}")
        
        # Test section accounting retrieval
        try:
            response = await client.get(f"{BASE_URL}/accounting/section/SEC-Z1-001")
            success = response.status_code in [200, 404]  # 404 is ok for new system
            print_result("Get Section Accounting", success, f"Status: {response.status_code}")
        except Exception as e:
            print_result("Get Section Accounting", False, f"Error: {str(e)}")
        
        # Test flow data validation
        flow_data = {
            "readings": [
                {"timestamp": datetime.now().isoformat(), "flow_rate_m3s": 2.5, "quality": 0.95},
                {"timestamp": datetime.now().isoformat(), "flow_rate_m3s": 12.0, "quality": 0.7},  # High flow, low quality
            ]
        }
        
        try:
            response = await client.post(f"{BASE_URL}/delivery/validate-flow-data", json=flow_data)
            success = response.status_code == 200
            print_result("Validate Flow Data", success, f"Status: {response.status_code}")
            if success:
                print(f"{Colors.YELLOW}Validation Result:{Colors.END}")
                print_json(response.json())
        except Exception as e:
            print_result("Validate Flow Data", False, f"Error: {str(e)}")

async def test_reconciliation_workflow():
    """Test weekly reconciliation workflow"""
    print_section("Testing Reconciliation Workflow")
    
    async with httpx.AsyncClient() as client:
        # Simulate a week's worth of deliveries
        print(f"{Colors.BOLD}Simulating Weekly Deliveries:{Colors.END}")
        
        sections = ["SEC-Z1-001", "SEC-Z1-002", "SEC-Z2-001"]
        delivery_ids = []
        
        for day in range(7):
            for section in sections:
                # Create delivery data
                delivery_data = {
                    "section_id": section,
                    "flow_readings": [
                        {
                            "timestamp": (datetime.now() - timedelta(days=day, hours=h)).isoformat(),
                            "flow_rate_m3s": 2.0 + (h % 6) * 0.3,
                            "gate_id": f"RG-{section[-5]}-1",
                            "quality": 0.9 + (h % 3) * 0.03
                        }
                        for h in range(8)  # 8 hours of delivery
                    ]
                }
                
                try:
                    response = await client.post(f"{MOCK_URL}/delivery/complete", json=delivery_data)
                    if response.status_code == 200:
                        delivery_id = response.json().get("delivery_id")
                        delivery_ids.append(delivery_id)
                        print(f"  Day {day+1}, {section}: Delivery {delivery_id} completed")
                except Exception as e:
                    print(f"  Day {day+1}, {section}: Failed - {str(e)}")
        
        # Get weekly summary
        print(f"\n{Colors.BOLD}Weekly Summary:{Colors.END}")
        current_week = datetime.now().isocalendar()[1]
        
        try:
            response = await client.get(f"{MOCK_URL}/deficits/week/{current_week}/2024")
            if response.status_code == 200:
                data = response.json()
                print(f"\nWeek {data['week']} Deficit Summary:")
                print(f"Total deficit: {data['summary']['total_deficit_m3']:,} m³")
                print(f"Sections affected: {data['summary']['sections_affected']}")
                print(f"Critical sections: {data['summary']['critical_sections']}")
                
                # Show stress levels
                stress_table = []
                for deficit in data['deficits'][:5]:  # Show first 5
                    stress_table.append([
                        deficit['section_id'],
                        f"{deficit['demand_m3']:,}",
                        f"{deficit['delivered_m3']:,}",
                        f"{deficit['deficit_m3']:,}",
                        f"{deficit['deficit_percentage']:.1f}%",
                        deficit['stress_level']
                    ])
                
                print(f"\n{Colors.BOLD}Section Stress Levels:{Colors.END}")
                print(tabulate(stress_table, 
                              headers=["Section", "Demand (m³)", "Delivered (m³)", "Deficit (m³)", "Deficit %", "Stress"],
                              tablefmt="grid"))
        except Exception as e:
            print(f"Failed to get weekly summary: {str(e)}")

async def test_efficiency_analysis():
    """Test efficiency analysis and reporting"""
    print_section("Testing Efficiency Analysis")
    
    async with httpx.AsyncClient() as client:
        # Get system-wide efficiency report
        try:
            response = await client.get(f"{MOCK_URL}/efficiency/report")
            if response.status_code == 200:
                data = response.json()
                print(f"\n{Colors.BOLD}System Efficiency Report - {data['period']}:{Colors.END}")
                print(f"System Average: {data['system_average']:.1%}")
                print(f"Benchmark: {data['benchmark']:.1%}")
                
                # Show section performance
                perf_table = []
                for section in data['sections']:
                    perf_table.append([
                        section['section_id'],
                        f"{section['delivered_m3']:,}",
                        f"{section['losses_m3']:,}",
                        f"{section['efficiency']:.1%}",
                        section['classification']
                    ])
                
                print(f"\n{Colors.BOLD}Section Performance:{Colors.END}")
                print(tabulate(perf_table,
                              headers=["Section", "Delivered (m³)", "Losses (m³)", "Efficiency", "Classification"],
                              tablefmt="grid"))
                
                print(f"\n{Colors.BOLD}Recommendations:{Colors.END}")
                for rec in data['recommendations']:
                    print(f"  • {rec}")
        except Exception as e:
            print(f"Failed to get efficiency report: {str(e)}")
        
        # Get efficiency trends for a specific section
        section_id = "SEC-Z1-001"
        try:
            response = await client.get(f"{MOCK_URL}/efficiency/trends/{section_id}?weeks=8")
            if response.status_code == 200:
                data = response.json()
                print(f"\n{Colors.BOLD}Efficiency Trends - {section_id}:{Colors.END}")
                print(f"Status: {data['status']}")
                print(f"Improvement rate: {data['improvement_rate']:.1f}%")
                
                # Show weekly trends
                trend_table = []
                for trend in data['trends']:
                    trend_table.append([
                        trend['week'],
                        f"{trend['delivered_m3']:,}",
                        f"{trend['losses_m3']:,}",
                        f"{trend['efficiency']:.1%}"
                    ])
                
                print(f"\n{Colors.BOLD}Weekly Efficiency:{Colors.END}")
                print(tabulate(trend_table,
                              headers=["Week", "Delivered (m³)", "Losses (m³)", "Efficiency"],
                              tablefmt="grid"))
        except Exception as e:
            print(f"Failed to get efficiency trends: {str(e)}")

async def test_deficit_management():
    """Test deficit tracking and recovery planning"""
    print_section("Testing Deficit Management")
    
    async with httpx.AsyncClient() as client:
        # Get stress assessment
        try:
            response = await client.get(f"{MOCK_URL}/deficits/stress-assessment")
            if response.status_code == 200:
                data = response.json()
                print(f"\n{Colors.BOLD}System-Wide Stress Assessment:{Colors.END}")
                print(f"Assessment Date: {data['assessment_date']}")
                
                # Show stress summary
                stress_summary = data['system_summary']
                stress_table = []
                for level, count in stress_summary.items():
                    stress_table.append([level.capitalize(), count])
                
                print(f"\n{Colors.BOLD}Stress Level Distribution:{Colors.END}")
                print(tabulate(stress_table,
                              headers=["Stress Level", "Section Count"],
                              tablefmt="grid"))
                
                # Show zone summary
                zone_table = []
                for zone in data['zones']:
                    zone_table.append([
                        f"Zone {zone['zone']}",
                        zone['zone_stress'],
                        len([s for s in zone['sections'] if s['stress_level'] != 'none'])
                    ])
                
                print(f"\n{Colors.BOLD}Zone Summary:{Colors.END}")
                print(tabulate(zone_table,
                              headers=["Zone", "Zone Stress", "Affected Sections"],
                              tablefmt="grid"))
                
                print(f"\n{Colors.BOLD}Recommendations:{Colors.END}")
                for rec in data['recommendations']:
                    print(f"  • {rec}")
        except Exception as e:
            print(f"Failed to get stress assessment: {str(e)}")
        
        # Test recovery planning
        section_id = "SEC-Z3-001"
        try:
            # First get carry-forward status
            response = await client.get(f"{MOCK_URL}/deficits/carry-forward/{section_id}")
            if response.status_code == 200:
                carry_data = response.json()
                total_deficit = carry_data['total_carry_forward_m3']
                
                print(f"\n{Colors.BOLD}Deficit Recovery Planning - {section_id}:{Colors.END}")
                print(f"Total carry-forward deficit: {total_deficit:,} m³")
                print(f"Recovery priority: {carry_data['recovery_priority']}")
                
                # Generate recovery plan
                recovery_request = {
                    "section_id": section_id,
                    "deficit_m3": total_deficit
                }
                
                response = await client.post(f"{MOCK_URL}/deficits/recovery-plan", json=recovery_request)
                if response.status_code == 200:
                    plan = response.json()['recovery_plan']
                    print(f"\n{Colors.BOLD}Recovery Plan:{Colors.END}")
                    print(f"  Daily allocation: {plan['daily_allocation_m3']:,} m³")
                    print(f"  Days required: {plan['days_required']}")
                    print(f"  Start date: {plan['start_date']}")
                    print(f"  End date: {plan['end_date']}")
                    print(f"  Strategy: {plan['strategy']}")
                    print(f"\n  Constraints:")
                    for constraint in plan['constraints']:
                        print(f"    • {constraint}")
        except Exception as e:
            print(f"Failed to generate recovery plan: {str(e)}")

async def main():
    """Run all tests"""
    print(f"{Colors.BOLD}{Colors.GREEN}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     Water Accounting Service - Comprehensive Testing     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    # Test 1: Mock Server
    mock_ok = await test_mock_server()
    
    if not mock_ok:
        print(f"\n{Colors.RED}Mock server tests failed. Please check if mock server is running on port 3099{Colors.END}")
        return
    
    # Test 2: Water Accounting Integration
    await test_water_accounting_integration()
    
    # Test 3: Reconciliation Workflow
    await test_reconciliation_workflow()
    
    # Test 4: Efficiency Analysis
    await test_efficiency_analysis()
    
    # Test 5: Deficit Management
    await test_deficit_management()
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'Testing Complete!':^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*60}{Colors.END}")

if __name__ == "__main__":
    asyncio.run(main())