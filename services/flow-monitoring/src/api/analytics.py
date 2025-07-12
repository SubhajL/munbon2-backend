from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
import structlog

from schemas import (
    EfficiencyMetrics,
    FlowAnomaly,
    APIResponse,
    TimeRange,
    PaginatedResponse,
    PaginationParams
)
from services.analytics_service import AnalyticsService
from db import DatabaseManager
from core.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()
router = APIRouter()

# Dependency injection
async def get_analytics_service():
    db_manager = DatabaseManager()
    return AnalyticsService(db_manager)


@router.get("/efficiency", response_model=APIResponse[List[EfficiencyMetrics]])
async def get_efficiency_metrics(
    segment_ids: List[UUID] = Query(..., description="List of segment IDs"),
    time_period: str = Query("24h", regex="^\\d+[hd]$", description="Time period"),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get network efficiency metrics for segments"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/analytics/efficiency").time():
        try:
            # Parse time period
            end_time = datetime.utcnow()
            if time_period.endswith('h'):
                hours = int(time_period[:-1])
                start_time = end_time - timedelta(hours=hours)
            else:  # days
                days = int(time_period[:-1])
                start_time = end_time - timedelta(days=days)
            
            metrics = await analytics_service.calculate_efficiency_metrics(
                segment_ids=segment_ids,
                start_time=start_time,
                end_time=end_time
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/analytics/efficiency",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=metrics,
                message="Efficiency metrics calculated successfully"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/analytics/efficiency",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to calculate efficiency metrics", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/analytics/efficiency",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/losses", response_model=APIResponse[Dict[str, Any]])
async def analyze_losses(
    segment_id: UUID,
    start_time: datetime,
    end_time: datetime,
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Analyze water losses for a segment"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/analytics/losses").time():
        try:
            # Validate time range
            time_range = TimeRange(start_time=start_time, end_time=end_time)
            time_range.validate_range()
            
            analysis = await analytics_service.analyze_losses(
                segment_id=segment_id,
                start_time=start_time,
                end_time=end_time
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/analytics/losses",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=analysis,
                message="Loss analysis completed"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/analytics/losses",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to analyze losses", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/analytics/losses",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies", response_model=APIResponse[PaginatedResponse[FlowAnomaly]])
async def get_anomalies(
    location_ids: Optional[List[UUID]] = Query(None, description="Filter by location IDs"),
    severity: Optional[str] = Query(None, enum=["info", "warning", "critical", "emergency"]),
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    pagination: PaginationParams = Depends(),
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Get detected flow anomalies"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/alerts/anomalies").time():
        try:
            anomalies, total = await analytics_service.get_anomalies(
                location_ids=location_ids,
                severity=severity,
                resolved=resolved,
                start_time=start_time,
                end_time=end_time,
                offset=pagination.offset,
                limit=pagination.page_size
            )
            
            response = PaginatedResponse.from_query(
                items=anomalies,
                total=total,
                pagination=pagination
            )
            
            http_requests_total.labels(
                method="GET",
                endpoint="/alerts/anomalies",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=response,
                message="Anomalies retrieved successfully"
            )
            
        except Exception as e:
            logger.error("Failed to get anomalies", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/alerts/anomalies",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: UUID,
    resolution_notes: str = "",
    analytics_service: AnalyticsService = Depends(get_analytics_service)
):
    """Mark an anomaly as resolved"""
    with http_request_duration_seconds.labels(method="POST", endpoint="/alerts/anomalies/resolve").time():
        try:
            await analytics_service.resolve_anomaly(anomaly_id, resolution_notes)
            
            http_requests_total.labels(
                method="POST",
                endpoint="/alerts/anomalies/resolve",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data="Anomaly resolved",
                message=f"Anomaly {anomaly_id} marked as resolved"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="POST",
                endpoint="/alerts/anomalies/resolve",
                status="404"
            ).inc()
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error("Failed to resolve anomaly", error=str(e))
            http_requests_total.labels(
                method="POST",
                endpoint="/alerts/anomalies/resolve",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))