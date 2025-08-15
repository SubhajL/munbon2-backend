"""
GIS Service Client
Handles communication with the GIS service for spatial data
"""

from typing import Dict, List, Optional
import httpx
import json
import structlog

from config import settings
from core import get_logger

logger = get_logger(__name__)


class GISClient:
    """Client for interacting with GIS service"""
    
    def __init__(self):
        self.base_url = settings.gis_service_url
        self.logger = logger.bind(client="gis")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._use_mock = settings.use_mock_server
    
    async def get_parcels(
        self, 
        zone_id: Optional[str] = None,
        include_geometry: bool = False,
        limit: int = 100
    ) -> List[Dict]:
        """Get parcels/sections from GIS service"""
        if self._use_mock:
            return self._mock_parcels(zone_id)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                params = {
                    "limit": limit,
                    "includeGeometry": include_geometry
                }
                if zone_id:
                    params["zoneId"] = zone_id
                
                response = await client.get(
                    f"{self.base_url}/api/v1/parcels",
                    params=params
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data", [])
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to get parcels", error=str(e))
                return []
    
    async def get_parcel_by_id(self, parcel_id: str) -> Optional[Dict]:
        """Get specific parcel details"""
        if self._use_mock:
            return self._mock_parcel_detail(parcel_id)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/parcels/{parcel_id}"
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data")
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to get parcel", parcel_id=parcel_id, error=str(e))
                return None
    
    async def query_parcels_by_location(
        self,
        lat: float,
        lon: float,
        radius_km: float = 5.0
    ) -> List[Dict]:
        """Query parcels near a location"""
        if self._use_mock:
            return self._mock_parcels_near_location(lat, lon, radius_km)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/spatial/query",
                    json={
                        "type": "near",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        },
                        "distance": radius_km * 1000,  # Convert to meters
                        "unit": "meters"
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data", [])
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to query parcels", error=str(e))
                return []
    
    async def get_zone_parcels(self, zone_id: int) -> List[Dict]:
        """Get all parcels in a specific zone"""
        if self._use_mock:
            return self._mock_zone_parcels(zone_id)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/zones/{zone_id}/parcels"
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data", [])
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to get zone parcels", zone_id=zone_id, error=str(e))
                return []
    
    # Mock methods for development
    def _mock_parcels(self, zone_id: Optional[str] = None) -> List[Dict]:
        """Mock parcel list"""
        parcels = []
        zones = [2, 3, 5, 6] if not zone_id else [int(zone_id)]
        
        for zone in zones:
            for letter in ["A", "B", "C", "D"]:
                parcel_id = f"Zone_{zone}_Section_{letter}"
                parcels.append({
                    "id": parcel_id,
                    "plotCode": parcel_id,
                    "zoneId": zone,
                    "areaHa": 150 + (zone * 10),
                    "areaRai": (150 + (zone * 10)) * 6.25,
                    "farmerId": f"farmer_{zone}{letter}",
                    "landUseType": "rice" if zone in [2, 3] else "sugarcane",
                    "irrigationMethod": "flooding",
                    "status": "active",
                    "elevationM": 220 - (zone * 0.5)
                })
        
        return parcels
    
    def _mock_parcel_detail(self, parcel_id: str) -> Dict:
        """Mock parcel detail"""
        zone = int(parcel_id.split("_")[1]) if "_" in parcel_id else 1
        letter = parcel_id.split("_")[-1] if "_" in parcel_id else "A"
        
        return {
            "id": parcel_id,
            "plotCode": parcel_id,
            "zoneId": zone,
            "areaHa": 150 + (zone * 10),
            "areaRai": (150 + (zone * 10)) * 6.25,
            "farmerId": f"farmer_{zone}{letter}",
            "landUseType": "rice" if zone in [2, 3] else "sugarcane",
            "irrigationMethod": "flooding",
            "status": "active",
            "elevationM": 220 - (zone * 0.5),
            "soilType": "clay_loam",
            "lastPlantingDate": "2024-01-01T00:00:00Z",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[103.15, 14.82], [103.16, 14.82], [103.16, 14.83], [103.15, 14.83], [103.15, 14.82]]]
            },
            "centroid": {
                "type": "Point",
                "coordinates": [103.155, 14.825]
            }
        }
    
    def _mock_parcels_near_location(self, lat: float, lon: float, radius_km: float) -> List[Dict]:
        """Mock parcels near a location"""
        # Simple mock - return parcels in zones 2 and 3
        parcels = []
        for zone in [2, 3]:
            for letter in ["A", "B"]:
                parcel_id = f"Zone_{zone}_Section_{letter}"
                parcels.append({
                    "id": parcel_id,
                    "plotCode": parcel_id,
                    "zoneId": zone,
                    "areaRai": (150 + (zone * 10)) * 6.25,
                    "distance_km": radius_km / 2,  # Mock distance
                    "landUseType": "rice"
                })
        return parcels
    
    def _mock_zone_parcels(self, zone_id: int) -> List[Dict]:
        """Mock parcels in a zone"""
        parcels = []
        for letter in ["A", "B", "C", "D"]:
            parcel_id = f"Zone_{zone_id}_Section_{letter}"
            parcels.append({
                "id": parcel_id,
                "plotCode": parcel_id,
                "zoneId": zone_id,
                "areaHa": 150 + (zone_id * 10),
                "areaRai": (150 + (zone_id * 10)) * 6.25,
                "farmerId": f"farmer_{zone_id}{letter}",
                "landUseType": "rice" if zone_id in [2, 3] else "sugarcane",
                "irrigationMethod": "flooding",
                "status": "active"
            })
        return parcels