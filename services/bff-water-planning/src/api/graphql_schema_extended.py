import strawberry
from typing import List, Optional
from datetime import datetime

# Import existing schemas
from schemas.section import SectionType, SectionPerformanceType
from schemas.demand import DemandSubmissionResult, WeeklyDemandInput
from schemas.delivery import DeliveryPointType, PerformanceSummary
from schemas.spatial import SpatialMappingType, GateMappingType

# Import new schemas
from schemas.crop_season import CropSeasonConfigType, CropSeasonConfigInput, CropSeasonInitResult
from schemas.time_based_demand import (
    DailyDemandType, AccumulatedDemandType, DemandComparisonType,
    SeasonalDemandSummaryType, SpatialDemandType, DemandTimeSeriesType,
    TimePeriodEnum, CalculationMethodEnum
)

# Import services
from services import (
    DemandAggregatorService,
    SpatialMappingService,
    FeedbackService,
    PriorityEngine
)

# Import new query/mutation classes
from .water_demand_queries import WaterDemandQueries
from .crop_season_queries import CropSeasonQueries
from .crop_season_mutations import CropSeasonMutations
from .aggregated_queries import AggregatedQueries


@strawberry.type
class ExtendedQuery:
    """Extended GraphQL Query with all water planning features"""
    
    # === Existing Queries ===
    @strawberry.field
    async def section(self, id: str) -> Optional[SectionType]:
        """Get detailed information about a specific section"""
        spatial_service = SpatialMappingService()
        section_data = await spatial_service.get_section(id)
        if section_data:
            return SectionType(**section_data)
        return None
    
    @strawberry.field
    async def sections_by_zone(self, zone: int) -> List[SectionType]:
        """Get all sections in a specific zone"""
        spatial_service = SpatialMappingService()
        sections = await spatial_service.get_sections_by_zone(zone)
        return [SectionType(**s) for s in sections]
    
    @strawberry.field
    async def section_performance(
        self, 
        section_id: str, 
        weeks: int = 4
    ) -> List[SectionPerformanceType]:
        """Get historical performance data for a section"""
        feedback_service = FeedbackService()
        performances = await feedback_service.get_section_performance(
            section_id, weeks
        )
        return [SectionPerformanceType(**p) for p in performances]
    
    @strawberry.field
    async def delivery_points(self) -> List[DeliveryPointType]:
        """Get all delivery points (gates) in the system"""
        spatial_service = SpatialMappingService()
        points = await spatial_service.get_all_delivery_points()
        return [
            DeliveryPointType(
                gate_id=p["gate_id"],
                location_lat=p["location"]["lat"],
                location_lon=p["location"]["lon"],
                sections_served=p["sections_served"],
                max_flow_m3s=p["max_flow_m3s"],
                current_flow_m3s=p.get("current_flow_m3s", 0)
            )
            for p in points
        ]
    
    @strawberry.field
    async def gate_mappings(self) -> List[GateMappingType]:
        """Get gate utilization and section mappings"""
        spatial_service = SpatialMappingService()
        mappings = await spatial_service.get_gate_mappings()
        return [
            GateMappingType(
                gate_id=m["gate_id"],
                gate_type=m["gate_type"],
                sections_count=len(m["sections_served"]),
                total_area_rai=m["total_area_rai"],
                utilization_percent=m["utilization_percent"]
            )
            for m in mappings
        ]
    
    @strawberry.field
    async def spatial_mapping(self, section_id: str) -> Optional[SpatialMappingType]:
        """Get spatial routing information for a section"""
        spatial_service = SpatialMappingService()
        mapping = await spatial_service.get_section_mapping(section_id)
        if mapping:
            return SpatialMappingType(
                section_id=mapping["section_id"],
                delivery_gate=mapping["delivery_gate"],
                distance_km=mapping["distance_km"],
                travel_time_hours=mapping["travel_time_hours"]
            )
        return None
    
    @strawberry.field
    async def weekly_performance_summary(self, week: str) -> Optional[PerformanceSummary]:
        """Get aggregated performance metrics for a week"""
        feedback_service = FeedbackService()
        summary = await feedback_service.get_weekly_summary(week)
        if summary:
            return PerformanceSummary(**summary)
        return None
    
    @strawberry.field
    async def demand_conflicts(self, week: str) -> List[str]:
        """Check for demand conflicts in a given week"""
        aggregator = DemandAggregatorService()
        conflicts = await aggregator.check_conflicts(week)
        return conflicts
    
    # === New Water Demand Queries ===
    # Delegate to WaterDemandQueries class
    water_demands: WaterDemandQueries = strawberry.field(resolver=lambda: WaterDemandQueries())
    
    # === New Crop Season Queries ===
    # Delegate to CropSeasonQueries class
    crop_season: CropSeasonQueries = strawberry.field(resolver=lambda: CropSeasonQueries())
    
    # === Aggregated Queries (existing but enhanced) ===
    # Delegate to AggregatedQueries class
    aggregated: AggregatedQueries = strawberry.field(resolver=lambda: AggregatedQueries())


@strawberry.type
class ExtendedMutation:
    """Extended GraphQL Mutation with all water planning features"""
    
    # === Existing Mutations ===
    @strawberry.mutation
    async def submit_demands(
        self, 
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
        
        return DemandSubmissionResult(
            schedule_id=result["schedule_id"],
            status=result["status"],
            conflicts=result.get("conflicts", []),
            estimated_completion=result["estimated_completion"],
            total_sections=len(input.demands),
            total_volume_m3=sum(d.volume_m3 for d in input.demands)
        )
    
    @strawberry.mutation
    async def update_delivery_feedback(
        self,
        week: str,
        section_id: str,
        delivered_m3: float,
        efficiency: float
    ) -> bool:
        """Update delivery performance feedback"""
        feedback_service = FeedbackService()
        success = await feedback_service.update_section_delivery(
            week=week,
            section_id=section_id,
            delivered_m3=delivered_m3,
            efficiency=efficiency
        )
        return success
    
    @strawberry.mutation
    async def recalculate_priorities(self, week: str) -> List[str]:
        """Recalculate demand priorities based on latest data"""
        priority_engine = PriorityEngine()
        updated_sections = await priority_engine.recalculate_week(week)
        return updated_sections
    
    @strawberry.mutation
    async def update_section_mapping(
        self,
        section_id: str,
        new_gate_id: str
    ) -> bool:
        """Update the delivery gate for a section"""
        spatial_service = SpatialMappingService()
        success = await spatial_service.update_section_gate(
            section_id, new_gate_id
        )
        return success
    
    # === New Crop Season Mutations ===
    # Delegate to CropSeasonMutations class
    crop_season: CropSeasonMutations = strawberry.field(resolver=lambda: CropSeasonMutations())


# Create the extended GraphQL schema
extended_schema = strawberry.Schema(query=ExtendedQuery, mutation=ExtendedMutation)