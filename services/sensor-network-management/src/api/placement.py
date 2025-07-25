from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta

from db import get_db
from models.placement import (
    PlacementRecommendation, OptimizationRequest, 
    OptimizationResult, SensorPlacement
)
from services.placement_optimizer import PlacementOptimizer

router = APIRouter()

@router.post("/optimize", response_model=OptimizationResult)
async def optimize_sensor_placement(
    request: OptimizationRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Generate optimal sensor placement recommendations"""
    optimizer: PlacementOptimizer = req.app.state.placement_optimizer
    
    try:
        result = await optimizer.optimize_placement(
            request, db
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations", response_model=List[PlacementRecommendation])
async def get_placement_recommendations(
    req: Request,
    days_ahead: int = 7,
    min_priority: str = "medium",
    db: AsyncSession = Depends(get_db)
):
    """Get placement recommendations for the next N days"""
    optimizer: PlacementOptimizer = req.app.state.placement_optimizer
    
    recommendations = await optimizer.get_recommendations(
        days_ahead=days_ahead,
        min_priority=min_priority,
        db=db
    )
    
    return recommendations

@router.get("/current", response_model=List[SensorPlacement])
async def get_current_placements(
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current sensor placements"""
    optimizer: PlacementOptimizer = req.app.state.placement_optimizer
    
    placements = await optimizer.get_current_placements(db)
    return placements

@router.post("/schedule", response_model=OptimizationResult)
async def schedule_placement(
    placement: SensorPlacement,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Schedule a specific sensor placement"""
    optimizer: PlacementOptimizer = req.app.state.placement_optimizer
    
    try:
        result = await optimizer.schedule_placement(placement, db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/coverage-analysis")
async def analyze_coverage(
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Analyze current sensor coverage"""
    optimizer: PlacementOptimizer = req.app.state.placement_optimizer
    
    analysis = await optimizer.analyze_coverage(db)
    return analysis

@router.get("/historical-performance")
async def get_historical_performance(
    section_id: Optional[str] = None,
    days_back: int = 30,
    req: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Get historical sensor placement performance"""
    optimizer: PlacementOptimizer = req.app.state.placement_optimizer
    
    performance = await optimizer.get_historical_performance(
        section_id=section_id,
        days_back=days_back,
        db=db
    )
    
    return performance