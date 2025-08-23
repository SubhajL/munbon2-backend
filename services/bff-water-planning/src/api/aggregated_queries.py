import strawberry
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import asyncio

from schemas.client_specific import ChartData, ChartDataset
from ..context import GraphQLContext
from core import get_logger

logger = get_logger(__name__)


@strawberry.type
class ComprehensiveSectionData:
    """Aggregated data from multiple services for a section"""
    # Basic info
    section_id: str
    section_name: str
    zone_code: str
    area_rai: float
    
    # From ROS Service
    current_demand_m3: float
    demand_method: str
    demand_updated_at: datetime
    
    # From GIS Service
    plot_count: int
    crop_distribution: Dict[str, int]
    
    # From Weather Service
    current_temperature: float
    rainfall_24h: float
    eto_today: float
    
    # From AWD Service (when integrated)
    awd_status: str
    awd_recommendation: Optional[str]
    moisture_level: Optional[float]
    
    # Calculated metrics
    water_efficiency: float
    demand_per_rai: float


@strawberry.type
class WaterPlanningOverview:
    """Complete overview aggregating data from all services"""
    timestamp: datetime
    
    # Summary statistics
    total_sections: int
    total_area_rai: float
    total_demand_m3: float
    active_awd_plots: int
    
    # Service health
    services_status: Dict[str, bool]
    
    # Charts
    demand_by_zone_chart: ChartData
    demand_by_method_chart: ChartData
    efficiency_trend_chart: ChartData
    
    # Alerts
    critical_sections: List[str]
    maintenance_alerts: List[Dict]
    weather_alerts: List[Dict]


@strawberry.type
class AggregatedQueries:
    """Queries that aggregate data from multiple backend services"""
    
    @strawberry.field
    async def comprehensive_section_data(
        self,
        info: strawberry.Info[GraphQLContext],
        section_id: str
    ) -> Optional[ComprehensiveSectionData]:
        """Get all available data for a section in one query"""
        context = info.context
        
        # Start all backend calls in parallel
        tasks = {
            "section": context.dataloaders.section_loader.load(section_id),
            "demand": context.dataloaders.demand_loader.load(
                (section_id, datetime.now().date(), "ROS")
            ),
            "plots": context.dataloaders.plot_loader.load(section_id),
            "weather": self._get_weather_data(section_id),
            "awd": context.dataloaders.awd_loader.load(section_id)
        }
        
        # Wait for all results
        results = {}
        for key, task in tasks.items():
            try:
                results[key] = await task
            except Exception as e:
                logger.error(f"Failed to fetch {key} data", error=str(e))
                results[key] = None
        
        # Check if section exists
        if not results["section"]:
            return None
        
        # Calculate crop distribution from plots
        crop_distribution = {}
        if results["plots"]:
            for plot in results["plots"]:
                crop = plot.get("crop_type", "unknown")
                crop_distribution[crop] = crop_distribution.get(crop, 0) + 1
        
        # Build comprehensive response
        return ComprehensiveSectionData(
            section_id=section_id,
            section_name=results["section"]["name"],
            zone_code=results["section"]["zone_code"],
            area_rai=results["section"]["area_rai"],
            current_demand_m3=results["demand"]["net_demand_m3"] if results["demand"] else 0,
            demand_method=results["demand"]["method"] if results["demand"] else "N/A",
            demand_updated_at=datetime.now(),
            plot_count=len(results["plots"]) if results["plots"] else 0,
            crop_distribution=crop_distribution,
            current_temperature=results["weather"]["temperature"] if results["weather"] else 30.0,
            rainfall_24h=results["weather"]["rainfall_24h"] if results["weather"] else 0.0,
            eto_today=results["weather"]["eto"] if results["weather"] else 5.0,
            awd_status=results["awd"]["current_phase"] if results["awd"] else "inactive",
            awd_recommendation=results["awd"]["recommendation"] if results["awd"] else None,
            moisture_level=results["awd"]["moisture_level"] if results["awd"] else None,
            water_efficiency=0.85,  # Would be calculated
            demand_per_rai=(
                results["demand"]["net_demand_m3"] / results["section"]["area_rai"]
                if results["demand"] and results["section"]["area_rai"] > 0
                else 0
            )
        )
    
    @strawberry.field
    async def water_planning_overview(
        self,
        info: strawberry.Info[GraphQLContext]
    ) -> WaterPlanningOverview:
        """Get complete system overview with data from all services"""
        
        # Parallel fetch from multiple services
        overview_tasks = {
            "zones": self._get_all_zones(),
            "total_demand": self._get_total_system_demand(),
            "service_health": self._check_all_services(),
            "weather_alerts": self._get_weather_alerts(),
            "critical_sections": self._get_critical_sections()
        }
        
        results = {}
        for key, task in overview_tasks.items():
            try:
                results[key] = await task
            except Exception as e:
                logger.error(f"Failed to fetch {key}", error=str(e))
                results[key] = None
        
        # Calculate summary statistics
        total_sections = sum(z["section_count"] for z in results.get("zones", []))
        total_area = sum(z["total_area_rai"] for z in results.get("zones", []))
        
        # Prepare charts
        demand_by_zone = self._prepare_zone_demand_chart(results.get("zones", []))
        demand_by_method = self._prepare_method_chart(results.get("total_demand", {}))
        
        return WaterPlanningOverview(
            timestamp=datetime.now(),
            total_sections=total_sections,
            total_area_rai=total_area,
            total_demand_m3=results.get("total_demand", {}).get("total", 0),
            active_awd_plots=0,  # Will be updated with AWD integration
            services_status=results.get("service_health", {}),
            demand_by_zone_chart=demand_by_zone,
            demand_by_method_chart=demand_by_method,
            efficiency_trend_chart=self._prepare_efficiency_trend(),
            critical_sections=results.get("critical_sections", []),
            maintenance_alerts=[],
            weather_alerts=results.get("weather_alerts", [])
        )
    
    async def _get_weather_data(self, section_id: str) -> Dict:
        """Mock weather data fetch"""
        # In production, would call weather service
        return {
            "temperature": 32.5,
            "rainfall_24h": 2.5,
            "eto": 5.2,
            "humidity": 75
        }
    
    async def _get_all_zones(self) -> List[Dict]:
        """Get all zones with statistics"""
        # In production, would query database
        return [
            {"zone_id": "01-03-01", "section_count": 15, "total_area_rai": 2250, "demand_m3": 45000},
            {"zone_id": "01-03-02", "section_count": 12, "total_area_rai": 1800, "demand_m3": 36000},
            {"zone_id": "01-03-03", "section_count": 18, "total_area_rai": 2700, "demand_m3": 54000}
        ]
    
    async def _get_total_system_demand(self) -> Dict:
        """Get total system demand by method"""
        return {
            "total": 135000,
            "by_method": {
                "ROS": 100000,
                "RID-MS": 35000
            }
        }
    
    async def _check_all_services(self) -> Dict[str, bool]:
        """Check health of all integrated services"""
        return {
            "ros": True,
            "gis": True,
            "weather": True,
            "awd": False,  # Not yet integrated
            "scheduler": True
        }
    
    async def _get_weather_alerts(self) -> List[Dict]:
        """Get current weather alerts"""
        return [
            {
                "type": "rainfall",
                "severity": "info",
                "message": "Light rain expected in next 24 hours",
                "affected_zones": ["01-03-01", "01-03-02"]
            }
        ]
    
    async def _get_critical_sections(self) -> List[str]:
        """Get sections with critical water needs"""
        return ["Zone_2_Section_A", "Zone_5_Section_C"]
    
    def _prepare_zone_demand_chart(self, zones: List[Dict]) -> ChartData:
        """Prepare demand by zone chart"""
        labels = [z["zone_id"] for z in zones]
        data = [z["demand_m3"] for z in zones]
        
        return ChartData(
            labels=labels,
            datasets=[
                ChartDataset(
                    label="Water Demand by Zone (m³)",
                    data=data,
                    borderColor="#10B981",
                    backgroundColor="rgba(16, 185, 129, 0.5)"
                )
            ]
        )
    
    def _prepare_method_chart(self, demand_data: Dict) -> ChartData:
        """Prepare demand by calculation method chart"""
        by_method = demand_data.get("by_method", {})
        
        return ChartData(
            labels=list(by_method.keys()),
            datasets=[
                ChartDataset(
                    label="Demand by Method (m³)",
                    data=list(by_method.values()),
                    borderColor="#F59E0B",
                    backgroundColor="rgba(245, 158, 11, 0.5)"
                )
            ]
        )
    
    def _prepare_efficiency_trend(self) -> ChartData:
        """Prepare water efficiency trend chart"""
        # Mock data for last 7 days
        dates = [(datetime.now() - timedelta(days=i)).strftime("%m/%d") for i in range(6, -1, -1)]
        efficiency = [0.82, 0.84, 0.83, 0.85, 0.86, 0.85, 0.87]
        
        return ChartData(
            labels=dates,
            datasets=[
                ChartDataset(
                    label="Water Efficiency",
                    data=efficiency,
                    borderColor="#6366F1",
                    backgroundColor="rgba(99, 102, 241, 0.5)"
                )
            ]
        )