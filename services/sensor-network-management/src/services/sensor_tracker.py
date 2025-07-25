import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
import numpy as np

from models.sensor import SensorDB, SensorStatus, SensorType
from db.redis import cache_sensor_location, get_cached_locations
from db.influxdb import write_sensor_reading

class SensorTracker:
    """Track and manage mobile sensor fleet"""
    
    def __init__(self):
        self.max_water_sensors = int(os.getenv("MAX_WATER_LEVEL_SENSORS", 6))
        self.max_moisture_sensors = int(os.getenv("MAX_MOISTURE_SENSORS", 1))
        self.battery_threshold = float(os.getenv("SENSOR_BATTERY_LOW_THRESHOLD", 20))
    
    async def update_sensor_location(self, sensor_id: str, lat: float, lon: float, 
                                   section_id: str, db: AsyncSession):
        """Update sensor location and cache it"""
        # Update in database
        await db.execute(
            update(SensorDB)
            .where(SensorDB.id == sensor_id)
            .values(
                latitude=lat,
                longitude=lon,
                current_section_id=section_id,
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()
        
        # Cache in Redis for quick access
        await cache_sensor_location(sensor_id, lat, lon, section_id)
    
    async def record_sensor_reading(self, sensor_id: str, value: float, 
                                  unit: str, quality: float, db: AsyncSession):
        """Record sensor reading and update status"""
        # Get sensor details
        result = await db.execute(
            select(SensorDB).where(SensorDB.id == sensor_id)
        )
        sensor = result.scalar_one_or_none()
        
        if not sensor:
            raise ValueError(f"Sensor {sensor_id} not found")
        
        # Write to InfluxDB
        await write_sensor_reading(
            sensor_id=sensor_id,
            sensor_type=sensor.type,
            value=value,
            unit=unit,
            quality=quality,
            battery=sensor.battery_level,
            lat=sensor.latitude or 0,
            lon=sensor.longitude or 0,
            section_id=sensor.current_section_id
        )
        
        # Update last reading time
        await db.execute(
            update(SensorDB)
            .where(SensorDB.id == sensor_id)
            .values(last_reading=datetime.utcnow())
        )
        await db.commit()
    
    async def get_available_sensors(self, sensor_type: SensorType, 
                                  db: AsyncSession) -> List[SensorDB]:
        """Get available sensors of specific type"""
        result = await db.execute(
            select(SensorDB).where(
                and_(
                    SensorDB.type == sensor_type,
                    SensorDB.status == SensorStatus.ACTIVE,
                    SensorDB.battery_level > self.battery_threshold
                )
            )
        )
        return result.scalars().all()
    
    async def predict_battery_life(self, sensor_id: str, db: AsyncSession) -> Dict:
        """Predict remaining battery life based on usage patterns"""
        # Get sensor
        result = await db.execute(
            select(SensorDB).where(SensorDB.id == sensor_id)
        )
        sensor = result.scalar_one_or_none()
        
        if not sensor:
            raise ValueError(f"Sensor {sensor_id} not found")
        
        # Simple linear prediction based on operational hours
        if sensor.total_operational_hours > 0:
            battery_per_hour = (100 - sensor.battery_level) / sensor.total_operational_hours
            remaining_hours = sensor.battery_level / battery_per_hour if battery_per_hour > 0 else 999
        else:
            remaining_hours = 168  # Default to 1 week
        
        return {
            "sensor_id": sensor_id,
            "current_battery": sensor.battery_level,
            "estimated_hours_remaining": min(remaining_hours, 336),  # Cap at 2 weeks
            "estimated_days_remaining": min(remaining_hours / 24, 14),
            "requires_maintenance": sensor.battery_level < self.battery_threshold
        }
    
    async def get_sensor_health_metrics(self, db: AsyncSession) -> Dict:
        """Get overall health metrics for sensor fleet"""
        # Get all sensors
        result = await db.execute(select(SensorDB))
        sensors = result.scalars().all()
        
        total_sensors = len(sensors)
        active_sensors = sum(1 for s in sensors if s.status == SensorStatus.ACTIVE)
        low_battery = sum(1 for s in sensors if s.battery_level < self.battery_threshold)
        faulty_sensors = sum(1 for s in sensors if s.status == SensorStatus.FAULTY)
        
        # Calculate average accuracy
        accuracies = [s.accuracy_rating for s in sensors if s.accuracy_rating is not None]
        avg_accuracy = np.mean(accuracies) if accuracies else 1.0
        
        return {
            "total_sensors": total_sensors,
            "active_sensors": active_sensors,
            "inactive_sensors": total_sensors - active_sensors,
            "low_battery_sensors": low_battery,
            "faulty_sensors": faulty_sensors,
            "average_accuracy": float(avg_accuracy),
            "utilization_rate": active_sensors / total_sensors if total_sensors > 0 else 0,
            "health_score": (active_sensors - low_battery - faulty_sensors) / total_sensors if total_sensors > 0 else 0
        }
    
    async def calculate_sensor_efficiency(self, sensor_id: str, 
                                        days: int, db: AsyncSession) -> Dict:
        """Calculate sensor efficiency over specified period"""
        # This would typically query historical data
        # For now, return mock metrics
        return {
            "sensor_id": sensor_id,
            "period_days": days,
            "readings_collected": np.random.randint(100, 1000),
            "data_quality_avg": np.random.uniform(0.8, 1.0),
            "uptime_percentage": np.random.uniform(0.9, 1.0) * 100,
            "battery_efficiency": np.random.uniform(0.7, 0.95),
            "movement_efficiency": np.random.uniform(0.8, 1.0)
        }