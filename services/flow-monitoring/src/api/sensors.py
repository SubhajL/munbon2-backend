from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
import structlog

from schemas import (
    SensorConfig,
    SensorCalibration,
    CalibrationHistory,
    SensorHealthMetrics,
    APIResponse,
    PaginatedResponse,
    PaginationParams
)
from services.sensor_service import SensorService
from db import DatabaseManager
from core.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()
router = APIRouter()

# Dependency injection
async def get_sensor_service():
    db_manager = DatabaseManager()
    return SensorService(db_manager)


@router.post("/calibrate", response_model=APIResponse[str])
async def calibrate_sensor(
    calibration: SensorCalibration,
    sensor_service: SensorService = Depends(get_sensor_service)
):
    """Calibrate a flow sensor"""
    with http_request_duration_seconds.labels(method="POST", endpoint="/sensors/calibrate").time():
        try:
            await sensor_service.calibrate_sensor(calibration)
            
            http_requests_total.labels(
                method="POST",
                endpoint="/sensors/calibrate",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data="Sensor calibrated successfully",
                message=f"Sensor {calibration.sensor_id} calibrated"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="POST",
                endpoint="/sensors/calibrate",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to calibrate sensor", error=str(e))
            http_requests_total.labels(
                method="POST",
                endpoint="/sensors/calibrate",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/{sensor_id}", response_model=APIResponse[SensorConfig])
async def get_sensor_config(
    sensor_id: UUID,
    sensor_service: SensorService = Depends(get_sensor_service)
):
    """Get sensor configuration"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/sensors/config").time():
        try:
            config = await sensor_service.get_sensor_config(sensor_id)
            
            if not config:
                http_requests_total.labels(
                    method="GET",
                    endpoint="/sensors/config",
                    status="404"
                ).inc()
                raise HTTPException(status_code=404, detail="Sensor not found")
            
            http_requests_total.labels(
                method="GET",
                endpoint="/sensors/config",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=config,
                message="Sensor configuration retrieved"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to get sensor config", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/sensors/config",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=APIResponse[List[SensorHealthMetrics]])
async def get_sensor_health(
    location_id: Optional[UUID] = Query(None, description="Filter by location ID"),
    sensor_service: SensorService = Depends(get_sensor_service)
):
    """Get sensor health metrics"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/sensors/health").time():
        try:
            metrics = await sensor_service.get_sensor_health(location_id)
            
            http_requests_total.labels(
                method="GET",
                endpoint="/sensors/health",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=metrics,
                message="Sensor health metrics retrieved"
            )
            
        except Exception as e:
            logger.error("Failed to get sensor health", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/sensors/health",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration/history/{sensor_id}", response_model=APIResponse[List[CalibrationHistory]])
async def get_calibration_history(
    sensor_id: UUID,
    limit: int = Query(10, ge=1, le=100, description="Number of records"),
    sensor_service: SensorService = Depends(get_sensor_service)
):
    """Get sensor calibration history"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/sensors/calibration/history").time():
        try:
            history = await sensor_service.get_calibration_history(sensor_id, limit)
            
            http_requests_total.labels(
                method="GET",
                endpoint="/sensors/calibration/history",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=history,
                message="Calibration history retrieved"
            )
            
        except Exception as e:
            logger.error("Failed to get calibration history", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/sensors/calibration/history",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))