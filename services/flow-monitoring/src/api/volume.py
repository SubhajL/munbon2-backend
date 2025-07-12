from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
import structlog

from schemas import (
    VolumeData,
    WaterBalance,
    APIResponse,
    TimeRange,
    PaginatedResponse,
    PaginationParams
)
from services.volume_service import VolumeService
from db import DatabaseManager
from core.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()
router = APIRouter()

# Dependency injection
async def get_volume_service():
    db_manager = DatabaseManager()
    return VolumeService(db_manager)


@router.get("/cumulative", response_model=APIResponse[VolumeData])
async def get_cumulative_volume(
    location_id: UUID,
    start_time: datetime,
    end_time: datetime,
    channel_id: Optional[str] = Query("main", description="Channel ID"),
    volume_service: VolumeService = Depends(get_volume_service)
):
    """Get cumulative volume for a location over a time period"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/volume/cumulative").time():
        try:
            # Validate time range
            time_range = TimeRange(start_time=start_time, end_time=end_time)
            time_range.validate_range()
            
            data = await volume_service.calculate_cumulative_volume(
                location_id=location_id,
                start_time=start_time,
                end_time=end_time,
                channel_id=channel_id
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/cumulative",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message="Cumulative volume calculated successfully"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/cumulative",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to calculate cumulative volume", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/cumulative",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance", response_model=APIResponse[WaterBalance])
async def get_water_balance(
    segment_id: UUID,
    time_period: str = Query("1d", regex="^\\d+[hd]$", description="Time period (e.g., 1h, 1d)"),
    volume_service: VolumeService = Depends(get_volume_service)
):
    """Calculate water balance for a network segment"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/volume/balance").time():
        try:
            # Parse time period
            end_time = datetime.utcnow()
            if time_period.endswith('h'):
                hours = int(time_period[:-1])
                start_time = end_time - timedelta(hours=hours)
            else:  # days
                days = int(time_period[:-1])
                start_time = end_time - timedelta(days=days)
            
            data = await volume_service.calculate_water_balance(
                segment_id=segment_id,
                start_time=start_time,
                end_time=end_time
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/balance",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message="Water balance calculated successfully"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/balance",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to calculate water balance", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/balance",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily", response_model=APIResponse[List[VolumeData]])
async def get_daily_volumes(
    location_ids: List[UUID] = Query(..., description="List of location IDs"),
    days: int = Query(7, ge=1, le=365, description="Number of days"),
    volume_service: VolumeService = Depends(get_volume_service)
):
    """Get daily volume totals for multiple locations"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/volume/daily").time():
        try:
            end_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            start_time = end_time - timedelta(days=days)
            
            data = await volume_service.get_daily_volumes(
                location_ids=location_ids,
                start_time=start_time,
                end_time=end_time
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/daily",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message=f"Daily volumes for {days} days retrieved successfully"
            )
            
        except Exception as e:
            logger.error("Failed to get daily volumes", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/daily",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance/history", response_model=APIResponse[PaginatedResponse[WaterBalance]])
async def get_balance_history(
    segment_id: UUID,
    start_time: datetime,
    end_time: datetime,
    pagination: PaginationParams = Depends(),
    volume_service: VolumeService = Depends(get_volume_service)
):
    """Get historical water balance records for a segment"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/volume/balance/history").time():
        try:
            # Validate time range
            time_range = TimeRange(start_time=start_time, end_time=end_time)
            time_range.validate_range()
            
            data, total = await volume_service.get_balance_history(
                segment_id=segment_id,
                start_time=start_time,
                end_time=end_time,
                offset=pagination.offset,
                limit=pagination.page_size
            )
            
            response = PaginatedResponse.from_query(
                items=data,
                total=total,
                pagination=pagination
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/balance/history",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=response,
                message="Balance history retrieved successfully"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/balance/history",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to get balance history", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/volume/balance/history",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/balance/calculate")
async def trigger_balance_calculation(
    segment_ids: List[UUID],
    volume_service: VolumeService = Depends(get_volume_service)
):
    """Trigger water balance calculation for multiple segments"""
    with http_request_duration_seconds.labels(method="POST", endpoint="/volume/balance/calculate").time():
        try:
            results = await volume_service.trigger_balance_calculations(segment_ids)
            
            http_requests_total.labels(
                method="POST",
                endpoint="/volume/balance/calculate",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=results,
                message=f"Balance calculation triggered for {len(segment_ids)} segments",
                metadata={"segment_count": len(segment_ids)}
            )
            
        except Exception as e:
            logger.error("Failed to trigger balance calculation", error=str(e))
            http_requests_total.labels(
                method="POST",
                endpoint="/volume/balance/calculate",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))