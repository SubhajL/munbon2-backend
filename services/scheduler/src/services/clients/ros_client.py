from typing import List, Dict, Any, Optional
from datetime import date

from .base_client import BaseServiceClient
from ...core.config import settings
from ...core.logger import get_logger

logger = get_logger(__name__)


class ROSClient(BaseServiceClient):
    """Client for ROS (Reservoir Operation System) Service"""
    
    def __init__(self):
        super().__init__(settings.ros_service_url, "ROS")
    
    async def get_current_week_demand(
        self,
        week: Optional[int] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get water demand for all active plots in the current week"""
        params = {}
        if week:
            params["week"] = week
        if year:
            params["year"] = year
        
        response = await self.get("/api/v1/ros/plot-demand/plots/current-week", params)
        return response.get("data", {})
    
    async def get_zone_plots(self, zone_id: str) -> List[Dict[str, Any]]:
        """Get all plots within a zone"""
        response = await self.get(f"/api/v1/ros/plot-demand/plots/by-area/zone/{zone_id}")
        return response.get("data", [])
    
    async def get_section_plots(self, section_id: str) -> List[Dict[str, Any]]:
        """Get all plots within a section"""
        response = await self.get(f"/api/v1/ros/plot-demand/plots/by-area/section/{section_id}")
        return response.get("data", [])
    
    async def calculate_plot_demand(
        self,
        plot_id: str,
        crop_type: str,
        planting_date: str,
        include_rainfall: bool = True,
        include_land_preparation: bool = True
    ) -> Dict[str, Any]:
        """Calculate seasonal water demand for a plot"""
        data = {
            "cropType": crop_type,
            "plantingDate": planting_date,
            "includeRainfall": include_rainfall,
            "includeLandPreparation": include_land_preparation,
        }
        
        response = await self.post(f"/api/v1/ros/plot-demand/plot/{plot_id}/calculate", data)
        return response.get("data", {})
    
    async def calculate_zone_demand(
        self,
        zone_id: str,
        crop_type: str,
        planting_date: str,
        include_rainfall: bool = True,
        include_land_preparation: bool = True
    ) -> Dict[str, Any]:
        """Calculate total water demand for all plots in a zone"""
        data = {
            "cropType": crop_type,
            "plantingDate": planting_date,
            "includeRainfall": include_rainfall,
            "includeLandPreparation": include_land_preparation,
        }
        
        response = await self.post(f"/api/v1/ros/plot-demand/zone/{zone_id}/calculate", data)
        return response.get("data", {})
    
    async def get_area_hierarchy(self, area_id: str) -> Dict[str, Any]:
        """Get area hierarchy (zones and sections)"""
        response = await self.get(f"/api/v1/ros/areas/hierarchy/{area_id}")
        return response.get("data", {})
    
    async def get_weekly_effective_rainfall(
        self,
        area_id: str,
        week_start_date: str
    ) -> Dict[str, Any]:
        """Get weekly effective rainfall for an area"""
        params = {"weekStartDate": week_start_date}
        response = await self.get(f"/api/v1/ros/rainfall/weekly/{area_id}", params)
        return response.get("data", {})
    
    async def get_water_level(self, area_id: str) -> Dict[str, Any]:
        """Get current water level for an area"""
        response = await self.get(f"/api/v1/ros/water-level/current/{area_id}")
        return response.get("data", {})