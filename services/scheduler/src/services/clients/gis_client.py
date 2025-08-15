from typing import List, Dict, Any, Optional

from .base_client import BaseServiceClient
from ...core.config import settings
from ...core.logger import get_logger

logger = get_logger(__name__)


class GISClient(BaseServiceClient):
    """Client for GIS Data Service"""
    
    def __init__(self):
        super().__init__(settings.gis_service_url, "GIS")
    
    async def get_zones(self) -> List[Dict[str, Any]]:
        """Get all zones"""
        response = await self.get("/api/v1/zones")
        return response.get("data", [])
    
    async def get_zone(self, zone_id: str) -> Dict[str, Any]:
        """Get zone details"""
        response = await self.get(f"/api/v1/zones/{zone_id}")
        return response.get("data", {})
    
    async def get_zone_parcels(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all parcels in a zone"""
        response = await self.get(f"/api/v1/zones/{zone_id}/parcels")
        return response.get("data", [])
    
    async def get_canals(self) -> List[Dict[str, Any]]:
        """Get all canals"""
        response = await self.get("/api/v1/canals")
        return response.get("data", [])
    
    async def get_canal(self, canal_id: str) -> Dict[str, Any]:
        """Get canal details"""
        response = await self.get(f"/api/v1/canals/{canal_id}")
        return response.get("data", {})
    
    async def get_canal_network_topology(self) -> Dict[str, Any]:
        """Get canal network topology"""
        response = await self.get("/api/v1/canals/network/topology")
        return response.get("data", {})
    
    async def query_by_bounds(
        self,
        table_name: str,
        bounds: List[float],
        properties: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Query features within bounds"""
        data = {
            "tableName": table_name,
            "bounds": bounds,
        }
        if properties:
            data["properties"] = properties
        
        response = await self.post("/api/v1/spatial/query/bounds", data)
        return response.get("data", [])
    
    async def query_by_distance(
        self,
        table_name: str,
        center: List[float],
        radius_meters: float,
        properties: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Query features within distance"""
        data = {
            "tableName": table_name,
            "center": center,
            "radius": radius_meters,
        }
        if properties:
            data["properties"] = properties
        
        response = await self.post("/api/v1/spatial/query/distance", data)
        return response.get("data", [])
    
    async def calculate_area(self, geometry: Dict[str, Any]) -> float:
        """Calculate area of geometry in square meters"""
        response = await self.post("/api/v1/spatial/area", {"geometry": geometry})
        return response.get("data", {}).get("area", 0.0)
    
    async def get_gates_in_zone(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all gates in a zone"""
        # Query gates within zone bounds
        zone = await self.get_zone(zone_id)
        if zone and zone.get("geometry"):
            # Extract bounds from zone geometry
            # This is a simplified approach - actual implementation would
            # properly calculate bounds from the polygon
            return await self.query_by_bounds("gates", zone["bounds"])
        return []