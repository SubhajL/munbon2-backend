from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from uuid import UUID
import structlog

from schemas import APIResponse
from services.hydraulic_service import HydraulicService
from db import DatabaseManager
from core.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()
router = APIRouter()

# Dependency injection
async def get_hydraulic_service():
    db_manager = DatabaseManager()
    return HydraulicService(db_manager)


@router.get("/model", response_model=APIResponse[Dict[str, Any]])
async def get_hydraulic_model_results(
    location_id: UUID,
    model_type: Optional[str] = Query("manning", enum=["manning", "saint-venant", "rating-curve"]),
    hydraulic_service: HydraulicService = Depends(get_hydraulic_service)
):
    """Get hydraulic model results for a location"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/hydraulics/model").time():
        try:
            results = await hydraulic_service.get_model_results(location_id, model_type)
            
            http_requests_total.labels(
                method="GET",
                endpoint="/hydraulics/model",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=results,
                message="Hydraulic model results retrieved"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/hydraulics/model",
                status="404"
            ).inc()
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error("Failed to get hydraulic model results", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/hydraulics/model",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/model/propagation", response_model=APIResponse[Dict[str, Any]])
async def simulate_water_propagation(
    start_location_id: UUID = Body(..., description="Starting location ID"),
    flow_rate: float = Body(..., description="Initial flow rate in m³/s"),
    duration_hours: int = Body(..., ge=1, le=72, description="Simulation duration in hours"),
    downstream_locations: Optional[List[UUID]] = Body(None, description="Specific downstream locations to simulate"),
    hydraulic_service: HydraulicService = Depends(get_hydraulic_service)
):
    """Simulate water propagation through the network"""
    with http_request_duration_seconds.labels(method="POST", endpoint="/model/propagation").time():
        try:
            simulation = await hydraulic_service.simulate_propagation(
                start_location_id=start_location_id,
                flow_rate=flow_rate,
                duration_hours=duration_hours,
                downstream_locations=downstream_locations
            )
            
            http_requests_total.labels(
                method="POST",
                endpoint="/model/propagation",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=simulation,
                message="Water propagation simulation completed"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="POST",
                endpoint="/model/propagation",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to simulate propagation", error=str(e))
            http_requests_total.labels(
                method="POST",
                endpoint="/model/propagation",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/ungauged/{location_id}")
async def estimate_ungauged_flow(
    location_id: UUID,
    hydraulic_service: HydraulicService = Depends(get_hydraulic_service)
):
    """Estimate flow at ungauged location using hydraulic modeling"""
    with http_request_duration_seconds.labels(method="GET", endpoint="/hydraulics/ungauged").time():
        try:
            estimation = await hydraulic_service.estimate_ungauged_flow(location_id)
            
            http_requests_total.labels(
                method="GET",
                endpoint="/hydraulics/ungauged",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=estimation,
                message="Ungauged flow estimation completed"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="GET",
                endpoint="/hydraulics/ungauged",
                status="404"
            ).inc()
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error("Failed to estimate ungauged flow", error=str(e))
            http_requests_total.labels(
                method="GET",
                endpoint="/hydraulics/ungauged",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/model/calibrate")
async def calibrate_hydraulic_model(
    location_id: UUID = Body(...),
    observed_data: List[Dict[str, Any]] = Body(..., description="Observed flow/level data for calibration"),
    model_type: str = Body("manning", enum=["manning", "saint-venant", "rating-curve"]),
    hydraulic_service: HydraulicService = Depends(get_hydraulic_service)
):
    """Calibrate hydraulic model parameters using observed data"""
    with http_request_duration_seconds.labels(method="POST", endpoint="/hydraulics/calibrate").time():
        try:
            calibration_result = await hydraulic_service.calibrate_model(
                location_id=location_id,
                observed_data=observed_data,
                model_type=model_type
            )
            
            http_requests_total.labels(
                method="POST",
                endpoint="/hydraulics/calibrate",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=calibration_result,
                message="Model calibration completed successfully"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="POST",
                endpoint="/hydraulics/calibrate",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to calibrate model", error=str(e))
            http_requests_total.labels(
                method="POST",
                endpoint="/hydraulics/calibrate",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-schedule", response_model=APIResponse[Dict[str, Any]])
async def verify_irrigation_schedule(
    schedule: Dict[str, Any] = Body(..., description="Irrigation schedule to verify"),
    safety_margin: float = Body(0.1, ge=0, le=0.3, description="Safety margin for hydraulic constraints"),
    hydraulic_service: HydraulicService = Depends(get_hydraulic_service)
):
    """
    Verify if an irrigation schedule is hydraulically feasible.
    Checks water availability, delivery constraints, and system capacity.
    """
    with http_request_duration_seconds.labels(method="POST", endpoint="/hydraulics/verify-schedule").time():
        try:
            # Extract schedule details
            deliveries = schedule.get("deliveries", [])
            if not deliveries:
                raise ValueError("No deliveries specified in schedule")
            
            # Run hydraulic verification
            verification_result = await hydraulic_service.verify_schedule(
                deliveries=deliveries,
                safety_margin=safety_margin
            )
            
            http_requests_total.labels(
                method="POST",
                endpoint="/hydraulics/verify-schedule",
                status="200"
            ).inc()
            
            return APIResponse.success_response(
                data=verification_result,
                message="Schedule verification completed"
            )
            
        except ValueError as e:
            http_requests_total.labels(
                method="POST",
                endpoint="/hydraulics/verify-schedule",
                status="400"
            ).inc()
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("Failed to verify schedule", error=str(e))
            http_requests_total.labels(
                method="POST",
                endpoint="/hydraulics/verify-schedule",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=str(e))