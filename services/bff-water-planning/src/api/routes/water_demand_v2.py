"""
Water Demand API V2 - Using Pre-calculated Database Tables
Queries from weekly_water_demands and crop_season_weekly_progress tables
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
from pydantic import BaseModel

from core import get_logger
from db.weekly_demand_repository import weekly_demand_repo

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v2/water-demand", tags=["water-demand-v2"])


# Response Models
class WeeklyDemandResponse(BaseModel):
    """Weekly demand response from pre-calculated data"""
    week_start_date: str
    week_end_date: str
    area_id: str
    area_type: str
    calculation_method: str
    area_rai: float
    active_plots: int
    et0_mm: float
    avg_kc_factor: float
    gross_demand_m3: float
    net_demand_m3: float
    effective_rainfall_m3: float
    sensor_adjustment_factor: float
    adjusted_demand_m3: float
    final_demand_m3: float
    adjustment_percentage: float
    data_source: str


class SeasonProgressResponse(BaseModel):
    """Crop season progress response"""
    area_id: str
    area_type: str
    crop_type: str
    week_number: int
    week_start_date: str
    growth_stage: str
    area_rai: float
    weekly_demand_m3: float
    weekly_delivered_m3: float
    cumulative_demand_m3: float
    cumulative_delivered_m3: float
    remaining_weeks: int
    fulfillment_pct: float
    season_progress_pct: float
    stress_indicator: float


class ComparisonResponse(BaseModel):
    """Method comparison response"""
    area_id: str
    area_type: str
    week_date: str
    methods: Dict[str, Dict]
    differences: Optional[Dict]


# Section Level Endpoints
@router.get("/sections/{section_id}/weekly")
async def get_section_weekly_demand(
    section_id: str,
    week_date: Optional[date] = Query(None, description="Any date within the week"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> WeeklyDemandResponse:
    """Get pre-calculated weekly water demand for a section"""
    # Default to current week if not specified
    if not week_date:
        week_date = date.today()
    
    demand = await weekly_demand_repo.get_weekly_demand(
        area_id=section_id,
        area_type="section",
        week_date=week_date,
        calculation_method=calculation_method
    )
    
    if not demand:
        raise HTTPException(
            status_code=404,
            detail=f"No demand data found for section {section_id} for week containing {week_date}"
        )
    
    return WeeklyDemandResponse(**demand)


@router.get("/sections/{section_id}/historical")
async def get_section_historical_demands(
    section_id: str,
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> List[WeeklyDemandResponse]:
    """Get historical weekly demands for a section"""
    demands = await weekly_demand_repo.get_historical_demands(
        area_id=section_id,
        area_type="section",
        start_date=start_date,
        end_date=end_date,
        calculation_method=calculation_method
    )
    
    return [WeeklyDemandResponse(**d) for d in demands]


@router.get("/sections/{section_id}/compare-methods")
async def compare_section_methods(
    section_id: str,
    week_date: Optional[date] = Query(None, description="Any date within the week")
) -> ComparisonResponse:
    """Compare ROS vs RID-MS calculations for same section/week"""
    if not week_date:
        week_date = date.today()
    
    comparison = await weekly_demand_repo.compare_calculation_methods(
        area_id=section_id,
        area_type="section",
        week_date=week_date
    )
    
    return ComparisonResponse(**comparison)


@router.get("/sections/{section_id}/season-progress")
async def get_section_season_progress(
    section_id: str,
    crop_type: Optional[str] = Query(None, description="Filter by crop type"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> List[SeasonProgressResponse]:
    """Get crop season progress for a section"""
    progress = await weekly_demand_repo.get_season_progress(
        area_id=section_id,
        area_type="section",
        crop_type=crop_type,
        calculation_method=calculation_method
    )
    
    return [SeasonProgressResponse(**p) for p in progress]


# Zone Level Endpoints
@router.get("/zones/{zone_id}/weekly")
async def get_zone_weekly_demand(
    zone_id: int,
    week_date: Optional[date] = Query(None, description="Any date within the week"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> WeeklyDemandResponse:
    """Get pre-calculated weekly water demand for a zone"""
    if not week_date:
        week_date = date.today()
    
    demand = await weekly_demand_repo.get_weekly_demand(
        area_id=str(zone_id),
        area_type="zone",
        week_date=week_date,
        calculation_method=calculation_method
    )
    
    if not demand:
        raise HTTPException(
            status_code=404,
            detail=f"No demand data found for zone {zone_id} for week containing {week_date}"
        )
    
    return WeeklyDemandResponse(**demand)


@router.get("/zones/{zone_id}/sections")
async def get_zone_sections_weekly(
    zone_id: int,
    week_date: Optional[date] = Query(None, description="Any date within the week"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> Dict:
    """Get weekly demands for all sections in a zone"""
    if not week_date:
        week_date = date.today()
    
    # Get zone total
    zone_demand = await weekly_demand_repo.get_weekly_demand(
        area_id=str(zone_id),
        area_type="zone",
        week_date=week_date,
        calculation_method=calculation_method
    )
    
    # Get section demands
    section_demands = await weekly_demand_repo.get_current_week_demands(
        area_type="section",
        calculation_method=calculation_method,
        zone_filter=zone_id
    )
    
    return {
        "zone_id": zone_id,
        "week_start_date": zone_demand['week_start_date'] if zone_demand else None,
        "week_end_date": zone_demand['week_end_date'] if zone_demand else None,
        "calculation_method": calculation_method,
        "zone_total": zone_demand,
        "sections": [WeeklyDemandResponse(**s) for s in section_demands]
    }


@router.get("/zones/{zone_id}/season-progress")
async def get_zone_season_progress(
    zone_id: int,
    crop_type: Optional[str] = Query(None, description="Filter by crop type"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> List[SeasonProgressResponse]:
    """Get crop season progress for a zone"""
    progress = await weekly_demand_repo.get_season_progress(
        area_id=str(zone_id),
        area_type="zone",
        crop_type=crop_type,
        calculation_method=calculation_method
    )
    
    return [SeasonProgressResponse(**p) for p in progress]


# Munbon Level Endpoints
@router.get("/munbon/weekly")
async def get_munbon_weekly_demand(
    week_date: Optional[date] = Query(None, description="Any date within the week"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> WeeklyDemandResponse:
    """Get pre-calculated weekly water demand for entire Munbon"""
    if not week_date:
        week_date = date.today()
    
    demand = await weekly_demand_repo.get_weekly_demand(
        area_id="munbon",
        area_type="munbon",
        week_date=week_date,
        calculation_method=calculation_method
    )
    
    if not demand:
        raise HTTPException(
            status_code=404,
            detail=f"No demand data found for Munbon for week containing {week_date}"
        )
    
    return WeeklyDemandResponse(**demand)


@router.get("/munbon/current-summary")
async def get_munbon_current_summary(
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> Dict:
    """Get current season summary for Munbon"""
    zone_summary = await weekly_demand_repo.get_current_season_summary(
        area_type="zone",
        calculation_method=calculation_method
    )
    
    section_summary = await weekly_demand_repo.get_current_season_summary(
        area_type="section",
        calculation_method=calculation_method
    )
    
    return {
        "calculation_method": calculation_method,
        "timestamp": datetime.now().isoformat(),
        "zone_level": zone_summary,
        "section_level": section_summary
    }


# Current Week Endpoints
@router.get("/current-week/sections")
async def get_current_week_sections(
    zone_filter: Optional[int] = Query(None, description="Filter by zone"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> List[WeeklyDemandResponse]:
    """Get all section demands for current week"""
    demands = await weekly_demand_repo.get_current_week_demands(
        area_type="section",
        calculation_method=calculation_method,
        zone_filter=zone_filter
    )
    
    return [WeeklyDemandResponse(**d) for d in demands]


@router.get("/current-week/zones")
async def get_current_week_zones(
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> List[WeeklyDemandResponse]:
    """Get all zone demands for current week"""
    demands = await weekly_demand_repo.get_current_week_demands(
        area_type="zone",
        calculation_method=calculation_method
    )
    
    return [WeeklyDemandResponse(**d) for d in demands]


# Stress Analysis Endpoints
@router.get("/stressed-areas")
async def get_stressed_areas(
    stress_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Stress indicator threshold"),
    area_type: str = Query("section", regex="^(section|zone)$")
) -> List[Dict]:
    """Get areas with high water stress indicators"""
    stressed_areas = await weekly_demand_repo.get_stressed_areas(
        stress_threshold=stress_threshold,
        area_type=area_type
    )
    
    return stressed_areas


# Delivery Update Endpoint
@router.post("/delivery-update")
async def update_delivery_data(
    area_id: str = Query(..., description="Area ID"),
    area_type: str = Query(..., regex="^(section|zone)$"),
    week_date: date = Query(..., description="Any date within the week"),
    delivered_m3: float = Query(..., ge=0, description="Actual delivered volume"),
    scheduled_m3: float = Query(..., ge=0, description="Scheduled delivery volume")
) -> Dict:
    """Update actual delivery data for tracking"""
    await weekly_demand_repo.update_delivery_data(
        area_id=area_id,
        area_type=area_type,
        week_date=week_date,
        delivered_m3=delivered_m3,
        scheduled_m3=scheduled_m3
    )
    
    return {
        "status": "success",
        "message": "Delivery data updated",
        "area_id": area_id,
        "area_type": area_type,
        "week_date": week_date.isoformat(),
        "delivered_m3": delivered_m3,
        "scheduled_m3": scheduled_m3
    }


# Daily Approximation Endpoints (calculates from weekly data)
@router.get("/sections/{section_id}/daily-estimate")
async def get_section_daily_estimate(
    section_id: str,
    target_date: date = Query(..., description="Date for demand estimate"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> Dict:
    """Get daily demand estimate from weekly data (weekly/7)"""
    # Get the weekly demand for the week containing the target date
    weekly_demand = await weekly_demand_repo.get_weekly_demand(
        area_id=section_id,
        area_type="section",
        week_date=target_date,
        calculation_method=calculation_method
    )
    
    if not weekly_demand:
        raise HTTPException(
            status_code=404,
            detail=f"No weekly demand data found for section {section_id} for week containing {target_date}"
        )
    
    # Calculate daily estimate (weekly / 7)
    daily_factor = 1.0 / 7.0
    
    return {
        "section_id": section_id,
        "date": target_date.isoformat(),
        "calculation_method": calculation_method,
        "estimated_from_week": weekly_demand['week_start_date'],
        "daily_estimate": {
            "gross_demand_m3": weekly_demand['gross_demand_m3'] * daily_factor,
            "net_demand_m3": weekly_demand['net_demand_m3'] * daily_factor,
            "adjusted_demand_m3": weekly_demand['adjusted_demand_m3'] * daily_factor,
            "final_demand_m3": weekly_demand['final_demand_m3'] * daily_factor,
            "effective_rainfall_m3": weekly_demand['effective_rainfall_m3'] * daily_factor
        },
        "note": "Daily values are estimated as weekly values divided by 7"
    }


@router.get("/zones/{zone_id}/daily-estimate")
async def get_zone_daily_estimate(
    zone_id: int,
    target_date: date = Query(..., description="Date for demand estimate"),
    calculation_method: str = Query("ros", regex="^(ros|rid_ms|combined)$")
) -> Dict:
    """Get daily demand estimate for zone from weekly data"""
    weekly_demand = await weekly_demand_repo.get_weekly_demand(
        area_id=str(zone_id),
        area_type="zone",
        week_date=target_date,
        calculation_method=calculation_method
    )
    
    if not weekly_demand:
        raise HTTPException(
            status_code=404,
            detail=f"No weekly demand data found for zone {zone_id} for week containing {target_date}"
        )
    
    daily_factor = 1.0 / 7.0
    
    return {
        "zone_id": zone_id,
        "date": target_date.isoformat(),
        "calculation_method": calculation_method,
        "estimated_from_week": weekly_demand['week_start_date'],
        "daily_estimate": {
            "gross_demand_m3": weekly_demand['gross_demand_m3'] * daily_factor,
            "net_demand_m3": weekly_demand['net_demand_m3'] * daily_factor,
            "adjusted_demand_m3": weekly_demand['adjusted_demand_m3'] * daily_factor,
            "final_demand_m3": weekly_demand['final_demand_m3'] * daily_factor,
            "effective_rainfall_m3": weekly_demand['effective_rainfall_m3'] * daily_factor
        },
        "note": "Daily values are estimated as weekly values divided by 7"
    }


# Health Check
@router.get("/health")
async def health_check() -> Dict:
    """Check if weekly demand data is available"""
    try:
        # Check if we have current week data
        current_week_sections = await weekly_demand_repo.get_current_week_demands(
            area_type="section",
            calculation_method="ros"
        )
        
        current_week_zones = await weekly_demand_repo.get_current_week_demands(
            area_type="zone",
            calculation_method="ros"
        )
        
        return {
            "status": "healthy",
            "current_week_sections": len(current_week_sections),
            "current_week_zones": len(current_week_zones),
            "data_available": len(current_week_sections) > 0 or len(current_week_zones) > 0
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "data_available": False
        }