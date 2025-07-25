"""
Demand Processing API endpoints
Handles water demand submission and aggregation
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional
from datetime import datetime
import structlog

from ..schemas.demands import (
    DemandSubmission, DemandResponse, AggregatedDemands,
    DemandStatus, DemandConflict
)
from ..services.demand_service import DemandService
from ..services.schedule_optimizer import ScheduleOptimizer
from ..db.connections import DatabaseManager

logger = structlog.get_logger()
router = APIRouter()


def get_demand_service() -> DemandService:
    """Dependency to get demand service instance"""
    from ..main import db_manager, demand_aggregator
    return DemandService(db_manager, demand_aggregator)


@router.post("/demands", response_model=DemandResponse)
async def submit_demands(
    demands: DemandSubmission,
    background_tasks: BackgroundTasks,
    service: DemandService = Depends(get_demand_service)
):
    """
    Submit water demands for scheduling.
    This endpoint is called by Instance 18 (ROS/GIS Integration).
    """
    try:
        # Validate demands
        validation_result = await service.validate_demands(demands)
        
        if not validation_result.is_valid:
            return DemandResponse(
                schedule_id=None,
                status=DemandStatus.REJECTED,
                conflicts=validation_result.conflicts,
                message=validation_result.message
            )
        
        # Store demands
        demand_id = await service.store_demands(demands)
        
        # Generate schedule ID
        schedule_id = f"SCH-{demands.week}-{demand_id}"
        
        # Trigger schedule generation in background
        background_tasks.add_task(
            service.process_demands_for_scheduling,
            schedule_id,
            demands
        )
        
        logger.info(
            f"Demands submitted for week {demands.week}",
            schedule_id=schedule_id,
            sections_count=len(demands.sections)
        )
        
        return DemandResponse(
            schedule_id=schedule_id,
            status=DemandStatus.PROCESSING,
            conflicts=[],
            estimated_completion=datetime.utcnow().isoformat(),
            message="Demands accepted and schedule generation initiated"
        )
        
    except Exception as e:
        logger.error(f"Failed to submit demands: {e}")
        raise HTTPException(status_code=500, detail=f"Demand submission failed: {str(e)}")


@router.get("/demands/week/{week}", response_model=AggregatedDemands)
async def get_weekly_demands(
    week: str,
    service: DemandService = Depends(get_demand_service)
):
    """Get aggregated demands for a specific week"""
    try:
        demands = await service.get_aggregated_demands(week)
        
        if not demands:
            raise HTTPException(status_code=404, detail=f"No demands found for week {week}")
        
        return demands
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get weekly demands: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve demands: {str(e)}")


@router.get("/demands/status/{schedule_id}")
async def get_demand_processing_status(
    schedule_id: str,
    service: DemandService = Depends(get_demand_service)
):
    """Check the processing status of submitted demands"""
    try:
        status = await service.get_processing_status(schedule_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Schedule ID {schedule_id} not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get processing status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/demands/validate")
async def validate_demands(
    demands: DemandSubmission,
    service: DemandService = Depends(get_demand_service)
):
    """
    Validate demands without submitting them.
    Useful for pre-validation in client applications.
    """
    try:
        validation_result = await service.validate_demands(demands)
        
        return {
            "is_valid": validation_result.is_valid,
            "conflicts": validation_result.conflicts,
            "warnings": validation_result.warnings,
            "total_demand_m3": sum(s.demand_m3 for s in demands.sections),
            "sections_validated": len(demands.sections),
            "message": validation_result.message
        }
        
    except Exception as e:
        logger.error(f"Failed to validate demands: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.put("/demands/{demand_id}/priority")
async def update_demand_priority(
    demand_id: str,
    priority_update: Dict[str, int],
    service: DemandService = Depends(get_demand_service)
):
    """Update the priority of a specific demand"""
    try:
        new_priority = priority_update.get("priority")
        if new_priority is None or not (1 <= new_priority <= 10):
            raise HTTPException(
                status_code=400, 
                detail="Priority must be between 1 and 10"
            )
        
        success = await service.update_demand_priority(demand_id, new_priority)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Demand {demand_id} not found")
        
        return {
            "status": "success",
            "demand_id": demand_id,
            "new_priority": new_priority,
            "message": "Demand priority updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update demand priority: {e}")
        raise HTTPException(status_code=500, detail=f"Priority update failed: {str(e)}")


@router.get("/demands/conflicts/{week}")
async def get_demand_conflicts(
    week: str,
    service: DemandService = Depends(get_demand_service)
):
    """Get conflicts between demands for a specific week"""
    try:
        conflicts = await service.analyze_demand_conflicts(week)
        
        return {
            "week": week,
            "has_conflicts": len(conflicts) > 0,
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "resolution_suggestions": await service.suggest_conflict_resolutions(conflicts)
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze conflicts: {e}")
        raise HTTPException(status_code=500, detail=f"Conflict analysis failed: {str(e)}")


@router.post("/demands/aggregate/{week}")
async def trigger_demand_aggregation(
    week: str,
    service: DemandService = Depends(get_demand_service)
):
    """Manually trigger demand aggregation for a week"""
    try:
        result = await service.aggregate_demands_for_week(week)
        
        return {
            "status": "success",
            "week": week,
            "total_sections": result.get("sections_count"),
            "total_demand_m3": result.get("total_demand"),
            "zones_covered": result.get("zones"),
            "message": "Demands aggregated successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to aggregate demands: {e}")
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")