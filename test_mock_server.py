#!/usr/bin/env python3
"""
Test Mock Server Functionality
Tests all mock endpoints that simulate the integrated services
"""

import httpx
import json
from datetime import datetime, timedelta
import asyncio

MOCK_SERVER_URL = "http://localhost:3099"

class MockServerTest:
    def __init__(self):
        self.test_results = []
        self.total = 0
        self.passed = 0

    def record(self, name: str, passed: bool, details: str = ""):
        self.total += 1
        if passed:
            self.passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}: {details}")
        self.test_results.append({"test": name, "passed": passed, "details": details})

    async def test_health(self):
        """Test health endpoint"""
        print("\n📋 Testing Health Endpoints...")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/health")
                data = response.json()
                self.record("Health Check", response.status_code == 200)
                self.record("Services Listed", "services" in data)
                print(f"   Services: {list(data.get('services', {}).keys())}")
            except Exception as e:
                self.record("Health Check", False, str(e))

    async def test_flow_monitoring_endpoints(self):
        """Test Instance 16 Mock Endpoints"""
        print("\n🌊 Testing Flow Monitoring Endpoints (Instance 16)...")
        async with httpx.AsyncClient() as client:
            # Test gate states
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/gates/state")
                data = response.json()
                self.record("Get Gate States", response.status_code == 200)
                gates = data.get("gates", {})
                print(f"   Found {len(gates)} gates")
                for gate_id, state in list(gates.items())[:3]:
                    print(f"   - {gate_id}: {state['opening_m']}m, {state['flow_m3s']} m³/s")
            except Exception as e:
                self.record("Get Gate States", False, str(e))

            # Test water levels
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/network/water-levels")
                data = response.json()
                self.record("Get Water Levels", response.status_code == 200)
                levels = data.get("levels", {})
                for node, info in levels.items():
                    print(f"   - {node}: {info['level_m']}m ({info['trend']})")
            except Exception as e:
                self.record("Get Water Levels", False, str(e))

            # Test hydraulic verification
            try:
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
                response = await client.post(
                    f"{MOCK_SERVER_URL}/api/v1/hydraulics/verify-schedule",
                    json=verification_data
                )
                data = response.json()
                self.record("Hydraulic Verification", response.status_code == 200)
                print(f"   Feasible: {data.get('feasible')}")
                print(f"   Warnings: {data.get('warnings', [])}")
            except Exception as e:
                self.record("Hydraulic Verification", False, str(e))

    async def test_scheduler_endpoints(self):
        """Test Instance 17 Mock Endpoints"""
        print("\n📅 Testing Scheduler Endpoints (Instance 17)...")
        async with httpx.AsyncClient() as client:
            week = "2024-W03"
            
            # Test weekly schedule
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/schedule/week/{week}")
                data = response.json()
                self.record("Get Weekly Schedule", response.status_code == 200)
                ops = data.get("operations", [])
                print(f"   Week: {data.get('week')}")
                print(f"   Status: {data.get('status')}")
                for op in ops:
                    print(f"   - {op['day']}: {op['team']} handles {len(op['gates'])} gates")
            except Exception as e:
                self.record("Get Weekly Schedule", False, str(e))

            # Test field instructions
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/field-ops/instructions/Team_A")
                data = response.json()
                self.record("Get Field Instructions", response.status_code == 200)
                instructions = data.get("instructions", [])
                print(f"   Team: {data.get('team')}")
                for inst in instructions:
                    print(f"   - Gate {inst['gate_id']}: {inst['action']} to {inst['target_opening_m']}m")
                    print(f"     Location: {inst['location']['lat']}, {inst['location']['lon']}")
                    print(f"     Markers: {inst['physical_markers']}")
            except Exception as e:
                self.record("Get Field Instructions", False, str(e))

    async def test_ros_gis_endpoints(self):
        """Test Instance 18 Mock Endpoints"""
        print("\n🌾 Testing ROS/GIS Integration Endpoints (Instance 18)...")
        async with httpx.AsyncClient() as client:
            week = "2024-W03"
            
            # Test weekly demands
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/demands/week/{week}")
                data = response.json()
                self.record("Get Weekly Demands", response.status_code == 200)
                sections = data.get("sections", [])
                print(f"   Found {len(sections)} sections with demands")
                total_demand = sum(s['demand_m3'] for s in sections)
                print(f"   Total demand: {total_demand:,} m³")
                for section in sections[:3]:
                    print(f"   - {section['section_id']}: {section['demand_m3']:,} m³ ({section['crop']})")
            except Exception as e:
                self.record("Get Weekly Demands", False, str(e))

    async def test_other_services(self):
        """Test other service endpoints"""
        print("\n🔧 Testing Other Service Endpoints...")
        async with httpx.AsyncClient() as client:
            # Test sensor management
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/sensors/mobile/status")
                data = response.json()
                self.record("Mobile Sensors Status", response.status_code == 200)
                sensors = data.get("sensors", [])
                print(f"   Found {len(sensors)} mobile sensors")
                for sensor in sensors:
                    print(f"   - {sensor['sensor_id']}: {sensor['last_reading']['value']}{sensor['last_reading']['unit']} (Battery: {sensor['battery_percent']}%)")
            except Exception as e:
                self.record("Mobile Sensors Status", False, str(e))

            # Test water accounting
            try:
                response = await client.get(f"{MOCK_SERVER_URL}/api/v1/accounting/section/Zone_2_Section_A")
                data = response.json()
                self.record("Section Accounting", response.status_code == 200)
                print(f"   Section: {data.get('section_id')}")
                print(f"   Delivered: {data.get('delivered_m3'):,} m³")
                print(f"   Efficiency: {data.get('efficiency')*100:.1f}%")
            except Exception as e:
                self.record("Section Accounting", False, str(e))

            # Test gravity optimizer
            try:
                optimize_data = {
                    "source": "Source",
                    "targets": ["Zone_2", "Zone_5"],
                    "demands": {"Zone_2": 50000, "Zone_5": 30000}
                }
                response = await client.post(
                    f"{MOCK_SERVER_URL}/api/v1/gravity/optimize-flow",
                    json=optimize_data
                )
                data = response.json()
                self.record("Gravity Optimization", response.status_code == 200)
                print(f"   Energy head: {data.get('energy_head_m')} m")
                print(f"   Friction losses: {data.get('friction_losses_m')} m")
                print(f"   Delivery time: {data.get('delivery_time_hours')} hours")
            except Exception as e:
                self.record("Gravity Optimization", False, str(e))

    def generate_report(self):
        """Generate test summary"""
        print("\n" + "="*60)
        print("📊 MOCK SERVER TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.total}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.total - self.passed}")
        print(f"Success Rate: {(self.passed/self.total*100):.1f}%")
        
        # Save report
        report_path = "/Users/subhajlimanond/dev/munbon2-backend/mock_server_test_report.json"
        with open(report_path, 'w') as f:
            json.dump({
                "timestamp": datetime.utcnow().isoformat(),
                "total_tests": self.total,
                "passed": self.passed,
                "failed": self.total - self.passed,
                "success_rate": f"{(self.passed/self.total*100):.1f}%",
                "results": self.test_results
            }, f, indent=2)
        print(f"\n📄 Report saved to: {report_path}")

    async def run_all_tests(self):
        """Run all tests"""
        await self.test_health()
        await self.test_flow_monitoring_endpoints()
        await self.test_scheduler_endpoints()
        await self.test_ros_gis_endpoints()
        await self.test_other_services()
        self.generate_report()

async def main():
    print("🧪 Mock Server Functionality Test")
    print("="*60)
    print("Testing mock server on port 3099...")
    
    tester = MockServerTest()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())