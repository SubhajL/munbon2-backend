"""Weather Integration Service client for weather data"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, date
from pydantic import BaseModel
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class WeatherData(BaseModel):
    """Current weather data"""
    location: str
    timestamp: datetime
    temperature: float  # Celsius
    humidity: float  # Percentage
    wind_speed: float  # m/s
    wind_direction: float  # degrees
    pressure: float  # hPa
    rainfall: float  # mm
    solar_radiation: Optional[float]  # W/m²
    evapotranspiration: Optional[float]  # mm/day


class WeatherForecast(BaseModel):
    """Weather forecast data"""
    location: str
    date: date
    min_temp: float
    max_temp: float
    rainfall_probability: float
    expected_rainfall: float
    wind_speed: float
    evapotranspiration: float
    confidence: float  # 0-1


class RainfallEvent(BaseModel):
    """Rainfall event information"""
    event_id: str
    start_time: datetime
    end_time: Optional[datetime]
    intensity: float  # mm/hour
    total_amount: float  # mm
    affected_zones: List[str]
    status: str  # predicted, ongoing, completed


class WeatherClient(BaseServiceClient):
    """Client for Weather Integration Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        # Get URL from service registry if not provided
        if not base_url:
            from .service_registry import service_registry
            import asyncio
            service_info = asyncio.run(service_registry.discover('weather'))
            base_url = service_info.url if service_info else 'http://localhost:3009'
        
        super().__init__(
            service_name='Weather Service',
            base_url=base_url
        )
    
    async def get_current_weather(self, location: Optional[str] = None) -> WeatherData:
        """Get current weather conditions"""
        try:
            params = {}
            if location:
                params['location'] = location
            
            response = await self.get('/api/v1/weather/current', params=params)
            return WeatherData(**response)
            
        except Exception as e:
            logger.error(f"Failed to get current weather: {e}")
            raise
    
    async def get_forecast(
        self, 
        days: int = 7,
        location: Optional[str] = None
    ) -> List[WeatherForecast]:
        """Get weather forecast"""
        try:
            params = {'days': days}
            if location:
                params['location'] = location
            
            response = await self.get('/api/v1/weather/forecast', params=params)
            
            forecasts = []
            for forecast_data in response.get('forecasts', []):
                forecasts.append(WeatherForecast(**forecast_data))
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Failed to get weather forecast: {e}")
            return []
    
    async def get_rainfall_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None
    ) -> List[RainfallEvent]:
        """Get rainfall events"""
        try:
            params = {}
            if start_date:
                params['start_date'] = start_date.isoformat()
            if end_date:
                params['end_date'] = end_date.isoformat()
            if status:
                params['status'] = status
            
            response = await self.get('/api/v1/weather/rainfall/events', params=params)
            
            events = []
            for event_data in response.get('events', []):
                events.append(RainfallEvent(**event_data))
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get rainfall events: {e}")
            return []
    
    async def get_evapotranspiration_map(self) -> Dict[str, float]:
        """Get ET values by zone"""
        try:
            response = await self.get('/api/v1/weather/evapotranspiration/map')
            return response.get('et_by_zone', {})
            
        except Exception as e:
            logger.error(f"Failed to get ET map: {e}")
            return {}
    
    async def subscribe_rainfall_alerts(self, zones: List[str]) -> bool:
        """Subscribe to rainfall alerts for specific zones"""
        try:
            response = await self.post(
                '/api/v1/weather/alerts/subscribe',
                data={
                    'subscriber': 'gravity-optimizer',
                    'zones': zones,
                    'threshold_mm': 10.0,
                    'callback_url': '/api/v1/gravity-optimizer/rainfall-alert'
                }
            )
            
            return response.get('success', False)
            
        except Exception as e:
            logger.error(f"Failed to subscribe to rainfall alerts: {e}")
            return False
    
    async def get_historical_rainfall(
        self,
        start_date: date,
        end_date: date,
        zone_id: Optional[str] = None
    ) -> Dict:
        """Get historical rainfall data"""
        try:
            params = {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            if zone_id:
                params['zone_id'] = zone_id
            
            response = await self.get('/api/v1/weather/rainfall/historical', params=params)
            return response
            
        except Exception as e:
            logger.error(f"Failed to get historical rainfall: {e}")
            return {}
    
    async def check_irrigation_conditions(self) -> Dict:
        """Check if weather conditions are suitable for irrigation"""
        try:
            response = await self.get('/api/v1/weather/irrigation/conditions')
            
            conditions = response.get('conditions', {})
            if not conditions.get('suitable', True):
                logger.warning(
                    f"Weather conditions not suitable for irrigation: "
                    f"{conditions.get('reason', 'Unknown')}"
                )
            
            return conditions
            
        except Exception as e:
            logger.error(f"Failed to check irrigation conditions: {e}")
            return {'suitable': True, 'reason': 'Weather service unavailable'}