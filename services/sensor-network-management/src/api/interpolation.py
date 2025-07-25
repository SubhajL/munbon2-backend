from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from datetime import datetime

from models.interpolation import (
    InterpolatedData, InterpolationRequest, 
    SpatialInterpolationGrid, InterpolationModelMetrics
)
from services.interpolation_engine import InterpolationEngine

router = APIRouter()

@router.get("/section/{section_id}", response_model=InterpolatedData)
async def get_interpolated_data(
    section_id: str,
    parameter: str = "water_level",
    req: Request = None
):
    """Get interpolated data for a specific section"""
    engine: InterpolationEngine = req.app.state.interpolation_engine
    
    try:
        data = await engine.interpolate_section(
            section_id=section_id,
            parameter=parameter
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch", response_model=List[InterpolatedData])
async def get_batch_interpolation(
    request: InterpolationRequest,
    req: Request = None
):
    """Get interpolated data for multiple sections"""
    engine: InterpolationEngine = req.app.state.interpolation_engine
    
    try:
        results = await engine.batch_interpolate(request)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/grid", response_model=SpatialInterpolationGrid)
async def get_spatial_grid(
    parameter: str = "water_level",
    resolution_m: float = 100.0,
    req: Request = None
):
    """Get spatial interpolation grid for visualization"""
    engine: InterpolationEngine = req.app.state.interpolation_engine
    
    try:
        grid = await engine.generate_spatial_grid(
            parameter=parameter,
            resolution_m=resolution_m
        )
        return grid
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/confidence/{section_id}")
async def get_interpolation_confidence(
    section_id: str,
    parameter: str = "water_level",
    req: Request = None
):
    """Get detailed confidence metrics for interpolation at a section"""
    engine: InterpolationEngine = req.app.state.interpolation_engine
    
    try:
        confidence = await engine.get_confidence_details(
            section_id=section_id,
            parameter=parameter
        )
        return confidence
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/model-metrics", response_model=List[InterpolationModelMetrics])
async def get_model_performance_metrics(
    req: Request = None
):
    """Get performance metrics for interpolation models"""
    engine: InterpolationEngine = req.app.state.interpolation_engine
    
    metrics = await engine.get_model_metrics()
    return metrics

@router.post("/calibrate")
async def calibrate_interpolation_model(
    section_id: str,
    actual_value: float,
    parameter: str = "water_level",
    req: Request = None
):
    """Calibrate interpolation model with actual measurement"""
    engine: InterpolationEngine = req.app.state.interpolation_engine
    
    try:
        result = await engine.calibrate_model(
            section_id=section_id,
            actual_value=actual_value,
            parameter=parameter
        )
        return {"status": "calibrated", "improvement": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coverage-map")
async def get_data_coverage_map(
    parameter: str = "water_level",
    req: Request = None
):
    """Get sensor coverage map showing data availability"""
    engine: InterpolationEngine = req.app.state.interpolation_engine
    
    coverage = await engine.get_coverage_map(parameter)
    return coverage