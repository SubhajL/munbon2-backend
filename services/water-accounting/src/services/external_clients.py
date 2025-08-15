"""External service client implementations"""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from ..config import get_settings

logger = logging.getLogger(__name__)

class ExternalServiceError(Exception):
    """Base exception for external service errors"""
    pass

class BaseServiceClient:
    """Base class for external service clients"""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request to service"""
        try:
            response = await self.client.get(
                f"{self.base_url}{endpoint}",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from {self.base_url}: {e}")
            raise ExternalServiceError(f"Service error: {e}")
        except Exception as e:
            logger.error(f"Error calling {self.base_url}: {e}")
            raise ExternalServiceError(f"Service unavailable: {e}")
    
    async def _post(self, endpoint: str, data: Dict) -> Dict:
        """Make POST request to service"""
        try:
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from {self.base_url}: {e}")
            raise ExternalServiceError(f"Service error: {e}")
        except Exception as e:
            logger.error(f"Error calling {self.base_url}: {e}")
            raise ExternalServiceError(f"Service unavailable: {e}")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

class SensorDataClient(BaseServiceClient):
    """Client for Sensor Data Service"""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(settings.SENSOR_DATA_SERVICE_URL)
    
    async def get_flow_readings(
        self,
        gate_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """Get flow readings for a gate over time period"""
        try:
            response = await self._get(
                f"/api/v1/flow/{gate_id}",
                params={
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                }
            )
            
            # Transform to expected format
            readings = []
            for reading in response.get("readings", []):
                readings.append({
                    "timestamp": reading["timestamp"],
                    "flow_rate_m3s": reading["flow_rate"],
                    "gate_id": gate_id,
                    "quality": reading.get("quality", 1.0)
                })
            
            return readings
            
        except ExternalServiceError:
            # Return empty list if service unavailable
            logger.warning(f"Could not fetch flow readings for gate {gate_id}")
            return []
    
    async def get_gate_status(self, gate_id: str) -> Dict:
        """Get current gate status"""
        try:
            return await self._get(f"/api/v1/gates/{gate_id}/status")
        except ExternalServiceError:
            return {
                "gate_id": gate_id,
                "status": "unknown",
                "opening_percentage": 0
            }

class GISServiceClient(BaseServiceClient):
    """Client for GIS Service"""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(settings.GIS_SERVICE_URL)
    
    async def get_section_details(self, section_id: str) -> Dict:
        """Get section geographic and infrastructure details"""
        try:
            response = await self._get(f"/api/v1/sections/{section_id}")
            
            return {
                "section_id": section_id,
                "area_hectares": response.get("area_hectares", 0),
                "canal_length_km": response.get("canal_length_km", 0),
                "canal_type": response.get("canal_type", "earthen"),
                "soil_type": response.get("soil_type", "clay"),
                "location": response.get("centroid", {}),
                "elevation_m": response.get("average_elevation", 0)
            }
            
        except ExternalServiceError:
            # Return defaults if service unavailable
            logger.warning(f"Could not fetch section details for {section_id}")
            return {
                "section_id": section_id,
                "area_hectares": 100,  # Default
                "canal_length_km": 2.0,  # Default
                "canal_type": "earthen",
                "soil_type": "clay",
                "location": {},
                "elevation_m": 0
            }
    
    async def update_deficit_status(
        self,
        section_id: str,
        deficit_data: Dict
    ) -> bool:
        """Update section deficit status for spatial analysis"""
        try:
            await self._post(
                f"/api/v1/sections/{section_id}/deficit",
                deficit_data
            )
            return True
        except ExternalServiceError:
            logger.error(f"Failed to update deficit status for {section_id}")
            return False

class WeatherServiceClient(BaseServiceClient):
    """Client for Weather Service"""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(settings.WEATHER_SERVICE_URL)
    
    async def get_environmental_conditions(
        self,
        location: Dict,
        time: datetime
    ) -> Dict:
        """Get weather conditions at location and time"""
        try:
            response = await self._get(
                "/api/v1/conditions",
                params={
                    "lat": location.get("lat", 0),
                    "lon": location.get("lon", 0),
                    "time": time.isoformat()
                }
            )
            
            return {
                "temperature_c": response.get("temperature", 30),
                "humidity_percent": response.get("humidity", 60),
                "wind_speed_ms": response.get("wind_speed", 2),
                "solar_radiation_wm2": response.get("solar_radiation", 250),
                "rainfall_mm": response.get("rainfall", 0)
            }
            
        except ExternalServiceError:
            # Return typical conditions if service unavailable
            logger.warning("Weather service unavailable, using defaults")
            return {
                "temperature_c": 30,
                "humidity_percent": 60,
                "wind_speed_ms": 2,
                "solar_radiation_wm2": 250,
                "rainfall_mm": 0
            }
    
    async def get_evapotranspiration_rate(
        self,
        location: Dict,
        date: datetime
    ) -> float:
        """Get reference evapotranspiration rate"""
        try:
            response = await self._get(
                "/api/v1/eto",
                params={
                    "lat": location.get("lat", 0),
                    "lon": location.get("lon", 0),
                    "date": date.isoformat()
                }
            )
            return response.get("eto_mm_day", 5.0)  # Default 5mm/day
            
        except ExternalServiceError:
            return 5.0  # Default ETo

class SCADAServiceClient(BaseServiceClient):
    """Client for SCADA Service"""
    
    def __init__(self):
        settings = get_settings()
        super().__init__(settings.SCADA_SERVICE_URL)
    
    async def get_gate_operational_data(
        self,
        gate_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """Get gate operational data including losses"""
        try:
            response = await self._get(
                f"/api/v1/gates/{gate_id}/operations",
                params={
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                }
            )
            
            return {
                "gate_id": gate_id,
                "total_operations": response.get("operation_count", 0),
                "avg_opening_percent": response.get("avg_opening", 0),
                "leakage_loss_m3": response.get("estimated_leakage", 0),
                "spillage_loss_m3": response.get("estimated_spillage", 0),
                "operational_efficiency": response.get("efficiency", 0.95)
            }
            
        except ExternalServiceError:
            # Return minimal losses if service unavailable
            logger.warning(f"SCADA service unavailable for gate {gate_id}")
            return {
                "gate_id": gate_id,
                "total_operations": 1,
                "avg_opening_percent": 100,
                "leakage_loss_m3": 0,
                "spillage_loss_m3": 0,
                "operational_efficiency": 0.95
            }
    
    async def get_automated_gates_list(self) -> List[str]:
        """Get list of automated gates with continuous monitoring"""
        try:
            response = await self._get("/api/v1/gates/automated")
            return response.get("gate_ids", [])
        except ExternalServiceError:
            # Return known automated gates
            return [f"GATE-{i:03d}" for i in range(1, 21)]  # 20 automated gates

class ServiceClientManager:
    """Manager for all external service clients"""
    
    def __init__(self):
        self.sensor_client = SensorDataClient()
        self.gis_client = GISServiceClient()
        self.weather_client = WeatherServiceClient()
        self.scada_client = SCADAServiceClient()
    
    async def close_all(self):
        """Close all client connections"""
        await self.sensor_client.close()
        await self.gis_client.close()
        await self.weather_client.close()
        await self.scada_client.close()
    
    async def fetch_delivery_data(
        self,
        delivery_id: str,
        section_id: str,
        gate_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """Fetch all required data for delivery completion"""
        
        # Fetch data from all services in parallel
        import asyncio
        
        tasks = [
            self.sensor_client.get_flow_readings(gate_id, start_time, end_time),
            self.gis_client.get_section_details(section_id),
            self.scada_client.get_gate_operational_data(gate_id, start_time, end_time)
        ]
        
        flow_readings, section_details, gate_data = await asyncio.gather(*tasks)
        
        # Get weather conditions at section location
        weather_conditions = await self.weather_client.get_environmental_conditions(
            section_details.get("location", {}),
            start_time
        )
        
        return {
            "delivery_id": delivery_id,
            "section_id": section_id,
            "gate_id": gate_id,
            "flow_readings": flow_readings,
            "canal_characteristics": {
                "length_km": section_details["canal_length_km"],
                "type": section_details["canal_type"],
                "soil_type": section_details["soil_type"]
            },
            "environmental_conditions": weather_conditions,
            "operational_losses": {
                "leakage_m3": gate_data["leakage_loss_m3"],
                "spillage_m3": gate_data["spillage_loss_m3"]
            }
        }