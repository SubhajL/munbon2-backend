"""
Client for GIS service integration
"""

from typing import Dict, List, Optional, Any, Tuple
from .base_client import BaseServiceClient
import logging

logger = logging.getLogger(__name__)


class GISClient(BaseServiceClient):
    """Client for interacting with GIS service for spatial operations"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url, "GIS Service")
    
    async def get_section_details(self, section_id: str) -> Dict[str, Any]:
        """Get section spatial and attribute details"""
        try:
            endpoint = f"/api/v1/sections/{section_id}"
            
            response = await self.get(endpoint)
            
            return {
                "section_id": section_id,
                "zone": response.get("zone", 0),
                "area_hectares": response.get("area_hectares", 0),
                "area_rai": response.get("area_rai", 0),
                "crop_type": response.get("crop_type", "rice"),
                "soil_type": response.get("soil_type", "clay"),
                "elevation_m": response.get("elevation_m", 0),
                "delivery_gate": response.get("delivery_gate"),
                "geometry": response.get("geometry"),
                "centroid": response.get("centroid", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get section details for {section_id}: {str(e)}")
            raise
    
    async def get_sections_by_gate(self, gate_id: str) -> List[Dict[str, Any]]:
        """Get all sections served by a specific gate"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/sections"
            
            response = await self.get(endpoint)
            
            return response.get("sections", [])
            
        except Exception as e:
            logger.error(f"Failed to get sections for gate {gate_id}: {str(e)}")
            raise
    
    async def get_sections_in_zone(self, zone: int) -> List[Dict[str, Any]]:
        """Get all sections within a zone"""
        try:
            endpoint = f"/api/v1/zones/{zone}/sections"
            
            response = await self.get(endpoint)
            
            return response.get("sections", [])
            
        except Exception as e:
            logger.error(f"Failed to get sections for zone {zone}: {str(e)}")
            raise
    
    async def calculate_travel_distance(
        self,
        from_gate: str,
        to_gate: str
    ) -> Dict[str, Any]:
        """Calculate travel distance between gates"""
        try:
            endpoint = "/api/v1/routing/distance"
            params = {
                "from": from_gate,
                "to": to_gate
            }
            
            response = await self.get(endpoint, params=params)
            
            return {
                "from_gate": from_gate,
                "to_gate": to_gate,
                "distance_km": response.get("distance_km", 0),
                "travel_time_hours": response.get("travel_time_hours", 0),
                "path": response.get("path", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate distance: {str(e)}")
            raise
    
    async def get_gate_network_topology(self, zone: Optional[int] = None) -> Dict[str, Any]:
        """Get gate network topology for hydraulic routing"""
        try:
            endpoint = "/api/v1/network/topology"
            params = {"zone": zone} if zone is not None else {}
            
            response = await self.get(endpoint, params=params)
            
            return {
                "nodes": response.get("nodes", []),  # Gates and junctions
                "edges": response.get("edges", []),  # Canals
                "hierarchy": response.get("hierarchy", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get network topology: {str(e)}")
            raise
    
    async def get_elevation_profile(
        self,
        gate_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get elevation profile for a list of gates"""
        try:
            endpoint = "/api/v1/elevation/profile"
            data = {"gate_ids": gate_ids}
            
            response = await self.post(endpoint, data)
            
            return response.get("elevations", [])
            
        except Exception as e:
            logger.error(f"Failed to get elevation profile: {str(e)}")
            raise
    
    async def find_downstream_gates(
        self,
        gate_id: str,
        max_distance_km: Optional[float] = None
    ) -> List[str]:
        """Find all downstream gates from a given gate"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/downstream"
            params = {"max_distance_km": max_distance_km} if max_distance_km else {}
            
            response = await self.get(endpoint, params=params)
            
            return response.get("downstream_gates", [])
            
        except Exception as e:
            logger.error(f"Failed to find downstream gates: {str(e)}")
            raise
    
    async def get_section_neighbors(
        self,
        section_id: str
    ) -> List[str]:
        """Get neighboring sections for water sharing analysis"""
        try:
            endpoint = f"/api/v1/sections/{section_id}/neighbors"
            
            response = await self.get(endpoint)
            
            return response.get("neighbors", [])
            
        except Exception as e:
            logger.error(f"Failed to get section neighbors: {str(e)}")
            raise
    
    async def calculate_service_area(
        self,
        gate_id: str
    ) -> Dict[str, Any]:
        """Calculate total service area for a gate"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/service-area"
            
            response = await self.get(endpoint)
            
            return {
                "gate_id": gate_id,
                "total_area_hectares": response.get("total_area_hectares", 0),
                "section_count": response.get("section_count", 0),
                "crop_distribution": response.get("crop_distribution", {}),
                "elevation_range": response.get("elevation_range", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate service area: {str(e)}")
            raise