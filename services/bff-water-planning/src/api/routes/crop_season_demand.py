"""
Crop Season Demand API Routes
Provides endpoints for full crop season water demand calculations
"""

from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
import asyncio

from core import get_logger
from db import DatabaseManager
from services.crop_season_demand_calculator import CropSeasonDemandCalculator
from config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/crop-season-demand", tags=["Crop Season Demand"])


class CropSeasonDemandRequest(BaseModel):
    """Request model for crop season demand calculation"""
    area_id: str = Field(..., description="Area ID (plot, section, zone, or 'munbon')")
    area_type: str = Field(..., description="Area type", pattern="^(plot|section|zone|munbon)$")
    crop_type: str = Field(..., description="Crop type (rice, sugarcane, cassava, etc.)")
    planting_date: date = Field(..., description="Planting date")
    calculation_method: str = Field(
        default="ros",
        description="Calculation method",
        pattern="^(ros|rid_ms|combined)$"
    )
    include_weekly_breakdown: bool = Field(
        default=True,
        description="Include weekly breakdown in response"
    )
    include_rainfall_forecast: bool = Field(
        default=True,
        description="Include rainfall forecast in calculations"
    )


class WeeklyDemand(BaseModel):
    """Weekly demand breakdown"""
    week_number: int
    calendar_week: int
    calendar_year: int
    start_date: date
    end_date: date
    et0_mm: float
    kc_factor: float
    effective_rainfall_mm: float
    gross_demand_mm: float
    net_demand_mm: float
    gross_demand_m3: float
    net_demand_m3: float
    growth_stage: Optional[str]
    water_level_adjustment: Optional[float]


class CropSeasonDemandResponse(BaseModel):
    """Response model for crop season demand calculation"""
    area_id: str
    area_type: str
    area_rai: float
    crop_type: str
    planting_date: date
    expected_harvest_date: date
    total_crop_weeks: int
    calculation_method: str
    
    # Summary totals
    total_gross_demand_m3: float
    total_net_demand_m3: float
    total_effective_rainfall_m3: float
    average_weekly_demand_m3: float
    peak_weekly_demand_m3: float
    peak_demand_week: int
    
    # Weekly breakdown (optional)
    weekly_demands: Optional[List[WeeklyDemand]] = None
    
    # Metadata
    calculation_date: datetime
    data_sources: Dict[str, str]


db_manager = DatabaseManager()
calculator = CropSeasonDemandCalculator()


@router.post("/calculate", response_model=CropSeasonDemandResponse)
async def calculate_crop_season_demand(
    request: CropSeasonDemandRequest = Body(...)
) -> CropSeasonDemandResponse:
    """
    Calculate total water demand for entire crop season
    
    This endpoint calculates the total water demand from planting to harvest,
    using historical ET0, Kc values, and effective rainfall data.
    """
    try:
        logger.info(
            "Calculating crop season demand",
            area_id=request.area_id,
            area_type=request.area_type,
            crop_type=request.crop_type,
            planting_date=request.planting_date.isoformat()
        )
        
        # Calculate full season demand
        result = await calculator.calculate_full_season_demand(
            area_id=request.area_id,
            area_type=request.area_type,
            crop_type=request.crop_type,
            planting_date=request.planting_date,
            calculation_method=request.calculation_method,
            include_rainfall_forecast=request.include_rainfall_forecast
        )
        
        # Format response
        response = CropSeasonDemandResponse(
            area_id=result['area_id'],
            area_type=result['area_type'],
            area_rai=result['area_rai'],
            crop_type=result['crop_type'],
            planting_date=result['planting_date'],
            expected_harvest_date=result['expected_harvest_date'],
            total_crop_weeks=result['total_crop_weeks'],
            calculation_method=result['calculation_method'],
            total_gross_demand_m3=result['total_gross_demand_m3'],
            total_net_demand_m3=result['total_net_demand_m3'],
            total_effective_rainfall_m3=result['total_effective_rainfall_m3'],
            average_weekly_demand_m3=result['average_weekly_demand_m3'],
            peak_weekly_demand_m3=result['peak_weekly_demand_m3'],
            peak_demand_week=result['peak_demand_week'],
            calculation_date=datetime.now(),
            data_sources=result['data_sources']
        )
        
        # Add weekly breakdown if requested
        if request.include_weekly_breakdown:
            response.weekly_demands = [
                WeeklyDemand(**week) for week in result['weekly_breakdown']
            ]
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to calculate crop season demand", error=str(e))
        raise HTTPException(status_code=500, detail="Calculation failed")


@router.get("/batch/{area_type}")
async def get_batch_crop_season_demands(
    area_type: str,
    area_ids: Optional[str] = Query(None, description="Comma-separated area IDs"),
    crop_types: Optional[str] = Query(None, description="Comma-separated crop types"),
    planting_after: Optional[date] = Query(None, description="Filter by planting date"),
    calculation_method: str = Query("ros", description="Calculation method")
) -> Dict:
    """
    Get crop season demands for multiple areas in batch
    
    Useful for dashboard displays showing total seasonal demands
    """
    try:
        # Parse filters
        area_id_list = area_ids.split(',') if area_ids else None
        crop_type_list = crop_types.split(',') if crop_types else None
        
        # Get batch results
        results = await calculator.calculate_batch_season_demands(
            area_type=area_type,
            area_ids=area_id_list,
            crop_types=crop_type_list,
            planting_after=planting_after,
            calculation_method=calculation_method
        )
        
        return {
            "area_type": area_type,
            "total_areas": len(results),
            "calculation_method": calculation_method,
            "demands": results,
            "summary": {
                "total_net_demand_m3": sum(r['total_net_demand_m3'] for r in results),
                "total_area_rai": sum(r['area_rai'] for r in results),
                "average_demand_per_rai": sum(r['total_net_demand_m3'] for r in results) / 
                                         sum(r['area_rai'] for r in results) if results else 0
            }
        }
        
    except Exception as e:
        logger.error("Failed to get batch crop season demands", error=str(e))
        raise HTTPException(status_code=500, detail="Batch calculation failed")


@router.get("/summary")
async def get_crop_season_summary(
    zone: Optional[int] = Query(None, description="Filter by zone"),
    crop_type: Optional[str] = Query(None, description="Filter by crop type")
) -> Dict:
    """
    Get summary of all active crop seasons
    
    Provides overview of total seasonal water demands across the system
    """
    try:
        summary = await calculator.get_active_season_summary(
            zone=zone,
            crop_type=crop_type
        )
        
        return summary
        
    except Exception as e:
        logger.error("Failed to get crop season summary", error=str(e))
        raise HTTPException(status_code=500, detail="Summary generation failed")


@router.post("/forecast/{area_id}")
async def forecast_crop_season_demand(
    area_id: str,
    area_type: str = Query(..., pattern="^(plot|section|zone|munbon)$"),
    scenarios: List[Dict] = Body(
        ...,
        description="List of scenarios with crop_type and planting_date"
    )
) -> Dict:
    """
    Forecast water demand for different crop scenarios
    
    Useful for planning crop selection based on water availability
    """
    try:
        forecasts = []
        
        for scenario in scenarios:
            result = await calculator.calculate_full_season_demand(
                area_id=area_id,
                area_type=area_type,
                crop_type=scenario['crop_type'],
                planting_date=scenario['planting_date'],
                calculation_method='combined',
                include_rainfall_forecast=True
            )
            
            forecasts.append({
                "scenario": scenario,
                "total_net_demand_m3": result['total_net_demand_m3'],
                "peak_weekly_demand_m3": result['peak_weekly_demand_m3'],
                "expected_harvest_date": result['expected_harvest_date'],
                "water_efficiency_score": result.get('water_efficiency_score', 0)
            })
        
        # Sort by water efficiency
        forecasts.sort(key=lambda x: x['total_net_demand_m3'])
        
        return {
            "area_id": area_id,
            "area_type": area_type,
            "scenarios_evaluated": len(scenarios),
            "forecasts": forecasts,
            "recommendation": forecasts[0] if forecasts else None
        }
        
    except Exception as e:
        logger.error("Failed to forecast crop season demand", error=str(e))
        raise HTTPException(status_code=500, detail="Forecast failed")