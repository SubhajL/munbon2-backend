"""
Weather Service client for the scheduler.

Integrates with weather service to get historical data and forecasts
for applying weather-based adjustments to irrigation schedules.
"""

from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta
import os

import httpx

from .base_client import BaseClient
from ...core.logger import get_logger


logger = get_logger(__name__)


class WeatherClient(BaseClient):
    """Client for weather service integration"""
    
    def __init__(self):
        base_url = os.getenv("WEATHER_SERVICE_URL", "http://localhost:3004")
        super().__init__(base_url, "weather")
        self.logger = logger
    
    async def get_zone_weather(self, zone_id: str, date: date) -> Dict[str, Any]:
        """
        Get weather data for a specific zone and date.
        
        Returns:
            - rainfall_mm: Total rainfall for the day
            - temperature_max/min: Temperature range
            - temperature_drop_celsius: Drop from previous day
            - humidity_percent: Average humidity
            - wind_speed_kmh: Average wind speed
            - evapotranspiration_mm: ET for the day
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/weather/zone/{zone_id}",
                params={"date": date.isoformat()}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"No weather data for zone {zone_id} on {date}")
                return self._get_default_weather(zone_id, date)
            raise
        except Exception as e:
            logger.error(f"Failed to get weather data: {str(e)}")
            return self._get_default_weather(zone_id, date)
    
    async def get_zone_weather_range(
        self, 
        zone_id: str, 
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get weather data for a date range"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/weather/zone/{zone_id}/range",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get weather range: {str(e)}")
            # Return daily defaults
            days = (end_date - start_date).days + 1
            return [
                self._get_default_weather(zone_id, start_date + timedelta(days=i))
                for i in range(days)
            ]
    
    async def get_weather_forecast(
        self, 
        zone_id: str, 
        days: int = 7
    ) -> Dict[str, Any]:
        """Get weather forecast for a zone"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/weather/forecast/{zone_id}",
                params={"days": days}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get weather forecast: {str(e)}")
            return {
                "zone_id": zone_id,
                "forecast_days": days,
                "forecast": self._get_default_forecast(days)
            }
    
    async def get_extreme_weather_alerts(
        self,
        zone_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get active extreme weather alerts"""
        try:
            params = {}
            if zone_ids:
                params["zone_ids"] = ",".join(zone_ids)
            
            response = await self.client.get(
                f"{self.base_url}/api/v1/weather/alerts",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get weather alerts: {str(e)}")
            return []
    
    async def get_historical_averages(
        self,
        zone_id: str,
        month: int,
        metric: str = "all"
    ) -> Dict[str, Any]:
        """Get historical weather averages for planning"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/weather/historical/{zone_id}",
                params={"month": month, "metric": metric}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get historical averages: {str(e)}")
            return self._get_default_historical(zone_id, month)
    
    def _get_default_weather(self, zone_id: str, date: date) -> Dict[str, Any]:
        """Get default weather data for development/testing"""
        # Simulate some variability based on date
        day_of_year = date.timetuple().tm_yday
        
        # Simple seasonal simulation
        if 150 <= day_of_year <= 270:  # Rainy season (May-Sept)
            rainfall_base = 8.0
            temp_max = 32.0
            humidity = 80.0
        else:  # Dry season
            rainfall_base = 1.0
            temp_max = 35.0
            humidity = 60.0
        
        # Add some randomness based on day
        rainfall = max(0, rainfall_base + (day_of_year % 10 - 5) * 2)
        
        return {
            "zone_id": zone_id,
            "date": date.isoformat(),
            "rainfall_mm": rainfall,
            "temperature_max": temp_max,
            "temperature_min": temp_max - 7,
            "temperature_drop_celsius": 1.5 if rainfall > 10 else 0.5,
            "humidity_percent": humidity,
            "wind_speed_kmh": 10 + (day_of_year % 5) * 3,
            "evapotranspiration_mm": 4.5 - (rainfall * 0.1),
            "sunshine_hours": 8 - (rainfall * 0.2),
            "is_default": True
        }
    
    def _get_default_forecast(self, days: int) -> List[Dict[str, Any]]:
        """Get default forecast for development"""
        forecast = []
        base_date = datetime.now().date()
        
        for i in range(days):
            forecast_date = base_date + timedelta(days=i+1)
            # Decrease rain probability over time
            rain_chance = max(10, 50 - i * 5)
            
            forecast.append({
                "date": forecast_date.isoformat(),
                "rain_probability_percent": rain_chance,
                "expected_rainfall_mm": rain_chance * 0.3,
                "temperature_max": 33 + i * 0.2,
                "temperature_min": 26 + i * 0.1,
                "wind_speed_kmh": 12 + i,
                "confidence": max(50, 90 - i * 10)
            })
        
        return forecast
    
    def _get_default_historical(self, zone_id: str, month: int) -> Dict[str, Any]:
        """Get default historical data"""
        # Thai seasonal patterns
        seasonal_data = {
            # Hot season (Mar-May)
            3: {"rain": 30, "temp": 35, "et": 5.5},
            4: {"rain": 50, "temp": 36, "et": 6.0},
            5: {"rain": 120, "temp": 34, "et": 5.0},
            # Rainy season (Jun-Oct)
            6: {"rain": 150, "temp": 32, "et": 4.5},
            7: {"rain": 160, "temp": 31, "et": 4.2},
            8: {"rain": 180, "temp": 31, "et": 4.0},
            9: {"rain": 200, "temp": 31, "et": 4.2},
            10: {"rain": 150, "temp": 31, "et": 4.5},
            # Cool season (Nov-Feb)
            11: {"rain": 40, "temp": 30, "et": 4.0},
            12: {"rain": 10, "temp": 28, "et": 3.5},
            1: {"rain": 8, "temp": 28, "et": 3.5},
            2: {"rain": 15, "temp": 30, "et": 4.0},
        }
        
        data = seasonal_data.get(month, {"rain": 50, "temp": 32, "et": 4.5})
        
        return {
            "zone_id": zone_id,
            "month": month,
            "average_rainfall_mm": data["rain"],
            "average_temperature": data["temp"],
            "average_et_mm": data["et"],
            "rainy_days": data["rain"] / 10,
            "years_of_data": 10,
            "is_default": True
        }