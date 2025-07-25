from typing import Dict, List, Optional, Any
import httpx
import asyncio
from datetime import datetime
from core import get_logger
from config import settings

logger = get_logger(__name__)


class IntegrationClient:
    """HTTP client for integrating with other services"""
    
    def __init__(self):
        self.logger = logger.bind(service="integration_client")
        self.timeout = httpx.Timeout(30.0)
        self.base_urls = {
            "flow_monitoring": settings.external_service_url,
            "scheduler": settings.scheduler_url if not settings.use_mock_server else settings.mock_server_url,
            "ros": settings.ros_service_url if not settings.use_mock_server else settings.mock_server_url,
            "gis": settings.gis_service_url if not settings.use_mock_server else settings.mock_server_url,
            "weather": settings.weather_api_url
        }
    
    async def get_gate_states(self) -> Dict[str, Dict]:
        """Get current gate states from Flow Monitoring Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_urls['flow_monitoring']}/api/v1/gates/state"
                )
                response.raise_for_status()
                data = response.json()
                return data.get("gates", {})
        except Exception as e:
            self.logger.error("Failed to get gate states", error=str(e))
            return {}
    
    async def get_water_levels(self) -> Dict[str, Dict]:
        """Get current water levels from Flow Monitoring Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_urls['flow_monitoring']}/api/v1/network/water-levels"
                )
                response.raise_for_status()
                data = response.json()
                return data.get("levels", {})
        except Exception as e:
            self.logger.error("Failed to get water levels", error=str(e))
            return {}
    
    async def post_scheduler_demands(self, demands: Dict) -> Dict:
        """Submit demands to Scheduler Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_urls['scheduler']}/api/v1/scheduler/demands",
                    json=demands
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self.logger.error("Failed to submit demands", error=str(e))
            return {
                "schedule_id": f"ERROR-{datetime.utcnow().timestamp()}",
                "status": "failed",
                "error": str(e),
                "estimated_completion": datetime.utcnow()
            }
    
    async def get_weekly_demands(self, week: str) -> Dict:
        """Get aggregated demands for a week"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_urls['flow_monitoring']}/api/v1/demands/week/{week}"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self.logger.error("Failed to get weekly demands", error=str(e), week=week)
            return {"sections": []}
    
    async def push_ros_calculations_to_gis(self, calculations: List[Dict]) -> bool:
        """Push ROS calculations to GIS database for consolidation"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_urls['gis']}/api/v1/ros-demands/bulk",
                    json={"demands": calculations},
                    headers={"Authorization": "Bearer mock-token"}  # TODO: Use real auth
                )
                response.raise_for_status()
                result = response.json()
                
                self.logger.info(
                    "Pushed ROS calculations to GIS",
                    count=result.get('count', 0)
                )
                return True
        except Exception as e:
            self.logger.error("Failed to push ROS calculations", error=str(e))
            return False
    
    async def get_consolidated_demands(self, section_ids: List[str], week: int, year: int) -> Dict[str, Dict]:
        """Get consolidated water demands from GIS (includes ROS calculations)"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Query GIS for consolidated demands
                demands = {}
                
                for section_id in section_ids:
                    response = await client.get(
                        f"{self.base_urls['gis']}/api/v1/ros-demands",
                        params={
                            "sectionId": section_id,
                            "calendarWeek": week,
                            "calendarYear": year,
                            "latest": "true"
                        },
                        headers={"Authorization": "Bearer mock-token"}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('data'):
                            demand_data = data['data'][0]
                            demands[section_id] = {
                                "crop_type": demand_data.get('crop_type'),
                                "growth_stage": demand_data.get('growth_stage'),
                                "crop_week": demand_data.get('crop_week'),
                                "area_rai": demand_data.get('area_rai'),
                                "net_demand_m3": demand_data.get('net_demand_m3'),
                                "gross_demand_m3": demand_data.get('gross_demand_m3'),
                                "moisture_deficit_percent": demand_data.get('moisture_deficit_percent'),
                                "stress_level": demand_data.get('stress_level'),
                                "amphoe": demand_data.get('amphoe'),
                                "tambon": demand_data.get('tambon'),
                                "has_ros_calculation": True
                            }
                
                return demands
        except Exception as e:
            self.logger.error("Failed to get consolidated demands", error=str(e))
            return {}
    
    async def get_crop_requirements(self, section_ids: List[str]) -> Dict[str, Dict]:
        """Get crop water requirements from ROS Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                requirements = {}
                
                # Fetch data for each section from ROS
                for section_id in section_ids:
                    try:
                        # Get area information
                        area_response = await client.get(
                            f"{self.base_urls['ros']}/api/v1/ros/areas/{section_id}"
                        )
                        area_response.raise_for_status()
                        area_data = area_response.json().get('data', {})
                        
                        # Get current crop calendar
                        calendar_response = await client.get(
                            f"{self.base_urls['ros']}/api/v1/ros/calendar/area/{section_id}?year={datetime.now().year}"
                        )
                        calendar_response.raise_for_status()
                        calendar_data = calendar_response.json().get('data', [])
                        
                        # Find active crop
                        active_crop = None
                        current_date = datetime.now().date()
                        
                        for crop in calendar_data:
                            planting_date = datetime.fromisoformat(crop['plantingDate']).date()
                            harvest_date = datetime.fromisoformat(crop['harvestDate']).date()
                            if planting_date <= current_date <= harvest_date:
                                active_crop = crop
                                break
                        
                        if active_crop:
                            # Calculate current crop week
                            planting_date = datetime.fromisoformat(active_crop['plantingDate']).date()
                            days_since_planting = (current_date - planting_date).days
                            crop_week = min((days_since_planting // 7) + 1, 16)  # Max 16 weeks for rice
                            
                            # Determine growth stage based on crop week
                            growth_stage = self._get_growth_stage(active_crop['cropType'], crop_week)
                            
                            requirements[section_id] = {
                                "crop_type": active_crop['cropType'],
                                "growth_stage": growth_stage,
                                "crop_week": crop_week,
                                "planting_date": active_crop['plantingDate'],
                                "harvest_date": active_crop['harvestDate'],
                                "et_mm_day": 5.5,  # Default, should be calculated
                                "kc_factor": self._get_kc_factor(active_crop['cropType'], crop_week),
                                "water_need_mm": 6.6,  # Should be calculated
                                "stress_level": "none",
                                "area_rai": area_data.get('totalAreaRai', 0)
                            }
                        else:
                            # No active crop
                            requirements[section_id] = {
                                "crop_type": "none",
                                "growth_stage": "fallow",
                                "et_mm_day": 0,
                                "kc_factor": 0,
                                "water_need_mm": 0,
                                "stress_level": "none",
                                "area_rai": area_data.get('totalAreaRai', 0)
                            }
                    
                    except Exception as e:
                        self.logger.warning(f"Failed to get data for section {section_id}", error=str(e))
                        # Fallback to defaults
                        requirements[section_id] = {
                            "crop_type": "unknown",
                            "growth_stage": "unknown",
                            "et_mm_day": 5.5,
                            "kc_factor": 1.0,
                            "water_need_mm": 5.5,
                            "stress_level": "unknown",
                            "area_rai": 0
                        }
                
                return requirements
        except Exception as e:
            self.logger.error("Failed to get crop requirements", error=str(e))
            return {}
    
    def _get_growth_stage(self, crop_type: str, crop_week: int) -> str:
        """Determine growth stage based on crop type and week"""
        if crop_type == "rice":
            if crop_week <= 3:
                return "seedling"
            elif crop_week <= 7:
                return "tillering"
            elif crop_week <= 11:
                return "flowering"
            else:
                return "maturity"
        elif crop_type == "sugarcane":
            if crop_week <= 12:
                return "germination"
            elif crop_week <= 28:
                return "tillering"
            elif crop_week <= 40:
                return "grand_growth"
            else:
                return "maturity"
        else:
            return "unknown"
    
    def _get_kc_factor(self, crop_type: str, crop_week: int) -> float:
        """Get Kc factor based on crop type and week"""
        # These should come from ROS Kc data API
        if crop_type == "rice":
            if crop_week <= 3:
                return 1.05
            elif crop_week <= 7:
                return 1.10
            elif crop_week <= 11:
                return 1.20
            else:
                return 0.95
        elif crop_type == "sugarcane":
            if crop_week <= 12:
                return 0.40
            elif crop_week <= 28:
                return 0.75
            elif crop_week <= 40:
                return 1.25
            else:
                return 0.80
        else:
            return 1.0
    
    async def get_section_boundaries(self, section_ids: List[str]) -> Dict[str, Dict]:
        """Get section spatial data from GIS Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                boundaries = {}
                
                # Get JWT token if needed (mock for now)
                headers = {"Authorization": "Bearer mock-token"}
                
                for section_id in section_ids:
                    try:
                        # Query GIS for parcels in this section
                        # Section ID format: section_X_Y where X is zone
                        zone = int(section_id.split("_")[1])
                        
                        # Map section to amphoe/tambon (this mapping should come from config)
                        # For now, use zone-based mapping
                        amphoe_map = {
                            1: "เมืองนครราชสีมา",
                            2: "พิมาย",
                            3: "ปากช่อง",
                            4: "สีคิ้ว",
                            5: "สูงเนิน",
                            6: "ขามทะเลสอ"
                        }
                        
                        amphoe = amphoe_map.get(zone, "เมืองนครราชสีมา")
                        
                        # Query parcels for this area
                        response = await client.get(
                            f"{self.base_urls['gis']}/api/v1/rid-plan/parcels",
                            params={
                                "amphoe": amphoe,
                                "limit": 100
                            },
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            features = data.get('features', [])
                            
                            if features:
                                # Aggregate geometry and calculate total area in rai
                                total_area_rai = 0
                                geometries = []
                                
                                for feature in features:
                                    props = feature.get('properties', {})
                                    # Area is already in rai in the GIS data
                                    total_area_rai += props.get('areaRai', 0)
                                    geometries.append(feature.get('geometry'))
                                
                                # For simplicity, use the first parcel's geometry as section boundary
                                # In production, would merge all geometries
                                boundaries[section_id] = {
                                    "geometry": geometries[0] if geometries else None,
                                    "area_rai": total_area_rai,  # Already in rai!
                                    "parcel_count": len(features),
                                    "amphoe": amphoe,
                                    "elevation_m": 220 - (zone * 0.5)  # Approximate
                                }
                            else:
                                # No parcels found, use default
                                boundaries[section_id] = self._get_default_boundary(section_id, zone)
                        else:
                            # GIS service error, use default
                            self.logger.warning(f"GIS returned {response.status_code} for {section_id}")
                            boundaries[section_id] = self._get_default_boundary(section_id, zone)
                    
                    except Exception as e:
                        self.logger.warning(f"Failed to get boundary for {section_id}", error=str(e))
                        boundaries[section_id] = self._get_default_boundary(section_id, zone)
                
                return boundaries
        except Exception as e:
            self.logger.error("Failed to get section boundaries", error=str(e))
            return {}
    
    def _get_default_boundary(self, section_id: str, zone: int) -> Dict:
        """Get default boundary when GIS query fails"""
        base_lat = 14.82 + (zone * 0.01)
        base_lon = 103.15 + (zone * 0.01)
        
        return {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[
                    [base_lon, base_lat],
                    [base_lon + 0.01, base_lat],
                    [base_lon + 0.01, base_lat + 0.01],
                    [base_lon, base_lat + 0.01],
                    [base_lon, base_lat]
                ]]]
            },
            "area_rai": (150 + (zone * 10)) * 6.25,  # Convert hectares to rai
            "parcel_count": 0,
            "amphoe": "unknown",
            "elevation_m": 220 - (zone * 0.5)
        }
    
    async def get_weather_forecast(self, location: Dict[str, float], days: int = 7) -> Dict:
        """Get weather forecast for location"""
        try:
            # In production, would call weather API
            # For now, return mock forecast
            forecast = {
                "location": location,
                "days": days,
                "data": []
            }
            
            for i in range(days):
                forecast["data"].append({
                    "date": (datetime.utcnow() + timedelta(days=i)).date().isoformat(),
                    "rainfall_mm": 0 if i % 3 else 15,  # Rain every 3 days
                    "temperature_max_c": 32 + (i % 3),
                    "temperature_min_c": 24 + (i % 2),
                    "humidity_percent": 70 + (i * 2),
                    "et0_mm": 5.5 + (i * 0.1)
                })
            
            return forecast
        except Exception as e:
            self.logger.error("Failed to get weather forecast", error=str(e))
            return {"data": []}
    
    async def verify_hydraulic_schedule(
        self,
        operations: List[Dict],
        constraints: Optional[Dict] = None
    ) -> Dict:
        """Verify schedule feasibility with Flow Monitoring Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "proposed_operations": operations,
                    "constraints": constraints or {}
                }
                
                response = await client.post(
                    f"{self.base_urls['flow_monitoring']}/api/v1/hydraulics/verify-schedule",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            self.logger.error("Failed to verify schedule", error=str(e))
            return {
                "feasible": False,
                "warnings": [str(e)],
                "water_levels": {}
            }
    
    async def get_mobile_sensor_data(self) -> List[Dict]:
        """Get latest mobile sensor readings"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_urls['flow_monitoring']}/api/v1/sensors/mobile/status"
                )
                response.raise_for_status()
                data = response.json()
                return data.get("sensors", [])
        except Exception as e:
            self.logger.error("Failed to get sensor data", error=str(e))
            return []
    
    async def update_performance_feedback(self, feedback: Dict) -> bool:
        """Send performance feedback to Flow Monitoring Service"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_urls['flow_monitoring']}/api/v1/performance/feedback",
                    json=feedback
                )
                response.raise_for_status()
                return True
        except Exception as e:
            self.logger.error("Failed to send feedback", error=str(e))
            return False