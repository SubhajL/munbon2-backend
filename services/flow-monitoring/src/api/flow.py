from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
import structlog

from schemas import (
    FlowReading,
    FlowReadingCreate,
    FlowHistory,
    RealtimeFlowResponse,
    APIResponse,
    TimeRange,
    ErrorResponse
)
from services.flow_service import FlowService
from db import DatabaseManager
from core.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()
router = APIRouter()

# Dependency injection
async def get_flow_service():
    db_manager = DatabaseManager()
    return FlowService(db_manager)


@router.get("/realtime", response_model=APIResponse[List[RealtimeFlowResponse]])
async def get_realtime_flow(
    location_ids: List[UUID] = Query(..., description="List of location IDs"),
    flow_service: FlowService = Depends(get_flow_service)
):
    """Get real-time flow data for multiple locations"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/flow/realtime").time():
        try:
            data = await flow_service.get_realtime_flow(location_ids)
            
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/realtime",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message="Real-time flow data retrieved successfully"
            )
            
        except Exception as e:
            logger.error("Failed to get real-time flow", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/realtime",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=APIResponse[FlowHistory])
async def get_flow_history(
    location_id: UUID,
    start_time: datetime,
    end_time: datetime,
    interval: str = Query("1h", regex="^\\d+[smhd]$", description="Aggregation interval (e.g., 5m, 1h, 1d)"),
    aggregation: str = Query("mean", enum=["mean", "max", "min", "sum"]),
    flow_service: FlowService = Depends(get_flow_service)
):
    """Get historical flow data with aggregation"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/flow/history").time():
        try:
            # Validate time range
            time_range = TimeRange(start_time=start_time, end_time=end_time)
            time_range.validate_range()
            
            data = await flow_service.get_flow_history(
                location_id=location_id,
                start_time=start_time,
                end_time=end_time,
                interval=interval,
                aggregation=aggregation
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/history",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message="Flow history retrieved successfully"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/history",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to get flow history", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/history",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", response_model=APIResponse[str])
async def ingest_flow_data(
    readings: List[FlowReadingCreate],
    flow_service: FlowService = Depends(get_flow_service)
):
    """Ingest flow sensor readings"""
    with http_request_duration_seconds.labels(method="POST", endpoint="/flow/ingest").time():
        try:
            # Validate and process readings
            processed_count = await flow_service.ingest_flow_data(readings)
            
            http_requests_total.labels(
                method="POST",
                endpoint="/flow/ingest",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=f"Processed {processed_count} readings",
                message="Flow data ingested successfully",
                metadata={"count": processed_count}
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="POST",
                endpoint="/flow/ingest",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to ingest flow data", error=str(e))
            http_requests_total.labels(
                method="POST",
                endpoint="/flow/ingest",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest/{location_id}", response_model=APIResponse[FlowReading])
async def get_latest_reading(
    location_id: UUID,
    channel_id: Optional[str] = Query("main", description="Channel ID"),
    flow_service: FlowService = Depends(get_flow_service)
):
    """Get the latest flow reading for a specific location"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/flow/latest").time():
        try:
            data = await flow_service.get_latest_reading(location_id, channel_id)
            
            if not data:
                http_requests_total.labels(
                    method="GET",
                    endpoint="/flow/latest",
                    status="404"
                ).inc()
                raise HTTPException(status_code=404, detail="No data found for this location")
            
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/latest",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=data,
                message="Latest flow reading retrieved successfully"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to get latest reading", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/latest",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/{location_id}")
async def get_flow_statistics(
    location_id: UUID,
    period: str = Query("24h", regex="^\\d+[hd]$", description="Time period (e.g., 24h, 7d)"),
    flow_service: FlowService = Depends(get_flow_service)
):
    """Get flow statistics for a location over a time period"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/flow/statistics").time():
        try:
            # Parse period
            if period.endswith('h'):
                hours = int(period[:-1])
                start_time = datetime.utcnow() - timedelta(hours=hours)
            else:  # days
                days = int(period[:-1])
                start_time = datetime.utcnow() - timedelta(days=days)
            
            stats = await flow_service.get_flow_statistics(
                location_id=location_id,
                start_time=start_time,
                end_time=datetime.utcnow()
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/statistics",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=stats,
                message="Flow statistics calculated successfully"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/statistics",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to get flow statistics", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/flow/statistics",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))