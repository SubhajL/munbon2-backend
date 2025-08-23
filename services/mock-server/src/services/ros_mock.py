"""
ROS Service Mock Endpoints
Provides mock water demand calculations and crop information
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, List
from datetime import datetime, date
import random

from data import get_mock_data_manager

router = APIRouter()
mock_data = get_mock_data_manager()


# Request/Response Models
class WaterDemandRequest(BaseModel):
    areaId: str
    areaType: str = "plot"
    areaRai: float
    cropType: str
    cropWeek: int
    calendarWeek: int
    calendarYear: int
    growthStage: Optional[str] = None
    effectiveRainfall: Optional[float] = 0


class SeasonalDemandRequest(BaseModel):
    areaId: str
    areaType: str = "section"
    areaRai: float
    cropType: str
    plantingDate: str
    includeRainfall: bool = True


# Endpoints
@router.post("/api/v1/water-demand/calculate")
async def calculate_water_demand(request: WaterDemandRequest):
    """Calculate water demand for a specific crop week"""
    
    # Get crop calendar for growth stage and Kc
    calendar = mock_data.get_crop_calendar(request.areaId, request.cropType)
    
    # Find appropriate growth stage
    growth_stage = request.growthStage
    kc_value = 1.0
    
    for stage in calendar['growth_stages']:
        if request.cropWeek >= stage['week']:
            growth_stage = stage['stage']
            kc_value = stage['kc']
    
    # Mock ET0 calculation (mm/day)
    et0_daily = random.uniform(4.5, 6.0)
    et0_weekly = et0_daily * 7
    
    # Calculate crop water demand
    etc = et0_weekly * kc_value
    percolation = 3 * 7  # 3mm/day percolation
    
    # Total water requirement in mm
    total_water_mm = etc + percolation
    
    # Convert to m³ (1mm on 1 rai = 1.6 m³)
    gross_demand_m3 = total_water_mm * request.areaRai * 1.6
    
    # Apply effective rainfall
    effective_rainfall_m3 = request.effectiveRainfall * request.areaRai * 1.6
    net_demand_m3 = max(0, gross_demand_m3 - effective_rainfall_m3)
    
    return {
        "status": "success",
        "data": {
            "areaId": request.areaId,
            "areaType": request.areaType,
            "areaRai": request.areaRai,
            "cropType": request.cropType,
            "cropWeek": request.cropWeek,
            "calendarWeek": request.calendarWeek,
            "calendarYear": request.calendarYear,
            "growthStage": growth_stage,
            "monthlyETo": et0_daily * 30,
            "weeklyETo": et0_weekly,
            "dailyETo": et0_daily,
            "kcValue": kc_value,
            "percolation": percolation / 7,  # Daily percolation
            "cropWaterDemandMm": total_water_mm,
            "cropWaterDemandM3": gross_demand_m3,
            "effectiveRainfall": request.effectiveRainfall,
            "effectiveRainfallM3": effective_rainfall_m3,
            "netWaterDemandMm": total_water_mm - request.effectiveRainfall,
            "netWaterDemandM3": net_demand_m3,
            "calculatedAt": datetime.utcnow().isoformat()
        }
    }


@router.post("/api/v1/water-demand/seasonal")
async def calculate_seasonal_demand(request: SeasonalDemandRequest):
    """Calculate seasonal water demand for entire crop cycle"""
    
    calendar = mock_data.get_crop_calendar(request.areaId, request.cropType)
    
    # Calculate total seasonal demand
    total_weeks = calendar['total_weeks']
    
    # Accumulate weekly demands
    total_demand_mm = 0
    total_effective_rainfall = 0
    weekly_demands = []
    
    for week in range(1, total_weeks + 1):
        # Find growth stage and Kc for this week
        kc = 1.0
        stage = "vegetative"
        
        for gs in calendar['growth_stages']:
            if week >= gs['week']:
                kc = gs['kc']
                stage = gs['stage']
        
        # Weekly calculations
        et0_weekly = random.uniform(30, 42)  # Weekly ET0
        etc = et0_weekly * kc
        percolation = 21  # 3mm/day * 7 days
        
        weekly_demand = etc + percolation
        weekly_rainfall = random.uniform(0, 20) if request.includeRainfall else 0
        
        total_demand_mm += weekly_demand
        total_effective_rainfall += weekly_rainfall * 0.8  # 80% effectiveness
        
        weekly_demands.append({
            "week": week,
            "stage": stage,
            "kc": kc,
            "demandMm": weekly_demand,
            "rainfallMm": weekly_rainfall
        })
    
    # Convert to m³
    total_demand_m3 = total_demand_mm * request.areaRai * 1.6
    total_rainfall_m3 = total_effective_rainfall * request.areaRai * 1.6
    net_demand_m3 = max(0, total_demand_m3 - total_rainfall_m3)
    
    return {
        "status": "success",
        "data": {
            "areaId": request.areaId,
            "areaType": request.areaType,
            "areaRai": request.areaRai,
            "cropType": request.cropType,
            "totalCropWeeks": total_weeks,
            "plantingDate": request.plantingDate,
            "harvestDate": calendar['expected_harvest_date'],
            "season": calendar['season'],
            "totalWaterDemandMm": total_demand_mm,
            "totalWaterDemandM3": total_demand_m3,
            "totalEffectiveRainfall": total_effective_rainfall,
            "totalEffectiveRainfallM3": total_rainfall_m3,
            "totalNetWaterDemandMm": total_demand_mm - total_effective_rainfall,
            "totalNetWaterDemandM3": net_demand_m3,
            "weeklyDemands": weekly_demands[:8],  # Return first 8 weeks as sample
            "calculatedAt": datetime.utcnow().isoformat()
        }
    }


@router.get("/api/v1/areas/{area_id}")
async def get_area_info(area_id: str):
    """Get area information including AOS station"""
    
    # Check if it's a plot or section
    if area_id.startswith("Z") and "P" in area_id:
        # It's a plot
        plot = mock_data.plots.get(area_id)
        if not plot:
            raise HTTPException(status_code=404, detail="Plot not found")
        
        section = mock_data.sections.get(plot['section_id'], {})
        
        return {
            "status": "success",
            "data": {
                "areaId": area_id,
                "areaType": "plot",
                "areaName": f"Plot {area_id}",
                "totalAreaRai": plot['area_rai'],
                "parentAreaId": plot['section_id'],
                "zone": plot['zone'],
                "aosStation": "Khon Kaen",  # Mock AOS station
                "province": "Khon Kaen",
                "elevation": plot.get('elevation_m', 220),
                "soilType": section.get('soil_type', 'loam'),
                "currentCrop": plot['crop_type'],
                "coordinates": {
                    "latitude": 16.4419 + (plot['zone'] * 0.01),
                    "longitude": 102.8359 + (plot['zone'] * 0.01)
                }
            }
        }
    else:
        # It's a section
        section = mock_data.sections.get(area_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")
        
        # Count plots in section
        plot_count = sum(1 for p in mock_data.plots.values() if p['section_id'] == area_id)
        
        return {
            "status": "success",
            "data": {
                "areaId": area_id,
                "areaType": "section",
                "areaName": f"Section {area_id}",
                "totalAreaRai": section['area_rai'],
                "totalAreaHectares": section['area_hectares'],
                "parentAreaId": f"Zone_{section['zone']}",
                "zone": section['zone'],
                "plotCount": plot_count,
                "aosStation": "Khon Kaen",
                "province": "Khon Kaen",
                "elevation": section.get('elevation_m', 220),
                "soilType": section.get('soil_type', 'loam'),
                "deliveryGate": section['delivery_gate'],
                "coordinates": {
                    "latitude": 16.4419 + (section['zone'] * 0.01),
                    "longitude": 102.8359 + (section['zone'] * 0.01)
                }
            }
        }


@router.get("/api/v1/crops/calendar")
async def get_crop_calendar(areaId: str, cropType: str):
    """Get crop calendar for planning"""
    
    calendar = mock_data.get_crop_calendar(areaId, cropType)
    
    return {
        "status": "success",
        "data": calendar
    }


@router.get("/api/v1/crops/coefficients/{crop_type}")
async def get_crop_coefficients(crop_type: str):
    """Get Kc coefficients for a crop type"""
    
    if crop_type == "rice":
        coefficients = {
            "initial": 1.05,
            "development": 1.1,
            "mid_season": 1.35,
            "late_season": 0.7,
            "stages": [
                {"stage": "seedling", "kc_min": 1.0, "kc_max": 1.1, "duration_days": 21},
                {"stage": "tillering", "kc_min": 1.05, "kc_max": 1.2, "duration_days": 28},
                {"stage": "panicle_initiation", "kc_min": 1.1, "kc_max": 1.3, "duration_days": 21},
                {"stage": "flowering", "kc_min": 1.2, "kc_max": 1.4, "duration_days": 21},
                {"stage": "grain_filling", "kc_min": 1.0, "kc_max": 1.2, "duration_days": 21},
                {"stage": "maturity", "kc_min": 0.6, "kc_max": 0.8, "duration_days": 14}
            ]
        }
    elif crop_type == "sugarcane":
        coefficients = {
            "initial": 0.4,
            "development": 0.7,
            "mid_season": 1.25,
            "late_season": 0.6,
            "stages": [
                {"stage": "germination", "kc_min": 0.35, "kc_max": 0.45, "duration_days": 84},
                {"stage": "tillering", "kc_min": 0.6, "kc_max": 0.8, "duration_days": 112},
                {"stage": "grand_growth", "kc_min": 1.1, "kc_max": 1.35, "duration_days": 84},
                {"stage": "ripening", "kc_min": 0.65, "kc_max": 0.85, "duration_days": 56},
                {"stage": "maturity", "kc_min": 0.5, "kc_max": 0.7, "duration_days": 28}
            ]
        }
    else:
        coefficients = {
            "initial": 0.3,
            "development": 0.7,
            "mid_season": 1.15,
            "late_season": 0.4,
            "stages": []
        }
    
    return {
        "status": "success",
        "data": {
            "cropType": crop_type,
            "coefficients": coefficients,
            "reference": "FAO-56",
            "lastUpdated": "2024-01-01"
        }
    }


@router.get("/api/v1/weather/eto/{location}")
async def get_eto_data(location: str, days: int = 7):
    """Get ETo (reference evapotranspiration) data"""
    
    # Generate mock ETo data
    eto_data = []
    
    for i in range(days):
        date_val = datetime.now().date() - timedelta(days=days-i-1)
        eto_data.append({
            "date": date_val.isoformat(),
            "eto_mm": round(random.uniform(3.5, 6.5), 1),
            "temperature_max": round(random.uniform(30, 37), 1),
            "temperature_min": round(random.uniform(22, 27), 1),
            "humidity_avg": round(random.uniform(60, 85), 0),
            "wind_speed_ms": round(random.uniform(1, 4), 1),
            "solar_radiation_mjm2": round(random.uniform(15, 25), 1)
        })
    
    return {
        "status": "success",
        "data": {
            "location": location,
            "station": "Khon Kaen AOS",
            "coordinates": {
                "latitude": 16.4419,
                "longitude": 102.8359
            },
            "elevation": 187,
            "daily_eto": eto_data,
            "monthly_avg": {
                "jan": 4.2, "feb": 4.8, "mar": 5.5, "apr": 6.2,
                "may": 5.8, "jun": 5.3, "jul": 5.0, "aug": 4.9,
                "sep": 4.6, "oct": 4.5, "nov": 4.1, "dec": 3.9
            }
        }
    }