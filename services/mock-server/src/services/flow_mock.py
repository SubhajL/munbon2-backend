"""Mock flow monitoring service endpoints"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
from fastapi import APIRouter, Query, HTTPException

router = APIRouter()

# Mock flow sensor data
MOCK_FLOW_SENSORS = [
    {
        "sensor_id": "FS-001",
        "location": "Main Canal Entry",
        "section_id": "S1",
        "type": "electromagnetic",
        "status": "active",
        "calibration_date": "2024-01-15"
    },
    {
        "sensor_id": "FS-002",
        "location": "Distribution Point A",
        "section_id": "S2",
        "type": "ultrasonic",
        "status": "active",
        "calibration_date": "2024-02-20"
    }
]

# Mock flow readings
def generate_flow_reading(sensor_id: str, timestamp: datetime) -> Dict:
    """Generate realistic flow reading"""
    base_flow = 150 + random.uniform(-30, 30)  # m³/s
    return {
        "sensor_id": sensor_id,
        "timestamp": timestamp.isoformat(),
        "flow_rate": round(base_flow, 2),
        "velocity": round(base_flow / 100, 2),  # m/s
        "cross_section_area": 100,  # m²
        "confidence": round(0.85 + random.uniform(0, 0.1), 2),
        "quality": "good" if random.random() > 0.1 else "degraded"
    }

@router.get("/api/v1/flow/current")
async def get_current_flow(
    section_id: Optional[str] = Query(None),
    sensor_id: Optional[str] = Query(None)
):
    """Get current flow readings"""
    print(f"[Mock Flow] GET current flow - section: {section_id}, sensor: {sensor_id}")
    
    sensors = MOCK_FLOW_SENSORS
    if section_id:
        sensors = [s for s in sensors if s["section_id"] == section_id]
    if sensor_id:
        sensors = [s for s in sensors if s["sensor_id"] == sensor_id]
    
    current_time = datetime.utcnow()
    readings = []
    
    for sensor in sensors:
        reading = generate_flow_reading(sensor["sensor_id"], current_time)
        reading["location"] = sensor["location"]
        reading["section_id"] = sensor["section_id"]
        readings.append(reading)
    
    return {
        "timestamp": current_time.isoformat(),
        "readings": readings,
        "total_flow": sum(r["flow_rate"] for r in readings),
        "sensor_count": len(readings)
    }

@router.get("/api/v1/flow/history")
async def get_flow_history(
    section_id: str,
    start_date: str,
    end_date: str,
    interval: str = Query("hourly", regex="^(minutely|hourly|daily)$")
):
    """Get historical flow data"""
    print(f"[Mock Flow] GET flow history for section {section_id} from {start_date} to {end_date}")
    
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Generate time series data
    interval_delta = {
        "minutely": timedelta(minutes=1),
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1)
    }[interval]
    
    data_points = []
    current = start
    base_flow = 150
    
    while current <= end:
        # Add some realistic variation
        flow_rate = base_flow + 20 * random.sin(current.timestamp() / 86400) + random.uniform(-10, 10)
        data_points.append({
            "timestamp": current.isoformat(),
            "flow_rate": round(flow_rate, 2),
            "velocity": round(flow_rate / 100, 2),
            "quality": "good"
        })
        current += interval_delta
    
    return {
        "section_id": section_id,
        "start_date": start_date,
        "end_date": end_date,
        "interval": interval,
        "data_points": data_points,
        "statistics": {
            "average_flow": round(sum(dp["flow_rate"] for dp in data_points) / len(data_points), 2),
            "max_flow": round(max(dp["flow_rate"] for dp in data_points), 2),
            "min_flow": round(min(dp["flow_rate"] for dp in data_points), 2),
            "total_volume": round(sum(dp["flow_rate"] for dp in data_points) * interval_delta.total_seconds(), 2)
        }
    }

@router.get("/api/v1/flow/sensors")
async def get_flow_sensors():
    """Get all flow sensor information"""
    print("[Mock Flow] GET flow sensors")
    
    sensors_with_status = []
    for sensor in MOCK_FLOW_SENSORS:
        sensor_info = sensor.copy()
        sensor_info["last_reading"] = datetime.utcnow().isoformat()
        sensor_info["battery_level"] = 85 + random.uniform(0, 15)
        sensor_info["signal_strength"] = -60 + random.uniform(-10, 10)
        sensors_with_status.append(sensor_info)
    
    return {
        "total_sensors": len(sensors_with_status),
        "active_sensors": len([s for s in sensors_with_status if s["status"] == "active"]),
        "sensors": sensors_with_status,
        "last_update": datetime.utcnow().isoformat()
    }

@router.post("/api/v1/flow/calibrate")
async def calibrate_sensor(calibration_data: Dict):
    """Calibrate a flow sensor"""
    print(f"[Mock Flow] POST calibrate sensor: {calibration_data}")
    
    sensor_id = calibration_data.get("sensor_id")
    if not sensor_id:
        raise HTTPException(status_code=400, detail="sensor_id is required")
    
    # Find sensor
    sensor = next((s for s in MOCK_FLOW_SENSORS if s["sensor_id"] == sensor_id), None)
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    return {
        "success": True,
        "sensor_id": sensor_id,
        "calibration": {
            "date": datetime.utcnow().isoformat(),
            "coefficients": {
                "offset": calibration_data.get("offset", 0),
                "scale": calibration_data.get("scale", 1),
                "linearization": calibration_data.get("linearization", [])
            },
            "reference_flow": calibration_data.get("reference_flow", 100),
            "calibrated_by": calibration_data.get("calibrated_by", "System")
        },
        "message": "Sensor calibrated successfully"
    }

@router.get("/api/v1/flow/balance/{section_id}")
async def get_flow_balance(
    section_id: str,
    date: Optional[str] = Query(None)
):
    """Get flow balance for a section (inflow vs outflow)"""
    print(f"[Mock Flow] GET flow balance for section {section_id}")
    
    target_date = datetime.utcnow() if not date else datetime.fromisoformat(date.replace('Z', '+00:00'))
    
    # Generate mock balance data
    inflow = 180 + random.uniform(-20, 20)
    distribution = {
        "canal_1": inflow * 0.4,
        "canal_2": inflow * 0.35,
        "canal_3": inflow * 0.2,
        "losses": inflow * 0.05
    }
    
    return {
        "section_id": section_id,
        "date": target_date.date().isoformat(),
        "balance": {
            "total_inflow": round(inflow, 2),
            "total_outflow": round(sum(distribution.values()), 2),
            "distribution": {k: round(v, 2) for k, v in distribution.items()},
            "efficiency": round((1 - distribution["losses"] / inflow) * 100, 1)
        },
        "hourly_pattern": [
            {
                "hour": h,
                "inflow": round(inflow * (0.8 + 0.4 * abs(12 - h) / 12), 2),
                "outflow": round(inflow * (0.8 + 0.4 * abs(12 - h) / 12) * 0.95, 2)
            }
            for h in range(24)
        ]
    }

@router.get("/api/v1/flow/alerts")
async def get_flow_alerts():
    """Get active flow alerts"""
    print("[Mock Flow] GET flow alerts")
    
    alerts = []
    
    # Generate some mock alerts
    if random.random() > 0.7:
        alerts.append({
            "alert_id": "FA-001",
            "type": "low_flow",
            "severity": "warning",
            "sensor_id": "FS-001",
            "section_id": "S1",
            "message": "Flow rate below threshold",
            "threshold": 100,
            "current_value": 85,
            "triggered_at": datetime.utcnow().isoformat(),
            "status": "active"
        })
    
    if random.random() > 0.8:
        alerts.append({
            "alert_id": "FA-002",
            "type": "sensor_fault",
            "severity": "critical",
            "sensor_id": "FS-002",
            "section_id": "S2",
            "message": "Sensor communication lost",
            "last_contact": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
            "triggered_at": datetime.utcnow().isoformat(),
            "status": "active"
        })
    
    return {
        "total_alerts": len(alerts),
        "critical": len([a for a in alerts if a["severity"] == "critical"]),
        "warnings": len([a for a in alerts if a["severity"] == "warning"]),
        "alerts": alerts,
        "last_check": datetime.utcnow().isoformat()
    }