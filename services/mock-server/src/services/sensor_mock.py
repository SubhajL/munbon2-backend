"""Mock sensor data service endpoints"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
from fastapi import APIRouter, Query

router = APIRouter()

# Mock water level sensor data
MOCK_WATER_LEVEL_DATA = [
    {
        "id": "wl-001",
        "sensor_id": "WL-SENSOR-001",
        "type": "ultrasonic",
        "section_id": "S1",
        "level_cm": 250.5,
        "voltage": 3.2,
        "rssi": -65,
        "quality_score": 0.95,
        "timestamp": datetime.utcnow().isoformat()
    },
    {
        "id": "wl-002",
        "sensor_id": "WL-SENSOR-002",
        "type": "pressure",
        "section_id": "S2",
        "level_cm": 180.3,
        "voltage": 3.1,
        "rssi": -72,
        "quality_score": 0.88,
        "timestamp": datetime.utcnow().isoformat()
    }
]

# Mock moisture sensor data
MOCK_MOISTURE_DATA = [
    {
        "id": "ms-001",
        "sensor_id": "MS-SENSOR-001",
        "plot_id": "P001",
        "moisture_percent": 65.5,
        "temperature_c": 28.3,
        "ec_value": 1.2,
        "battery_percent": 85,
        "timestamp": datetime.utcnow().isoformat()
    },
    {
        "id": "ms-002",
        "sensor_id": "MS-SENSOR-002",
        "plot_id": "P002",
        "moisture_percent": 58.2,
        "temperature_c": 29.1,
        "ec_value": 1.4,
        "battery_percent": 92,
        "timestamp": datetime.utcnow().isoformat()
    }
]

@router.get("/api/v1/water-levels/{section_id}")
async def get_water_levels(
    section_id: str,
    date: Optional[str] = Query(None),
    include_raw: Optional[bool] = Query(False)
):
    """Get water level readings for a section"""
    print(f"[Mock Sensor Data] GET water levels for section: {section_id}")
    
    # Filter readings by section
    section_readings = [
        reading for reading in MOCK_WATER_LEVEL_DATA 
        if reading["section_id"] == section_id
    ]
    
    # Generate historical data if date is provided
    readings = section_readings
    if date:
        target_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
        readings = []
        for reading in section_readings:
            modified_reading = reading.copy()
            modified_reading["timestamp"] = target_date.isoformat()
            # Add some variation to historical data
            modified_reading["level_cm"] = reading["level_cm"] + random.uniform(-10, 10)
            readings.append(modified_reading)
    
    avg_level = sum(r["level_cm"] for r in readings) / len(readings) if readings else 0
    
    return {
        "section_id": section_id,
        "date": date or datetime.utcnow().date().isoformat(),
        "readings": readings,
        "metadata": {
            "sensor_count": len(readings),
            "average_level_cm": avg_level,
            "last_update": datetime.utcnow().isoformat()
        }
    }

@router.get("/api/v1/moisture/{plot_id}")
async def get_moisture(
    plot_id: str,
    date: Optional[str] = Query(None)
):
    """Get moisture readings for a plot"""
    print(f"[Mock Sensor Data] GET moisture for plot: {plot_id}")
    
    # Filter readings by plot
    plot_readings = [
        reading for reading in MOCK_MOISTURE_DATA 
        if reading["plot_id"] == plot_id
    ]
    
    # Generate historical data if date is provided
    readings = plot_readings
    if date:
        target_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
        readings = []
        for reading in plot_readings:
            modified_reading = reading.copy()
            modified_reading["timestamp"] = target_date.isoformat()
            # Add variation to historical data
            modified_reading["moisture_percent"] = reading["moisture_percent"] + random.uniform(-5, 5)
            readings.append(modified_reading)
    
    if readings:
        moisture_values = [r["moisture_percent"] for r in readings]
        summary = {
            "average_moisture": sum(moisture_values) / len(moisture_values),
            "min_moisture": min(moisture_values),
            "max_moisture": max(moisture_values),
            "sensor_count": len(readings)
        }
    else:
        summary = {
            "average_moisture": 0,
            "min_moisture": 0,
            "max_moisture": 0,
            "sensor_count": 0
        }
    
    return {
        "plot_id": plot_id,
        "date": date or datetime.utcnow().date().isoformat(),
        "readings": readings,
        "summary": summary
    }

@router.get("/api/v1/sensors/status")
async def get_sensor_status():
    """Get status of all sensors"""
    print("[Mock Sensor Data] GET sensor status")
    
    all_sensors = []
    
    # Add water level sensors
    for sensor in MOCK_WATER_LEVEL_DATA:
        all_sensors.append({
            "sensor_id": sensor["sensor_id"],
            "type": "water_level",
            "status": "active",
            "battery_percent": 85 + random.uniform(0, 15),
            "last_reading": sensor["timestamp"],
            "location": sensor["section_id"]
        })
    
    # Add moisture sensors
    for sensor in MOCK_MOISTURE_DATA:
        all_sensors.append({
            "sensor_id": sensor["sensor_id"],
            "type": "moisture",
            "status": "active",
            "battery_percent": sensor["battery_percent"],
            "last_reading": sensor["timestamp"],
            "location": sensor["plot_id"]
        })
    
    return {
        "total_sensors": len(all_sensors),
        "active_sensors": len([s for s in all_sensors if s["status"] == "active"]),
        "sensors": all_sensors,
        "last_update": datetime.utcnow().isoformat()
    }

@router.post("/api/v1/readings/water-level")
async def create_water_level_reading(reading_data: Dict):
    """Create a new water level reading"""
    print(f"[Mock Sensor Data] POST water level reading: {reading_data}")
    
    reading = {
        "id": f"wl-{int(datetime.utcnow().timestamp() * 1000)}",
        **reading_data,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "accepted"
    }
    
    return {
        "success": True,
        "reading": reading,
        "message": "Water level reading accepted"
    }

@router.post("/api/v1/readings/moisture")
async def create_moisture_reading(reading_data: Dict):
    """Create a new moisture reading"""
    print(f"[Mock Sensor Data] POST moisture reading: {reading_data}")
    
    reading = {
        "id": f"ms-{int(datetime.utcnow().timestamp() * 1000)}",
        **reading_data,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "accepted"
    }
    
    return {
        "success": True,
        "reading": reading,
        "message": "Moisture reading accepted"
    }

@router.get("/api/v1/telemetry/latest")
async def get_latest_telemetry():
    """Get latest telemetry from all sensors"""
    print("[Mock Sensor Data] GET latest telemetry")
    
    water_levels = [
        {
            "sensor_id": s["sensor_id"],
            "section_id": s["section_id"],
            "level_cm": s["level_cm"],
            "timestamp": s["timestamp"]
        }
        for s in MOCK_WATER_LEVEL_DATA
    ]
    
    moisture_levels = [
        {
            "sensor_id": s["sensor_id"],
            "plot_id": s["plot_id"],
            "moisture_percent": s["moisture_percent"],
            "timestamp": s["timestamp"]
        }
        for s in MOCK_MOISTURE_DATA
    ]
    
    return {
        "water_levels": water_levels,
        "moisture_levels": moisture_levels,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/api/v1/analytics/water-level-trends")
async def get_water_level_trends(
    section_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=30)
):
    """Get water level trends over time"""
    print(f"[Mock Sensor Data] GET water level trends for {days} days")
    
    trends = []
    base_level = 200
    
    for i in range(days):
        date = datetime.utcnow().date() - timedelta(days=days-i-1)
        
        # Generate realistic trend data
        avg_level = base_level + random.uniform(-50, 50)
        min_level = avg_level - random.uniform(20, 50)
        max_level = avg_level + random.uniform(20, 50)
        
        trends.append({
            "date": date.isoformat(),
            "average_level_cm": round(avg_level, 1),
            "min_level_cm": round(min_level, 1),
            "max_level_cm": round(max_level, 1),
            "reading_count": 24 + random.randint(0, 10)
        })
    
    return {
        "section_id": section_id or "all",
        "period_days": days,
        "trends": trends,
        "generated_at": datetime.utcnow().isoformat()
    }