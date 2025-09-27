"""
Client for ROS (River Operation System) service integration
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from .base_client import BaseServiceClient
import logging

logger = logging.getLogger(__name__)


class ROSClient(BaseServiceClient):
    """Client for interacting with ROS water demand calculation service"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url, "ROS Service")
    
    async def get_water_demand(
        self,
        area_id: str,
        area_type: str,
        week: int,
        year: int
    ) -> Dict[str, Any]:
        """Get water demand calculation for a specific area and week"""
        try:
            endpoint = f"/api/v1/water-demand/{area_type}/{area_id}"
            params = {"week": week, "year": year}
            
            response = await self.get(endpoint, params=params)
            
            return {
                "area_id": area_id,
                "area_type": area_type,
                "week": week,
                "year": year,
                "demand_m3": response.get("net_demand_m3", 0),
                "eto_mm": response.get("eto_mm", 0),
                "kc": response.get("kc", 1.0),
                "percolation_mm": response.get("percolation_mm", 0),
                "area_hectares": response.get("area_hectares", 0),
                "crop_type": response.get("crop_type", "rice"),
                "crop_week": response.get("crop_week", 0),
                "water_level_adjustment": response.get("water_level_adjustment_factor", 1.0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get water demand for {area_id}: {str(e)}")
            raise
    
    async def get_bulk_water_demand(
        self,
        section_ids: List[str],
        week: int,
        year: int
    ) -> List[Dict[str, Any]]:
        """Get water demand for multiple sections in bulk"""
        try:
            endpoint = "/api/v1/water-demand/bulk"
            data = {
                "section_ids": section_ids,
                "week": week,
                "year": year
            }
            
            response = await self.post(endpoint, data)
            
            return response.get("demands", [])
            
        except Exception as e:
            logger.error(f"Failed to get bulk water demand: {str(e)}")
            raise
    
    async def get_weekly_water_levels(
        self,
        area_id: str,
        area_type: str,
        week: int,
        year: int
    ) -> Optional[float]:
        """Get average water level for the week"""
        try:
            endpoint = f"/api/v1/water-levels/{area_type}/{area_id}"
            params = {"week": week, "year": year}
            
            response = await self.get(endpoint, params=params)
            
            return response.get("avg_water_level_m")
            
        except Exception as e:
            logger.warning(f"Failed to get water levels for {area_id}: {str(e)}")
            return None
    
    async def get_crop_coefficient(
        self,
        crop_type: str,
        crop_week: int
    ) -> float:
        """Get crop coefficient (Kc) for specific crop and growth stage"""
        try:
            endpoint = f"/api/v1/crop-coefficients/{crop_type}"
            params = {"week": crop_week}
            
            response = await self.get(endpoint, params=params)
            
            return response.get("kc", 1.0)
            
        except Exception as e:
            logger.warning(f"Failed to get Kc for {crop_type} week {crop_week}: {str(e)}")
            return 1.0
    
    async def get_section_performance(
        self,
        section_id: str,
        start_week: int,
        end_week: int,
        year: int
    ) -> Dict[str, Any]:
        """Get historical performance data for a section"""
        try:
            endpoint = f"/api/v1/sections/{section_id}/performance"
            params = {
                "start_week": start_week,
                "end_week": end_week,
                "year": year
            }
            
            response = await self.get(endpoint, params=params)
            
            return {
                "section_id": section_id,
                "total_planned_m3": response.get("total_planned_m3", 0),
                "total_delivered_m3": response.get("total_delivered_m3", 0),
                "avg_efficiency": response.get("avg_efficiency", 0),
                "deficit_events": response.get("deficit_events", 0),
                "weekly_data": response.get("weekly_data", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to get section performance: {str(e)}")
            raise
    
    async def update_water_level_adjustment(
        self,
        area_id: str,
        week: int,
        year: int,
        water_level_m: float
    ) -> Dict[str, Any]:
        """Update water level for demand adjustment calculations"""
        try:
            endpoint = "/api/v1/water-levels/update"
            data = {
                "area_id": area_id,
                "week": week,
                "year": year,
                "water_level_m": water_level_m
            }
            
            response = await self.post(endpoint, data)
            
            return {
                "adjustment_factor": response.get("adjustment_factor", 1.0),
                "adjusted_demand_m3": response.get("adjusted_demand_m3", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to update water level adjustment: {str(e)}")
            raise