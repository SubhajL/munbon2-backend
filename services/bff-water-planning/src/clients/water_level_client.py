"""
Water Level Client
Handles fetching water level data from various sources including
manual readings, sensor data, and aggregated values
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import httpx
from decimal import Decimal
import asyncio

from config import settings
from core import get_logger
from db import DatabaseManager

logger = get_logger(__name__)


class WaterLevelClient:
    """Client for fetching and managing water level data"""
    
    def __init__(self):
        self.logger = logger.bind(client="water_level")
        self.db = DatabaseManager()
        # Use mock server URL if enabled, otherwise use sensor data service URL
        if settings.use_mock_server:
            self.sensor_data_url = f"{settings.mock_server_url}/sensor"
        else:
            self.sensor_data_url = getattr(settings, 'sensor_data_url', 'http://localhost:3003')
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._use_mock = settings.use_mock_server
        
    async def get_current_water_level(self, section_id: str) -> Optional[Dict]:
        """
        Get latest water level for a section from all sources
        Returns the most recent aggregated water level with confidence score
        """
        try:
            # First check aggregated data
            query = """
                SELECT 
                    section_id,
                    date,
                    avg_water_level_m as water_level_m,
                    min_water_level_m,
                    max_water_level_m,
                    data_source,
                    manual_reading_count,
                    sensor_reading_count,
                    confidence_score,
                    updated_at
                FROM ros_gis.water_level_aggregations
                WHERE section_id = $1
                AND date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY date DESC, confidence_score DESC
                LIMIT 1
            """
            
            result = await self.db.fetch_one(query, section_id)
            
            if result:
                return {
                    "section_id": result["section_id"],
                    "water_level_m": float(result["water_level_m"]),
                    "min_level_m": float(result["min_water_level_m"]) if result["min_water_level_m"] else None,
                    "max_level_m": float(result["max_water_level_m"]) if result["max_water_level_m"] else None,
                    "date": result["date"].isoformat(),
                    "data_source": result["data_source"],
                    "confidence_score": float(result["confidence_score"]) if result["confidence_score"] else 0,
                    "reading_count": result["manual_reading_count"] + result["sensor_reading_count"],
                    "last_updated": result["updated_at"].isoformat()
                }
            
            # If no aggregated data, try to get latest sensor reading
            return await self._get_latest_sensor_reading(section_id)
            
        except Exception as e:
            self.logger.error("Failed to get current water level", 
                            section_id=section_id, error=str(e))
            return None
    
    async def get_manual_readings(self, section_id: str, target_date: date) -> List[Dict]:
        """Get manual water level readings from GeoPackage imports or field volunteers"""
        try:
            query = """
                SELECT 
                    reading_id,
                    location_id,
                    section_id,
                    plot_id,
                    water_level_m,
                    reading_date,
                    reading_time,
                    volunteer_id,
                    volunteer_name,
                    geopackage_source,
                    ST_X(coordinates) as longitude,
                    ST_Y(coordinates) as latitude,
                    notes,
                    data_quality
                FROM ros_gis.manual_water_level_readings
                WHERE section_id = $1 
                AND reading_date = $2
                ORDER BY reading_time DESC
            """
            
            results = await self.db.fetch_all(query, section_id, target_date)
            
            return [
                {
                    "reading_id": str(row["reading_id"]),
                    "section_id": row["section_id"],
                    "plot_id": row["plot_id"],
                    "water_level_m": float(row["water_level_m"]),
                    "reading_datetime": datetime.combine(
                        row["reading_date"], 
                        row["reading_time"] or datetime.min.time()
                    ).isoformat(),
                    "volunteer": {
                        "id": row["volunteer_id"],
                        "name": row["volunteer_name"]
                    } if row["volunteer_id"] else None,
                    "location": {
                        "longitude": row["longitude"],
                        "latitude": row["latitude"]
                    } if row["longitude"] else None,
                    "geopackage_source": row["geopackage_source"],
                    "notes": row["notes"],
                    "data_quality": row["data_quality"]
                }
                for row in results
            ]
            
        except Exception as e:
            self.logger.error("Failed to get manual readings", 
                            section_id=section_id, date=str(target_date), error=str(e))
            return []
    
    async def get_sensor_readings(self, section_id: str, target_date: date) -> List[Dict]:
        """Get sensor water level readings from sensor-data service"""
        if self._use_mock:
            return self._mock_sensor_readings(section_id, target_date)
        
        try:
            # Try local database first
            query = """
                SELECT 
                    sensor_reading_id,
                    sensor_id,
                    sensor_type,
                    section_id,
                    water_level_m,
                    voltage,
                    rssi,
                    quality_score,
                    reading_timestamp
                FROM ros_gis.sensor_water_levels
                WHERE section_id = $1 
                AND DATE(reading_timestamp) = $2
                ORDER BY reading_timestamp DESC
            """
            
            results = await self.db.fetch_all(query, section_id, target_date)
            
            if results:
                return [self._format_sensor_reading(row) for row in results]
            
            # If no local data, fetch from sensor-data service
            return await self._fetch_from_sensor_service(section_id, target_date)
            
        except Exception as e:
            self.logger.error("Failed to get sensor readings", 
                            section_id=section_id, date=str(target_date), error=str(e))
            return []
    
    async def get_water_level_with_thresholds(self, section_id: str) -> Optional[Dict]:
        """Get current water level with operational thresholds"""
        try:
            query = """
                SELECT 
                    wls.*,
                    s.zone,
                    s.area_rai
                FROM ros_gis.v_water_level_status wls
                JOIN ros_gis.sections s ON wls.section_id = s.section_id
                WHERE wls.section_id = $1
            """
            
            result = await self.db.fetch_one(query, section_id)
            
            if result:
                return {
                    "section_id": result["section_id"],
                    "zone": result["zone"],
                    "area_rai": float(result["area_rai"]) if result["area_rai"] else None,
                    "water_level_m": float(result["water_level_m"]),
                    "status": result["status"],
                    "reading_date": result["reading_date"].isoformat(),
                    "thresholds": {
                        "critical_low": float(result["critical_low"]) if result["critical_low"] else None,
                        "warning_low": float(result["warning_low"]) if result["warning_low"] else None,
                        "optimal": float(result["optimal"]) if result["optimal"] else None,
                        "warning_high": float(result["warning_high"]) if result["warning_high"] else None,
                        "critical_high": float(result["critical_high"]) if result["critical_high"] else None
                    }
                }
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get water level with thresholds", 
                            section_id=section_id, error=str(e))
            return None
    
    async def calculate_adjustment_factor(self, section_id: str, water_level_m: float) -> float:
        """Calculate demand adjustment factor based on water level and thresholds"""
        try:
            # Get thresholds for the section
            thresholds = await self._get_section_thresholds(section_id)
            
            if not thresholds:
                # No thresholds defined, no adjustment
                return 1.0
            
            # Use the database function for consistent calculation
            query = """
                SELECT ros_gis.calculate_water_adjustment_factor(
                    $1::DECIMAL, $2::DECIMAL, $3::DECIMAL, 
                    $4::DECIMAL, $5::DECIMAL, $6::DECIMAL
                ) as adjustment_factor
            """
            
            result = await self.db.fetch_one(
                query,
                water_level_m,
                thresholds.get("critical_low", 0.5),
                thresholds.get("warning_low", 1.0),
                thresholds.get("optimal", 2.0),
                thresholds.get("warning_high", 3.0),
                thresholds.get("critical_high", 3.5)
            )
            
            return float(result["adjustment_factor"]) if result else 1.0
            
        except Exception as e:
            self.logger.error("Failed to calculate adjustment factor", 
                            section_id=section_id, water_level=water_level_m, error=str(e))
            return 1.0
    
    async def save_demand_adjustment(
        self, 
        section_id: str, 
        target_date: date,
        original_demand_m3: float,
        water_level_m: float,
        adjustment_factor: float,
        adjusted_demand_m3: float,
        reason: str
    ) -> bool:
        """Save water level based demand adjustment"""
        try:
            query = """
                INSERT INTO ros_gis.water_level_demand_adjustments (
                    section_id, date, original_demand_m3, water_level_m,
                    adjustment_factor, adjusted_demand_m3, adjustment_reason
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (section_id, date) 
                DO UPDATE SET
                    original_demand_m3 = EXCLUDED.original_demand_m3,
                    water_level_m = EXCLUDED.water_level_m,
                    adjustment_factor = EXCLUDED.adjustment_factor,
                    adjusted_demand_m3 = EXCLUDED.adjusted_demand_m3,
                    adjustment_reason = EXCLUDED.adjustment_reason,
                    created_at = CURRENT_TIMESTAMP
            """
            
            await self.db.execute(
                query,
                section_id, target_date, original_demand_m3, water_level_m,
                adjustment_factor, adjusted_demand_m3, reason
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to save demand adjustment", 
                            section_id=section_id, date=str(target_date), error=str(e))
            return False
    
    async def trigger_aggregation(self, section_id: str, target_date: date) -> bool:
        """Trigger water level aggregation for a section/date"""
        try:
            query = "SELECT ros_gis.aggregate_water_levels($1, $2)"
            await self.db.execute(query, section_id, target_date)
            return True
        except Exception as e:
            self.logger.error("Failed to trigger aggregation", 
                            section_id=section_id, date=str(target_date), error=str(e))
            return False
    
    # Private helper methods
    
    async def _get_latest_sensor_reading(self, section_id: str) -> Optional[Dict]:
        """Get the most recent sensor reading for a section"""
        try:
            query = """
                SELECT 
                    sensor_id,
                    section_id,
                    water_level_m,
                    quality_score,
                    reading_timestamp
                FROM ros_gis.sensor_water_levels
                WHERE section_id = $1
                ORDER BY reading_timestamp DESC
                LIMIT 1
            """
            
            result = await self.db.fetch_one(query, section_id)
            
            if result:
                return {
                    "section_id": result["section_id"],
                    "water_level_m": float(result["water_level_m"]),
                    "date": result["reading_timestamp"].date().isoformat(),
                    "data_source": "sensor",
                    "sensor_id": result["sensor_id"],
                    "confidence_score": float(result["quality_score"]) if result["quality_score"] else 0.5,
                    "reading_count": 1,
                    "last_updated": result["reading_timestamp"].isoformat()
                }
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get latest sensor reading", 
                            section_id=section_id, error=str(e))
            return None
    
    async def _get_section_thresholds(self, section_id: str) -> Dict[str, float]:
        """Get water level thresholds for a section"""
        try:
            query = """
                SELECT 
                    threshold_type,
                    water_level_m
                FROM ros_gis.water_level_thresholds
                WHERE section_id = $1
                AND effective_date <= CURRENT_DATE
                AND (expires_date IS NULL OR expires_date >= CURRENT_DATE)
            """
            
            results = await self.db.fetch_all(query, section_id)
            
            return {
                row["threshold_type"]: float(row["water_level_m"])
                for row in results
            }
            
        except Exception as e:
            self.logger.error("Failed to get section thresholds", 
                            section_id=section_id, error=str(e))
            return {}
    
    async def _fetch_from_sensor_service(self, section_id: str, target_date: date) -> List[Dict]:
        """Fetch water level data from sensor-data service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.sensor_data_url}/api/v1/water-levels/{section_id}",
                    params={
                        "date": target_date.isoformat(),
                        "include_raw": True
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return [
                        self._format_external_sensor_reading(reading) 
                        for reading in data.get("readings", [])
                    ]
                
                return []
                
        except Exception as e:
            self.logger.error("Failed to fetch from sensor service", 
                            section_id=section_id, error=str(e))
            return []
    
    def _format_sensor_reading(self, row: Dict) -> Dict:
        """Format sensor reading from database row"""
        return {
            "reading_id": str(row["sensor_reading_id"]),
            "sensor_id": row["sensor_id"],
            "sensor_type": row["sensor_type"],
            "section_id": row["section_id"],
            "water_level_m": float(row["water_level_m"]),
            "voltage": float(row["voltage"]) if row["voltage"] else None,
            "rssi": row["rssi"],
            "quality_score": float(row["quality_score"]) if row["quality_score"] else None,
            "reading_timestamp": row["reading_timestamp"].isoformat()
        }
    
    def _format_external_sensor_reading(self, data: Dict) -> Dict:
        """Format sensor reading from external service"""
        return {
            "reading_id": data.get("id"),
            "sensor_id": data.get("sensor_id"),
            "sensor_type": data.get("type", "unknown"),
            "section_id": data.get("section_id"),
            "water_level_m": data.get("level_cm", 0) / 100.0,  # Convert cm to m
            "voltage": data.get("voltage"),
            "rssi": data.get("rssi"),
            "quality_score": data.get("quality_score"),
            "reading_timestamp": data.get("timestamp")
        }
    
    def _mock_sensor_readings(self, section_id: str, target_date: date) -> List[Dict]:
        """Generate mock sensor readings for development"""
        import random
        
        base_level = 2.0 + random.uniform(-0.5, 0.5)
        readings = []
        
        for hour in range(0, 24, 6):  # Every 6 hours
            timestamp = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)
            variation = random.uniform(-0.1, 0.1)
            
            readings.append({
                "reading_id": f"mock-{section_id}-{hour}",
                "sensor_id": f"WL-{section_id[-4:]}",
                "sensor_type": "ultrasonic",
                "section_id": section_id,
                "water_level_m": round(base_level + variation, 3),
                "voltage": round(3.3 + random.uniform(-0.1, 0.1), 2),
                "rssi": random.randint(-80, -40),
                "quality_score": round(random.uniform(0.8, 1.0), 2),
                "reading_timestamp": timestamp.isoformat()
            })
        
        return readings