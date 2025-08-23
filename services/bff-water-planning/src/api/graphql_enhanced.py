import strawberry
from typing import List, Optional, Union
from datetime import datetime
import asyncio

from schemas.section import SectionType, SectionPerformanceType
from schemas.demand import DemandSubmissionResult, WeeklyDemandInput
from schemas.delivery import DeliveryPointType, PerformanceSummary
from schemas.spatial import SpatialMappingType, GateMappingType
from schemas.client_specific import (
    MobileSectionType, MobileDemandSummary, MobileWaterDashboard,
    WebSectionType, WebDemandDetails, WebWaterDashboard, ChartData, ChartDataset,
    APIResponse, APIDemandData
)
from services import (
    DemandAggregatorService,
    SpatialMappingService, 
    FeedbackService,
    PriorityEngine
)
from ..context import GraphQLContext
from core import get_logger

logger = get_logger(__name__)


@strawberry.type
class Query:
    @strawberry.field
    async def section(self, info: strawberry.Info[GraphQLContext], id: str) -> Optional[Union[MobileSectionType, WebSectionType]]:
        """Get section data optimized for client type"""
        context = info.context
        loader = context.dataloaders.section_loader
        
        # Use DataLoader for efficient fetching
        section_data = await loader.load(id)
        if not section_data:
            return None
        
        # Transform based on client type
        if context.client_type == "mobile":
            # Get just current demand for mobile
            demand_loader = context.dataloaders.demand_loader
            current_demand = await demand_loader.load((id, datetime.now().date(), "ROS"))
            
            return MobileSectionType(
                id=section_data["id"],
                name=section_data["name"],
                zone_code=section_data["zone_code"],
                area_rai=section_data["area_rai"],
                current_demand_m3=current_demand["net_demand_m3"] if current_demand else None,
                awd_active=False  # Will be updated with AWD integration
            )
        else:  # web or api
            # Get full data including plots and trends
            plot_loader = context.dataloaders.plot_loader
            plots = await plot_loader.load(id)
            
            # Get demand trend (last 7 days)
            demand_trend = []
            for i in range(7):
                date = datetime.now().date() - timedelta(days=i)
                demand = await context.dataloaders.demand_loader.load((id, date, "ROS"))
                if demand:
                    demand_trend.append(demand["net_demand_m3"])
            
            return WebSectionType(
                id=section_data["id"],
                name=section_data["name"],
                zone_code=section_data["zone_code"],
                area_rai=section_data["area_rai"],
                plot_count=len(plots),
                geometry=section_data.get("geometry"),
                current_demand_m3=demand_trend[0] if demand_trend else None,
                demand_trend=demand_trend,
                awd_status="inactive",  # Will be updated
                created_at=section_data["created_at"],
                updated_at=section_data["updated_at"]
            )
    
    @strawberry.field
    async def water_demand_dashboard(
        self, 
        info: strawberry.Info[GraphQLContext],
        zone_id: str,
        include_historical: bool = False
    ) -> Union[MobileWaterDashboard, WebWaterDashboard]:
        """Get dashboard data with request aggregation"""
        context = info.context
        
        # Parallel fetch all required data
        gis_service = SpatialMappingService()
        ros_service = DemandAggregatorService()
        awd_service = None  # Will be AWDService when integrated
        
        zone_data, sections, current_demands = await asyncio.gather(
            gis_service.get_zone(zone_id),
            gis_service.get_sections_by_zone(zone_id),
            ros_service.get_zone_demands(zone_id, datetime.now().date())
        )
        
        if context.client_type == "mobile":
            # Lightweight response for mobile
            mobile_sections = []
            for section in sections[:10]:  # Limit to 10 for mobile
                mobile_sections.append(MobileSectionType(
                    id=section["id"],
                    name=section["name"],
                    zone_code=zone_id,
                    area_rai=section["area_rai"],
                    current_demand_m3=current_demands.get(section["id"], {}).get("net_demand_m3"),
                    awd_active=False
                ))
            
            return MobileWaterDashboard(
                zone_name=zone_data["name"],
                total_demand=sum(d.get("net_demand_m3", 0) for d in current_demands.values()),
                awd_active=False,
                last_updated=datetime.now(),
                sections=mobile_sections,
                alerts_count=0  # Will be implemented
            )
        
        else:  # web
            # Full data for web including charts
            demand_details = []
            for section_id, demand in current_demands.items():
                demand_details.append(WebDemandDetails(
                    section_id=section_id,
                    gross_demand_m3=demand.get("gross_demand_m3", 0),
                    effective_rainfall_m3=demand.get("effective_rainfall_m3", 0),
                    net_demand_m3=demand.get("net_demand_m3", 0),
                    method=demand.get("method", "ROS"),
                    priority_score=demand.get("priority_score", 5.0)
                ))
            
            # Prepare chart data
            chart_data = self._prepare_demand_chart(current_demands)
            
            # Get historical data if requested
            historical_data = None
            if include_historical:
                historical_data = await ros_service.get_historical_demands(zone_id, days=30)
            
            return WebWaterDashboard(
                zone=zone_data,
                demand_details=demand_details,
                awd_full_status=None,  # Will be implemented
                charts=chart_data,
                historical_data=historical_data,
                predictions=None,  # Future enhancement
                performance_metrics={
                    "efficiency": 0.85,
                    "coverage": 0.92,
                    "satisfaction": 0.88
                }
            )
    
    def _prepare_demand_chart(self, demands: dict) -> ChartData:
        """Prepare chart data from demands"""
        labels = []
        data = []
        
        for section_id, demand in sorted(demands.items())[:10]:  # Top 10
            labels.append(section_id)
            data.append(demand.get("net_demand_m3", 0))
        
        return ChartData(
            labels=labels,
            datasets=[
                ChartDataset(
                    label="Water Demand (m³)",
                    data=data,
                    borderColor="#3B82F6",
                    backgroundColor="rgba(59, 130, 246, 0.5)"
                )
            ]
        )
    
    @strawberry.field
    async def sections_by_zone(
        self, 
        info: strawberry.Info[GraphQLContext],
        zone: int
    ) -> List[Union[MobileSectionType, WebSectionType]]:
        """Get sections with client-specific data"""
        context = info.context
        spatial_service = SpatialMappingService()
        sections = await spatial_service.get_sections_by_zone(zone)
        
        if context.client_type == "mobile":
            # Return simplified list for mobile
            return [
                MobileSectionType(
                    id=s["id"],
                    name=s["name"],
                    zone_code=str(zone),
                    area_rai=s["area_rai"],
                    awd_active=False
                )
                for s in sections[:20]  # Limit for mobile
            ]
        else:
            # Return full data for web
            result = []
            for s in sections:
                # Use DataLoader to batch fetch additional data
                plots = await context.dataloaders.plot_loader.load(s["id"])
                
                result.append(WebSectionType(
                    id=s["id"],
                    name=s["name"],
                    zone_code=str(zone),
                    area_rai=s["area_rai"],
                    plot_count=len(plots),
                    geometry=s.get("geometry"),
                    created_at=s["created_at"],
                    updated_at=s["updated_at"]
                ))
            return result


# Keep existing Mutation class
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def submit_demands(
        self,
        info: strawberry.Info[GraphQLContext],
        input: WeeklyDemandInput
    ) -> DemandSubmissionResult:
        """Submit weekly water demands for scheduling"""
        aggregator = DemandAggregatorService()
        priority_engine = PriorityEngine()
        
        # Process and prioritize demands
        prioritized_demands = await priority_engine.prioritize_demands(
            input.demands
        )
        
        # Aggregate by delivery points
        aggregated = await aggregator.aggregate_demands(
            week=input.week,
            demands=prioritized_demands,
            weather_adjustment=input.weather_adjustment,
            rainfall_mm=input.rainfall_forecast_mm
        )
        
        # Submit to scheduler
        result = await aggregator.submit_to_scheduler(aggregated)
        
        # Log based on client type
        logger.info(
            "Demands submitted",
            client_type=info.context.client_type,
            schedule_id=result["schedule_id"]
        )
        
        return DemandSubmissionResult(
            schedule_id=result["schedule_id"],
            status=result["status"],
            conflicts=result.get("conflicts", []),
            estimated_completion=result["estimated_completion"],
            total_sections=len(input.demands),
            total_volume_m3=sum(d.volume_m3 for d in input.demands)
        )


from datetime import timedelta

# Import was missing in the previous code
from datetime import datetime, timedelta