#!/usr/bin/env python3
"""
Comprehensive Test Suite for Scheduler Service
Tests all API endpoints and integrations with mock services
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
import time
import subprocess
import os
import signal
from typing import Dict, List, Optional

# Service URLs
MOCK_SERVER_URL = "http://localhost:3099"
SCHEDULER_URL = "http://localhost:3021"

class SchedulerTestSuite:
    def __init__(self):
        self.mock_server_process = None
        self.scheduler_process = None
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0

    async def start_services(self):
        """Start mock server and scheduler service"""
        print("\n🚀 Starting services...")
        
        # Start mock server
        print("Starting mock server on port 3099...")
        self.mock_server_process = subprocess.Popen(
            ["python3", "services/flow-monitoring/mock-server/app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Wait for mock server to start
        await self.wait_for_service(MOCK_SERVER_URL + "/health", "Mock Server")
        
        # Start scheduler service
        print("Starting scheduler service on port 3021...")
        os.environ['FLOW_MONITORING_URL'] = MOCK_SERVER_URL
        os.environ['ROS_GIS_URL'] = MOCK_SERVER_URL
        os.environ['POSTGRES_URL'] = 'postgresql://postgres:postgres@localhost:5432/munbon'
        os.environ['REDIS_URL'] = 'redis://localhost:6379/1'
        
        # Change to scheduler directory
        os.chdir('services/scheduler')
        self.scheduler_process = subprocess.Popen(
            ["python3", "-m", "uvicorn", "src.main:app", "--port", "3021"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        os.chdir('../..')
        
        # Wait for scheduler to start
        await self.wait_for_service(SCHEDULER_URL + "/health", "Scheduler Service")
        
    async def wait_for_service(self, url: str, service_name: str, max_attempts: int = 30):
        """Wait for a service to become available"""
        async with httpx.AsyncClient() as client:
            for i in range(max_attempts):
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        print(f"✅ {service_name} is ready!")
                        return True
                except:
                    pass
                await asyncio.sleep(1)
                print(f"Waiting for {service_name}... ({i+1}/{max_attempts})")
        
        raise Exception(f"❌ {service_name} failed to start after {max_attempts} attempts")

    def stop_services(self):
        """Stop all services"""
        print("\n🛑 Stopping services...")
        if self.mock_server_process:
            os.killpg(os.getpgid(self.mock_server_process.pid), signal.SIGTERM)
        if self.scheduler_process:
            os.killpg(os.getpgid(self.scheduler_process.pid), signal.SIGTERM)

    def record_test(self, test_name: str, passed: bool, details: str = ""):
        """Record test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"✅ {test_name}")
        else:
            print(f"❌ {test_name}: {details}")
        
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })

    async def test_health_endpoints(self):
        """Test health check endpoints"""
        print("\n📋 Testing Health Endpoints...")
        
        async with httpx.AsyncClient() as client:
            # Test mock server health
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/health")
                self.record_test("Mock Server Health", response.status_code == 200)
            except Exception as e:
                self.record_test("Mock Server Health", False, str(e))
            
            # Test scheduler health
            try:
                response = await client.get(f"{SCHEDULER_URL}/health")
                self.record_test("Scheduler Health", response.status_code == 200)
            except Exception as e:
                self.record_test("Scheduler Health", False, str(e))
            
            # Test scheduler readiness
            try:
                response = await client.get(f"{SCHEDULER_URL}/ready")
                self.record_test("Scheduler Readiness", response.status_code == 200)
            except Exception as e:
                self.record_test("Scheduler Readiness", False, str(e))

    async def test_schedule_endpoints(self):
        """Test schedule management endpoints"""
        print("\n📅 Testing Schedule Endpoints...")
        
        async with httpx.AsyncClient() as client:
            week = "2024-W03"
            
            # Generate schedule
            try:
                response = await client.post(f"{SCHEDULER_URL}/api/v1/schedule/week/{week}/generate")
                self.record_test("Generate Weekly Schedule", response.status_code in [200, 201])
                if response.status_code in [200, 201]:
                    schedule_data = response.json()
            except Exception as e:
                self.record_test("Generate Weekly Schedule", False, str(e))
            
            # Get schedule
            try:
                response = await client.get(f"{SCHEDULER_URL}/api/v1/schedule/week/{week}")
                self.record_test("Get Weekly Schedule", response.status_code == 200)
            except Exception as e:
                self.record_test("Get Weekly Schedule", False, str(e))
            
            # Get current schedule
            try:
                response = await client.get(f"{SCHEDULER_URL}/api/v1/schedule/current")
                self.record_test("Get Current Schedule", response.status_code in [200, 404])
            except Exception as e:
                self.record_test("Get Current Schedule", False, str(e))
            
            # Check conflicts
            try:
                response = await client.get(f"{SCHEDULER_URL}/api/v1/schedule/conflicts/{week}")
                self.record_test("Check Schedule Conflicts", response.status_code == 200)
            except Exception as e:
                self.record_test("Check Schedule Conflicts", False, str(e))

    async def test_demand_endpoints(self):
        """Test demand processing endpoints"""
        print("\n💧 Testing Demand Endpoints...")
        
        async with httpx.AsyncClient() as client:
            week = "2024-W03"
            
            # Submit demands
            demands_data = {
                "week": week,
                "sections": [
                    {
                        "section_id": "Zone_2_Section_A",
                        "demand_m3": 15000,
                        "crop": "rice",
                        "priority": 9
                    }
                ]
            }
            
            try:
                response = await client.post(
                    f"{SCHEDULER_URL}/api/v1/scheduler/demands",
                    json=demands_data
                )
                self.record_test("Submit Water Demands", response.status_code in [200, 201])
                if response.status_code in [200, 201]:
                    result = response.json()
                    schedule_id = result.get("schedule_id")
            except Exception as e:
                self.record_test("Submit Water Demands", False, str(e))
            
            # Get demands
            try:
                response = await client.get(f"{SCHEDULER_URL}/api/v1/scheduler/demands/week/{week}")
                self.record_test("Get Weekly Demands", response.status_code == 200)
            except Exception as e:
                self.record_test("Get Weekly Demands", False, str(e))
            
            # Validate demands
            try:
                response = await client.post(
                    f"{SCHEDULER_URL}/api/v1/scheduler/demands/validate",
                    json=demands_data
                )
                self.record_test("Validate Demands", response.status_code == 200)
            except Exception as e:
                self.record_test("Validate Demands", False, str(e))

    async def test_field_ops_endpoints(self):
        """Test field operations endpoints"""
        print("\n🚜 Testing Field Operations Endpoints...")
        
        async with httpx.AsyncClient() as client:
            team = "Team_A"
            
            # Get team instructions
            try:
                response = await client.get(f"{SCHEDULER_URL}/api/v1/field-ops/instructions/{team}")
                self.record_test("Get Team Instructions", response.status_code == 200)
            except Exception as e:
                self.record_test("Get Team Instructions", False, str(e))
            
            # Download offline package
            try:
                response = await client.post(f"{SCHEDULER_URL}/api/v1/field-ops/instructions/download/{team}")
                self.record_test("Download Offline Package", response.status_code == 200)
            except Exception as e:
                self.record_test("Download Offline Package", False, str(e))
            
            # Get teams status
            try:
                response = await client.get(f"{SCHEDULER_URL}/api/v1/field-ops/teams/status")
                self.record_test("Get Teams Status", response.status_code == 200)
            except Exception as e:
                self.record_test("Get Teams Status", False, str(e))
            
            # Update team location
            location_data = {
                "lat": 14.8234,
                "lon": 103.1567,
                "timestamp": datetime.utcnow().isoformat()
            }
            try:
                response = await client.post(
                    f"{SCHEDULER_URL}/api/v1/field-ops/teams/{team}/location",
                    json=location_data
                )
                self.record_test("Update Team Location", response.status_code in [200, 201])
            except Exception as e:
                self.record_test("Update Team Location", False, str(e))

    async def test_integration_flow(self):
        """Test complete integration flow"""
        print("\n🔄 Testing Integration Flow...")
        
        async with httpx.AsyncClient() as client:
            week = "2024-W03"
            
            # 1. Submit demands (simulating ROS/GIS service)
            demands_data = {
                "week": week,
                "sections": [
                    {
                        "section_id": "Zone_2_Section_A",
                        "demand_m3": 15000,
                        "crop": "rice",
                        "priority": 9,
                        "delivery_window": {
                            "start": datetime.utcnow().isoformat(),
                            "end": (datetime.utcnow() + timedelta(days=7)).isoformat()
                        }
                    }
                ]
            }
            
            try:
                response = await client.post(
                    f"{SCHEDULER_URL}/api/v1/scheduler/demands",
                    json=demands_data
                )
                self.record_test("Integration: Submit Demands", response.status_code in [200, 201])
            except Exception as e:
                self.record_test("Integration: Submit Demands", False, str(e))
            
            # 2. Generate schedule
            try:
                response = await client.post(f"{SCHEDULER_URL}/api/v1/schedule/week/{week}/generate")
                self.record_test("Integration: Generate Schedule", response.status_code in [200, 201])
            except Exception as e:
                self.record_test("Integration: Generate Schedule", False, str(e))
            
            # 3. Get field instructions
            try:
                response = await client.get(f"{SCHEDULER_URL}/api/v1/field-ops/instructions/Team_A")
                self.record_test("Integration: Get Instructions", response.status_code == 200)
                if response.status_code == 200:
                    instructions = response.json()
            except Exception as e:
                self.record_test("Integration: Get Instructions", False, str(e))
            
            # 4. Report operation completion
            if 'instructions' in locals() and instructions.get('instructions'):
                operation_id = "OP-001"  # Would come from instructions
                report_data = {
                    "operation_id": operation_id,
                    "status": "completed",
                    "actual_opening_m": 1.5,
                    "notes": "Completed successfully",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                try:
                    response = await client.put(
                        f"{SCHEDULER_URL}/api/v1/field-ops/operations/{operation_id}/report",
                        json=report_data
                    )
                    self.record_test("Integration: Report Completion", response.status_code in [200, 201])
                except Exception as e:
                    self.record_test("Integration: Report Completion", False, str(e))

    async def test_mock_service_integration(self):
        """Test integration with mock services"""
        print("\n🔗 Testing Mock Service Integration...")
        
        async with httpx.AsyncClient() as client:
            # Test Flow Monitoring integration
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/gates/state")
                self.record_test("Mock: Gate States Available", response.status_code == 200)
            except Exception as e:
                self.record_test("Mock: Gate States Available", False, str(e))
            
            # Test hydraulic verification
            verification_data = {
                "proposed_operations": [
                    {
                        "gate_id": "M(0,0)->M(0,2)",
                        "action": "adjust",
                        "target_opening_m": 1.5,
                        "scheduled_time": datetime.utcnow().isoformat()
                    }
                ],
                "constraints": {}
            }
            
            try:
                response = await client.post(
                    f"{MOCK_SERVER_URL}/api/v1/hydraulics/verify-schedule",
                    json=verification_data
                )
                self.record_test("Mock: Hydraulic Verification", response.status_code == 200)
                if response.status_code == 200:
                    result = response.json()
                    self.record_test("Mock: Verification Feasible", result.get("feasible", False))
            except Exception as e:
                self.record_test("Mock: Hydraulic Verification", False, str(e))

    def generate_report(self):
        """Generate test report"""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY REPORT")
        print("="*60)
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.total_tests - self.passed_tests}")
        print(f"Success Rate: {(self.passed_tests/self.total_tests*100):.1f}%")
        print("\nDetailed Results:")
        print("-"*60)
        
        for result in self.test_results:
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {result['test']}")
            if not result["passed"] and result["details"]:
                print(f"   └─ {result['details']}")
        
        # Save report to file
        report_path = "/Users/subhajlimanond/dev/munbon2-backend/scheduler_test_report.json"
        with open(report_path, 'w') as f:
            json.dump({
                "timestamp": datetime.utcnow().isoformat(),
                "total_tests": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.total_tests - self.passed_tests,
                "success_rate": f"{(self.passed_tests/self.total_tests*100):.1f}%",
                "results": self.test_results
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_path}")

    async def run_all_tests(self):
        """Run all tests"""
        try:
            # Start services
            await self.start_services()
            
            # Run test suites
            await self.test_health_endpoints()
            await self.test_schedule_endpoints()
            await self.test_demand_endpoints()
            await self.test_field_ops_endpoints()
            await self.test_integration_flow()
            await self.test_mock_service_integration()
            
            # Generate report
            self.generate_report()
            
        except Exception as e:
            print(f"\n❌ Test suite failed: {str(e)}")
        finally:
            # Stop services
            self.stop_services()

async def main():
    """Main test runner"""
    print("🧪 Munbon Scheduler Service - Comprehensive Test Suite")
    print("="*60)
    
    test_suite = SchedulerTestSuite()
    await test_suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())