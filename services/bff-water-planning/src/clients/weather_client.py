"""
Weather Service Client
Handles communication with the weather service
"""

from typing import Dict, List, Optional
import httpx
from datetime import datetime
from core import get_logger
from config import settings

logger = get_logger(__name__)


class WeatherClient:
    """Client for interacting with Weather service"""
    
    def __init__(self):
        # Use mock server URL if enabled, otherwise use actual weather service URL
        if settings.use_mock_server:
            self.base_url = f"{settings.mock_server_url}/weather"
        else:
            # Use a default weather service URL if not configured
            self.base_url = getattr(settings, 'weather_service_url', 'http://localhost:3006')
        self.logger = logger.bind(client="weather")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
    
    async def get_current_weather(
        self, 
        location: str = "munbon",
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> Optional[Dict]:
        """Get current weather conditions"""
        try:
            params = {"location": location}
            if lat is not None:
                params["lat"] = lat
            if lon is not None:
                params["lon"] = lon
                
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/weather/current",
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to get current weather", 
                            location=location, error=str(e))
            return None
    
    async def get_weather_forecast(
        self, 
        location: str = "munbon",
        days: int = 7
    ) -> Optional[Dict]:
        """Get weather forecast"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/weather/forecast",
                    params={
                        "location": location,
                        "days": days
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to get weather forecast", 
                            location=location, error=str(e))
            return None
    
    async def get_historical_weather(
        self,
        location: str,
        start_date: str,
        end_date: str
    ) -> Optional[Dict]:
        """Get historical weather data"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/weather/historical",
                    params={
                        "location": location,
                        "start_date": start_date,
                        "end_date": end_date
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to get historical weather", 
                            location=location, error=str(e))
            return None
    
    async def calculate_et0(
        self,
        temperature: float,
        humidity: float,
        wind_speed: float,
        solar_radiation: float,
        latitude: Optional[float] = None,
        elevation: Optional[float] = None
    ) -> Optional[Dict]:
        """Calculate ET0 using weather parameters"""
        try:
            params = {
                "temperature": temperature,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "solar_radiation": solar_radiation
            }
            if latitude is not None:
                params["latitude"] = latitude
            if elevation is not None:
                params["elevation"] = elevation
                
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/weather/et0/calculate",
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to calculate ET0", error=str(e))
            return None
    
    async def get_weather_alerts(self, location: str = "munbon") -> Optional[List[Dict]]:
        """Get active weather alerts"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/weather/alerts",
                    params={"location": location}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("alerts", [])
        except httpx.HTTPError as e:
            self.logger.error("Failed to get weather alerts", 
                            location=location, error=str(e))
            return None
    
    async def get_weather_stations(self) -> Optional[List[Dict]]:
        """Get available weather stations"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/v1/weather/stations")
                response.raise_for_status()
                data = response.json()
                return data.get("stations", [])
        except httpx.HTTPError as e:
            self.logger.error("Failed to get weather stations", error=str(e))
            return None