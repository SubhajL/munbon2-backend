"""Sensor Data Service client for real-time sensor readings"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class SensorReading(BaseModel):
    """Generic sensor reading"""
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    timestamp: datetime
    quality: str  # good, uncertain, bad
    location: Optional[Dict] = None  # lat, lon


class WaterLevelReading(BaseModel):
    """Water level sensor reading"""
    sensor_id: str
    channel_id: Optional[str]
    water_level: float  # meters
    reference_elevation: float  # meters
    timestamp: datetime
    battery_level: Optional[float]
    signal_strength: Optional[float]


class FlowMeterReading(BaseModel):
    """Flow meter reading"""
    sensor_id: str
    location_id: str
    flow_rate: float  # m³/s
    total_volume: float  # m³
    velocity: Optional[float]  # m/s
    timestamp: datetime


class GateSensor(BaseModel):
    """Gate position sensor"""
    gate_id: str
    opening_percentage: float
    upstream_level: Optional[float]
    downstream_level: Optional[float]
    vibration: Optional[float]
    timestamp: datetime


class SensorDataClient(BaseServiceClient):
    """Client for Sensor Data Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        # Get URL from service registry if not provided
        if not base_url:
            from .service_registry import service_registry
            import asyncio
            service_info = asyncio.run(service_registry.discover('sensor-data'))
            base_url = service_info.url if service_info else 'http://localhost:3003'
        
        super().__init__(
            service_name='Sensor Data Service',
            base_url=base_url,
            timeout=15.0
        )
    
    async def get_latest_reading(
        self, 
        sensor_id: str
    ) -> Optional[SensorReading]:
        """Get latest reading from a sensor"""
        try:
            response = await self.get(f'/api/v1/sensors/{sensor_id}/latest')
            return SensorReading(**response)
            
        except Exception as e:
            logger.error(f"Failed to get latest reading for sensor {sensor_id}: {e}")
            return None
    
    async def get_water_levels(
        self,
        channel_ids: Optional[List[str]] = None
    ) -> List[WaterLevelReading]:
        """Get current water levels"""
        try:
            params = {}
            if channel_ids:
                params['channels'] = ','.join(channel_ids)
            
            response = await self.get('/api/v1/sensors/water-levels/current', params=params)
            
            readings = []
            for reading_data in response.get('readings', []):
                readings.append(WaterLevelReading(**reading_data))
            
            return readings
            
        except Exception as e:
            logger.error(f"Failed to get water levels: {e}")
            return []
    
    async def get_flow_rates(
        self,
        location_ids: Optional[List[str]] = None
    ) -> List[FlowMeterReading]:
        """Get current flow rates"""
        try:
            params = {}
            if location_ids:
                params['locations'] = ','.join(location_ids)
            
            response = await self.get('/api/v1/sensors/flow-meters/current', params=params)
            
            readings = []
            for reading_data in response.get('readings', []):
                readings.append(FlowMeterReading(**reading_data))
            
            return readings
            
        except Exception as e:
            logger.error(f"Failed to get flow rates: {e}")
            return []
    
    async def get_gate_sensors(
        self,
        gate_ids: Optional[List[str]] = None
    ) -> List[GateSensor]:
        """Get gate sensor readings"""
        try:
            params = {}
            if gate_ids:
                params['gates'] = ','.join(gate_ids)
            
            response = await self.get('/api/v1/sensors/gates/current', params=params)
            
            readings = []
            for reading_data in response.get('readings', []):
                readings.append(GateSensor(**reading_data))
            
            return readings
            
        except Exception as e:
            logger.error(f"Failed to get gate sensors: {e}")
            return []
    
    async def get_sensor_history(
        self,
        sensor_id: str,
        start_time: datetime,
        end_time: datetime,
        interval: Optional[str] = None  # e.g., '5m', '1h'
    ) -> List[SensorReading]:
        """Get historical sensor data"""
        try:
            params = {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            }
            if interval:
                params['interval'] = interval
            
            response = await self.get(
                f'/api/v1/sensors/{sensor_id}/history',
                params=params
            )
            
            readings = []
            for reading_data in response.get('data', []):
                readings.append(SensorReading(**reading_data))
            
            return readings
            
        except Exception as e:
            logger.error(f"Failed to get sensor history: {e}")
            return []
    
    async def get_anomalies(
        self,
        sensor_types: Optional[List[str]] = None,
        severity: Optional[str] = None
    ) -> List[Dict]:
        """Get detected sensor anomalies"""
        try:
            params = {}
            if sensor_types:
                params['types'] = ','.join(sensor_types)
            if severity:
                params['severity'] = severity
            
            response = await self.get('/api/v1/sensors/anomalies/active', params=params)
            return response.get('anomalies', [])
            
        except Exception as e:
            logger.error(f"Failed to get anomalies: {e}")
            return []
    
    async def validate_reading(
        self,
        sensor_id: str,
        value: float,
        timestamp: datetime
    ) -> bool:
        """Validate a sensor reading against expected ranges"""
        try:
            response = await self.post(
                '/api/v1/sensors/validate',
                data={
                    'sensor_id': sensor_id,
                    'value': value,
                    'timestamp': timestamp.isoformat()
                }
            )
            
            return response.get('valid', False)
            
        except Exception as e:
            logger.error(f"Failed to validate reading: {e}")
            return True  # Assume valid if validation service fails
    
    async def get_sensor_status(self) -> Dict[str, Dict]:
        """Get overall sensor network status"""
        try:
            response = await self.get('/api/v1/sensors/network/status')
            return response.get('sensors', {})
            
        except Exception as e:
            logger.error(f"Failed to get sensor status: {e}")
            return {}
    
    async def subscribe_sensor_updates(
        self,
        sensor_ids: List[str],
        callback_url: str
    ) -> bool:
        """Subscribe to real-time sensor updates"""
        try:
            response = await self.post(
                '/api/v1/sensors/subscribe',
                data={
                    'subscriber': 'gravity-optimizer',
                    'sensor_ids': sensor_ids,
                    'callback_url': callback_url,
                    'filters': {
                        'min_change': 0.1,  # Minimum change to trigger update
                        'max_interval': 300  # Max seconds between updates
                    }
                }
            )
            
            return response.get('success', False)
            
        except Exception as e:
            logger.error(f"Failed to subscribe to sensor updates: {e}")
            return False