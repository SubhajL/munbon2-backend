from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
import structlog

from schemas import WaterLevel, APIResponse, FlowForecast
from services.level_service import LevelService
from db import DatabaseManager
from core.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()
router = APIRouter()

# Dependency injection
async def get_level_service():
    db_manager = DatabaseManager()
    return LevelService(db_manager)


@router.get("/current", response_model=APIResponse[List[WaterLevel]])
async def get_current_levels(
    location_ids: List[UUID] = Query(..., description="List of location IDs"),
    level_service: LevelService = Depends(get_level_service)
):
    """Get current water levels for multiple locations"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/level/current").time():
        try:
            data = await level_service.get_current_levels(location_ids)
            
            http_requests_total.labels(
                method="GET",
                endpoint="/level/current",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message="Current water levels retrieved successfully"
            )
            
        except Exception as e:
            logger.error("Failed to get current levels", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/level/current",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast", response_model=APIResponse[List[FlowForecast]])
async def get_level_forecast(
    location_ids: List[UUID] = Query(..., description="List of location IDs"),
    horizon_hours: int = Query(24, ge=1, le=168, description="Forecast horizon in hours"),
    level_service: LevelService = Depends(get_level_service)
):
    """Get water level forecasts for multiple locations"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/level/forecast").time():
        try:
            data = await level_service.get_level_forecasts(location_ids, horizon_hours)
            
            http_requests_total.labels(
                method="GET",
                endpoint="/level/forecast",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message=f"{horizon_hours}-hour forecasts retrieved successfully"
            )
            
        except Exception as e:
            logger.error("Failed to get level forecast", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/level/forecast",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))