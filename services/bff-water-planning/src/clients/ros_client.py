"""
ROS Service Client
Handles communication with the ROS (Reservoir Operation Study) service
"""

from typing import Dict, List, Optional
import httpx
from datetime import datetime
import structlog

from config import settings
from core import get_logger

logger = get_logger(__name__)


class ROSClient:
    """Client for interacting with ROS service"""
    
    def __init__(self):
        # Use mock server URL if enabled, otherwise use actual ROS service URL
        if settings.use_mock_server:
            self.base_url = f"{settings.mock_server_url}/ros"
        else:
            self.base_url = settings.ros_service_url
        self.logger = logger.bind(client="ros")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._use_mock = settings.use_mock_server
    
    async def calculate_water_demand(self, demand_input: Dict) -> Optional[Dict]:
        """Calculate water demand for a specific crop week"""
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/water-demand/calculate",
                    json=demand_input
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data")
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to calculate water demand", error=str(e))
                return None
    
    async def get_seasonal_water_demand(
        self, 
        area_id: str,
        area_type: str,
        area_rai: float,
        crop_type: str,
        planting_date: datetime
    ) -> Optional[Dict]:
        """Get seasonal water demand"""
        if self._use_mock:
            return self._mock_seasonal_demand(area_id, crop_type, area_rai)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/water-demand/seasonal",
                    json={
                        "areaId": area_id,
                        "areaType": area_type,
                        "areaRai": area_rai,
                        "cropType": crop_type,
                        "plantingDate": planting_date.isoformat(),
                        "includeRainfall": True
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data")
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to get seasonal demand", error=str(e))
                return None
    
    async def get_area_info(self, area_id: str) -> Optional[Dict]:
        """Get area information including AOS station"""
        if self._use_mock:
            return self._mock_area_info(area_id)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/areas/{area_id}"
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data")
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to get area info", error=str(e))
                return None
    
    async def get_crop_calendar(self, area_id: str, crop_type: str) -> Optional[Dict]:
        """Get crop calendar for planning"""
        if self._use_mock:
            return self._mock_crop_calendar(area_id, crop_type)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/crops/calendar",
                    params={
                        "areaId": area_id,
                        "cropType": crop_type
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data")
                
            except httpx.HTTPError as e:
                self.logger.error("Failed to get crop calendar", error=str(e))
                return None
    
    async def get_weekly_water_level(self, water_level_input: Dict) -> Optional[Dict]:
        """Get aggregated weekly water level from ROS service"""
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/water-levels/weekly",
                    params={
                        "areaId": water_level_input.get("areaId"),
                        "areaType": water_level_input.get("areaType", "section"),
                        "calendarWeek": water_level_input.get("calendarWeek"),
                        "calendarYear": water_level_input.get("calendarYear")
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("data")
                
            except httpx.HTTPError as e:
                self.logger.warning(
                    "Failed to get weekly water level", 
                    area_id=water_level_input.get("areaId"),
                    error=str(e)
                )
                return None
    
    # Mock methods for development
    def _mock_water_demand(self, demand_input: Dict) -> Dict:
        """Mock water demand calculation"""
        crop_type = demand_input.get("cropType", "rice")
        area_rai = demand_input.get("areaRai", 100)
        
        # Mock calculations
        kc_values = {
            "rice": {"vegetative": 1.1, "reproductive": 1.2, "flowering": 1.35, "maturity": 0.7},
            "corn": {"vegetative": 0.3, "reproductive": 0.8, "flowering": 1.1, "maturity": 0.5},
            "sugarcane": {"vegetative": 0.4, "reproductive": 0.85, "flowering": 1.25, "maturity": 0.6}
        }
        
        growth_stage = demand_input.get("growthStage", "vegetative")
        kc = kc_values.get(crop_type, {}).get(growth_stage, 1.0)
        
        # Assume ETo of 5 mm/day
        eto = 5.0
        crop_water_demand_mm = eto * kc + 3  # Add 3mm percolation
        crop_water_demand_m3 = crop_water_demand_mm * area_rai * 1.6
        
        return {
            "areaId": demand_input.get("areaId"),
            "areaType": demand_input.get("areaType"),
            "areaRai": area_rai,
            "cropType": crop_type,
            "cropWeek": demand_input.get("cropWeek", 1),
            "calendarWeek": demand_input.get("calendarWeek", 1),
            "calendarYear": demand_input.get("calendarYear", 2024),
            "monthlyETo": eto * 30,
            "weeklyETo": eto * 7,
            "kcValue": kc,
            "percolation": 3,
            "cropWaterDemandMm": crop_water_demand_mm,
            "cropWaterDemandM3": crop_water_demand_m3,
            "effectiveRainfall": demand_input.get("effectiveRainfall", 0),
            "netWaterDemandMm": max(0, crop_water_demand_mm - demand_input.get("effectiveRainfall", 0)),
            "netWaterDemandM3": max(0, crop_water_demand_m3 - (demand_input.get("effectiveRainfall", 0) * area_rai * 1.6))
        }
    
    def _mock_seasonal_demand(self, area_id: str, crop_type: str, area_rai: float) -> Dict:
        """Mock seasonal water demand"""
        total_weeks = 16 if crop_type == "rice" else 20
        total_demand_mm = 1200 if crop_type == "rice" else 800
        total_demand_m3 = total_demand_mm * area_rai * 1.6
        
        return {
            "areaId": area_id,
            "areaType": "section",
            "areaRai": area_rai,
            "cropType": crop_type,
            "totalCropWeeks": total_weeks,
            "plantingDate": "2024-01-01T00:00:00Z",
            "harvestDate": f"2024-{4 if crop_type == 'rice' else 5}-01T00:00:00Z",
            "totalWaterDemandMm": total_demand_mm,
            "totalWaterDemandM3": total_demand_m3,
            "totalEffectiveRainfall": 200,
            "totalNetWaterDemandMm": total_demand_mm - 200,
            "totalNetWaterDemandM3": (total_demand_mm - 200) * area_rai * 1.6
        }
    
    def _mock_area_info(self, area_id: str) -> Dict:
        """Mock area information"""
        zone = int(area_id.split("_")[1]) if "_" in area_id else 1
        
        return {
            "areaId": area_id,
            "areaType": "section",
            "areaName": f"Section {area_id}",
            "totalAreaRai": 940.625,  # 150.5 hectares
            "parentAreaId": f"Zone_{zone}",
            "aosStation": "Khon Kaen",
            "province": "Khon Kaen"
        }
    
    def _mock_crop_calendar(self, area_id: str, crop_type: str) -> Dict:
        """Mock crop calendar"""
        return {
            "areaId": area_id,
            "areaType": "section",
            "cropType": crop_type,
            "plantingDate": "2024-01-01T00:00:00Z",
            "expectedHarvestDate": f"2024-{4 if crop_type == 'rice' else 5}-01T00:00:00Z",
            "season": "dry",
            "year": 2024,
            "growthStages": [
                {"week": 1, "stage": "seedling", "waterNeed": "low"},
                {"week": 4, "stage": "vegetative", "waterNeed": "medium"},
                {"week": 8, "stage": "reproductive", "waterNeed": "high"},
                {"week": 12, "stage": "flowering", "waterNeed": "critical"},
                {"week": 15, "stage": "maturity", "waterNeed": "low"}
            ]
        }