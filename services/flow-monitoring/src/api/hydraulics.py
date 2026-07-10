from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from uuid import UUID
import structlog

from schemas import APIResponse
from services.hydraulic_service import HydraulicService
from core.metrics import http_requests_total, http_request_duration_seconds

logger = structlog.get_logger()
router = APIRouter()

# Initialized once in main.py lifespan (mirrors api.control); None until then. The
# old per-request construction rebuilt every solver AND a DatabaseManager that was
# never connected (Wave 1.3).
hydraulic_service: Optional[HydraulicService] = None


def get_hydraulic_service() -> HydraulicService:
    """Dependency: the app-scoped service, or 503 if the lifespan has not built it."""
    if hydraulic_service is None:
        raise HTTPException(status_code=503, detail="Hydraulic service not initialized")
    return hydraulic_service


FACADE_REMOVED_DETAIL = (
    "removed: this endpoint returned hardcoded facade values, never a real hydraulic "
    "model (PROGRAM_REVIEW_2026-07-09 decision 2); real modeling arrives with the "
    "scheduler/SCADA waves"
)


def _facade_501(method: str, endpoint: str) -> HTTPException:
    """An honest 501 for the deleted model facades. No service dependency here: the
    answer is 501 whether or not the lifespan initialized (503 must not mask it)."""
    http_requests_total.labels(method=method, endpoint=endpoint, status="501").inc()
    return HTTPException(status_code=501, detail=FACADE_REMOVED_DETAIL)


@router.get("/model")
async def get_hydraulic_model_results(
    location_id: UUID,
    model_type: Optional[str] = Query("manning", enum=["manning", "saint-venant", "rating-curve"]),
):
    """Removed facade: manning/saint-venant/rating-curve returned constants (5.0/5.2/4.8)."""
    raise _facade_501("GET", "/hydraulics/model")


@router.post("/model/propagation")
async def simulate_water_propagation(
    start_location_id: UUID = Body(..., description="Starting location ID"),
    flow_rate: float = Body(..., description="Initial flow rate in m\u00b3/s"),
    duration_hours: int = Body(..., ge=1, le=72, description="Simulation duration in hours"),
    downstream_locations: Optional[List[UUID]] = Body(None, description="Specific downstream locations to simulate"),
):
    """Removed facade: the propagation simulation called a solver API that never existed."""
    raise _facade_501("POST", "/model/propagation")


@router.get("/model/ungauged/{location_id}")
async def estimate_ungauged_flow(location_id: UUID):
    """Removed facade: estimates interpolated from hardcoded dummy gauge data."""
    raise _facade_501("GET", "/hydraulics/ungauged")


@router.post("/model/calibrate")
async def calibrate_hydraulic_model(
    location_id: UUID = Body(...),
    observed_data: List[Dict[str, Any]] = Body(..., description="Observed flow/level data for calibration"),
    model_type: str = Body("manning", enum=["manning", "saint-venant", "rating-curve"]),
):
    """Removed facade: 'calibration' optimized nothing and stored nothing."""
    raise _facade_501("POST", "/hydraulics/calibrate")


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