"""Integration test script for Water Accounting Service"""

import asyncio
import httpx
from datetime import datetime, timedelta
import json

WATER_ACCOUNTING_URL = "http://localhost:3024/api/v1"
MOCK_SERVER_URL = "http://localhost:3099/api/v1"

async def test_water_accounting():
    """Test water accounting service with mock data"""
    
    async with httpx.AsyncClient() as client:
        print("Testing Water Accounting Service Integration...")
        print("=" * 50)
        
        # 1. Test health endpoint
        try:
            response = await client.get("http://localhost:3024/health")
            print(f"✓ Health check: {response.json()}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            return
        
        # 2. Test section accounting retrieval
        section_id = "SEC-Z1-001"
        try:
            response = await client.get(f"{WATER_ACCOUNTING_URL}/accounting/section/{section_id}")
            if response.status_code == 200:
                print(f"✓ Section accounting retrieved for {section_id}")
            else:
                print(f"! Section not found (expected for new system)")
        except Exception as e:
            print(f"✗ Section accounting failed: {e}")
        
        # 3. Test delivery completion
        print("\nTesting delivery completion...")
        
        # Create sample flow readings
        now = datetime.now()
        flow_readings = []
        for i in range(24):  # 24 hours of readings
            timestamp = now - timedelta(hours=24-i)
            flow_rate = 5.0 + (i % 4) * 0.5  # Varying flow rate
            flow_readings.append({
                "timestamp": timestamp.isoformat(),
                "flow_rate_m3s": flow_rate,
                "gate_id": "RG-1-1",
                "quality": 1.0
            })
        
        delivery_data = {
            "delivery_id": f"DEL-{now.strftime('%Y%m%d%H%M%S')}",
            "section_id": section_id,
            "scheduled_start": (now - timedelta(hours=24)).isoformat(),
            "scheduled_end": now.isoformat(),
            "scheduled_volume_m3": 400000.0,
            "actual_start": (now - timedelta(hours=24)).isoformat(),
            "actual_end": now.isoformat(),
            "flow_readings": flow_readings,
            "consumed_volume_m3": 380000.0,
            "environmental_conditions": {
                "temperature_c": 32,
                "humidity_percent": 65,
                "wind_speed_ms": 2.5
            },
            "notes": "Test delivery completion"
        }
        
        try:
            response = await client.post(
                f"{WATER_ACCOUNTING_URL}/delivery/complete",
                json=delivery_data
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Delivery completed: {result['delivery_id']}")
                print(f"  - Gate outflow: {result['accounting_summary']['volumes']['gate_outflow_m3']:.2f} m³")
                print(f"  - Section inflow: {result['accounting_summary']['volumes']['section_inflow_m3']:.2f} m³")
                print(f"  - Transit loss: {result['accounting_summary']['volumes']['transit_loss_m3']:.2f} m³")
                print(f"  - Delivery efficiency: {result['accounting_summary']['efficiency']['delivery_efficiency']:.2%}")
            else:
                print(f"✗ Delivery completion failed: {response.status_code}")
                print(f"  Error: {response.text}")
        except Exception as e:
            print(f"✗ Delivery completion error: {e}")
        
        # 4. Test efficiency report generation
        print("\nTesting efficiency report generation...")
        try:
            response = await client.get(
                f"{WATER_ACCOUNTING_URL}/efficiency/report",
                params={
                    "report_type": "weekly",
                    "start_date": (now - timedelta(days=7)).isoformat(),
                    "end_date": now.isoformat()
                }
            )
            if response.status_code == 200:
                report = response.json()
                print(f"✓ Efficiency report generated: {report['report_id']}")
                print(f"  - Total sections: {report['total_sections']}")
                if report['total_sections'] > 0:
                    print(f"  - Avg delivery efficiency: {report['summary_statistics']['avg_delivery_efficiency']:.2%}")
            else:
                print(f"! Efficiency report: {response.status_code} (expected for limited data)")
        except Exception as e:
            print(f"✗ Efficiency report error: {e}")
        
        # 5. Test deficit tracking
        print("\nTesting deficit tracking...")
        week_number = datetime.now().isocalendar()[1]
        year = datetime.now().year
        
        try:
            response = await client.get(
                f"{WATER_ACCOUNTING_URL}/deficits/week/{week_number}/{year}"
            )
            if response.status_code == 200:
                deficits = response.json()
                print(f"✓ Weekly deficit summary retrieved")
                print(f"  - Week: {week_number}/{year}")
                print(f"  - Total sections: {deficits.get('summary_statistics', {}).get('total_sections', 0)}")
            else:
                print(f"! Deficit summary: {response.status_code}")
        except Exception as e:
            print(f"✗ Deficit tracking error: {e}")
        
        # 6. Test flow data validation
        print("\nTesting flow data validation...")
        try:
            # Test with some invalid data
            invalid_readings = flow_readings[:5] + [
                {"timestamp": now.isoformat(), "flow_rate_m3s": -1.0},  # Negative flow
                {"timestamp": (now + timedelta(hours=5)).isoformat(), "flow_rate_m3s": 100.0}  # Outlier
            ]
            
            response = await client.post(
                f"{WATER_ACCOUNTING_URL}/delivery/validate-flow-data",
                json=invalid_readings
            )
            if response.status_code == 200:
                validation = response.json()
                print(f"✓ Flow validation completed")
                print(f"  - Valid: {validation['valid']}")
                print(f"  - Quality score: {validation['quality_score']:.2f}")
                print(f"  - Issues: {len(validation['issues'])}")
                for issue in validation['issues']:
                    print(f"    • {issue}")
            else:
                print(f"✗ Flow validation failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Flow validation error: {e}")
        
        # 7. Test loss calculation
        print("\nTesting loss calculation...")
        try:
            loss_request = {
                "flow_data": {
                    "flow_rate_m3s": 5.0,
                    "transit_time_hours": 4.0,
                    "volume_m3": 72000.0
                },
                "canal_characteristics": {
                    "length_km": 10.0,
                    "type": "earthen",
                    "width_m": 5.0,
                    "water_depth_m": 1.5
                },
                "environmental_conditions": {
                    "temperature_c": 35,
                    "humidity_percent": 40,
                    "wind_speed_ms": 3.0,
                    "solar_radiation_wm2": 300
                }
            }
            
            response = await client.post(
                f"{WATER_ACCOUNTING_URL}/efficiency/calculate-losses",
                json=loss_request
            )
            if response.status_code == 200:
                losses = response.json()
                print(f"✓ Loss calculation completed")
                print(f"  - Total loss: {losses['losses']['total_loss_m3']:.2f} m³")
                print(f"  - Loss percentage: {losses['losses']['loss_percentage']:.2f}%")
                print(f"  - Breakdown:")
                for loss_type, value in losses['losses']['breakdown'].items():
                    print(f"    • {loss_type}: {value:.2f} m³")
                print(f"  - Confidence score: {losses['uncertainty']['confidence_score']:.2f}")
            else:
                print(f"✗ Loss calculation failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Loss calculation error: {e}")
        
        print("\n" + "=" * 50)
        print("Integration test completed!")

if __name__ == "__main__":
    asyncio.run(test_water_accounting())