"""
Schedule Management API endpoints
Handles weekly schedule retrieval and updates
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
import structlog

from ..schemas.schedule import (
    WeeklySchedule, ScheduleOperation, ScheduleStatus,
    ScheduleUpdate, ScheduleOptimizationRequest
)
from ..services.schedule_service import ScheduleService
from ..db.connections import DatabaseManager

logger = structlog.get_logger()
router = APIRouter()


def get_schedule_service() -> ScheduleService:
    """Dependency to get schedule service instance"""
    from ..main import db_manager, schedule_optimizer
    return ScheduleService(db_manager, schedule_optimizer)


@router.get("/week/{week}", response_model=WeeklySchedule)
async def get_weekly_schedule(
    week: str,
    service: ScheduleService = Depends(get_schedule_service)
):
    """
    Get the weekly irrigation schedule.
    Week format: YYYY-WW (e.g., 2025-03 for week 3 of 2025)
    """
    try:
        # Validate week format
        try:
            year, week_num = week.split("-")
            year = int(year)
            week_num = int(week_num)
            if week_num < 1 or week_num > 53:
                raise ValueError("Week number must be between 1 and 53")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid week format: {e}")
        
        # Get schedule
        schedule = await service.get_weekly_schedule(week)
        
        if not schedule:
            # Generate new schedule if none exists
            logger.info(f"No schedule found for week {week}, generating new schedule")
            schedule = await service.generate_new_schedule(week)
        
        return schedule
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get weekly schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve schedule: {str(e)}")


@router.post("/week/{week}/generate")
async def generate_schedule(
    week: str,
    request: ScheduleOptimizationRequest,
    service: ScheduleService = Depends(get_schedule_service)
):
    """
    Generate or regenerate schedule for a specific week.
    Triggers optimization based on current demands.
    """
    try:
        # Validate week format
        try:
            year, week_num = week.split("-")
            year = int(year)
            week_num = int(week_num)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid week format")
        
        # Generate optimized schedule
        result = await service.generate_optimized_schedule(
            week=week,
            force_regenerate=request.force_regenerate,
            optimization_params=request.optimization_params
        )
        
        logger.info(
            f"Schedule generated for week {week}",
            operations_count=len(result.get('operations', [])),
            optimization_time=result.get('optimization_time_ms')
        )
        
        return {
            "status": "success",
            "week": week,
            "schedule_id": result.get('schedule_id'),
            "operations_count": len(result.get('operations', [])),
            "optimization_metrics": result.get('optimization_metrics'),
            "message": "Schedule generated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Schedule generation failed: {str(e)}")


@router.put("/week/{week}/status")
async def update_schedule_status(
    week: str,
    status_update: ScheduleUpdate,
    service: ScheduleService = Depends(get_schedule_service)
):
    """Update the status of a weekly schedule"""
    try:
        success = await service.update_schedule_status(
            week=week,
            status=status_update.status,
            notes=status_update.notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Schedule for week {week} not found")
        
        logger.info(f"Schedule status updated for week {week} to {status_update.status}")
        
        return {
            "status": "success",
            "week": week,
            "new_status": status_update.status,
            "message": "Schedule status updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schedule status: {e}")
        raise HTTPException(status_code=500, detail=f"Status update failed: {str(e)}")


@router.get("/current")
async def get_current_schedule(
    service: ScheduleService = Depends(get_schedule_service)
):
    """Get the currently active schedule"""
    try:
        # Calculate current week
        today = date.today()
        week = today.isocalendar()[1]
        year = today.year
        current_week = f"{year}-{week:02d}"
        
        schedule = await service.get_weekly_schedule(current_week)
        
        if not schedule:
            return {
                "status": "no_schedule",
                "week": current_week,
                "message": "No active schedule for current week"
            }
        
        # Get today's operations
        day_name = today.strftime("%A")
        todays_operations = [
            op for op in schedule.operations 
            if op.day == day_name
        ]
        
        return {
            "week": current_week,
            "status": schedule.status,
            "total_operations": len(schedule.operations),
            "todays_operations": todays_operations,
            "teams_active": list(set(op.team_assigned for op in todays_operations if op.team_assigned))
        }
        
    except Exception as e:
        logger.error(f"Failed to get current schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve current schedule: {str(e)}")


@router.get("/history")
async def get_schedule_history(
    weeks: int = Query(4, ge=1, le=12, description="Number of past weeks to retrieve"),
    service: ScheduleService = Depends(get_schedule_service)
):
    """Get schedule history for past weeks"""
    try:
        today = date.today()
        history = []
        
        for i in range(weeks):
            week_date = today - timedelta(weeks=i)
            week_num = week_date.isocalendar()[1]
            year = week_date.year
            week_str = f"{year}-{week_num:02d}"
            
            schedule = await service.get_weekly_schedule(week_str)
            if schedule:
                history.append({
                    "week": week_str,
                    "status": schedule.status,
                    "operations_count": len(schedule.operations),
                    "completion_rate": await service.calculate_completion_rate(week_str)
                })
        
        return {
            "weeks_retrieved": len(history),
            "history": history
        }
        
    except Exception as e:
        logger.error(f"Failed to get schedule history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")


@router.post("/operation/{operation_id}/complete")
async def mark_operation_complete(
    operation_id: str,
    completion_data: Dict[str, any],
    service: ScheduleService = Depends(get_schedule_service)
):
    """Mark a scheduled operation as complete"""
    try:
        success = await service.mark_operation_complete(
            operation_id=operation_id,
            completion_time=completion_data.get('completion_time', datetime.utcnow()),
            actual_values=completion_data.get('actual_values', {}),
            notes=completion_data.get('notes')
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
        
        return {
            "status": "success",
            "operation_id": operation_id,
            "message": "Operation marked as complete"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark operation complete: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update operation: {str(e)}")


@router.get("/conflicts/{week}")
async def check_schedule_conflicts(
    week: str,
    service: ScheduleService = Depends(get_schedule_service)
):
    """Check for conflicts in the weekly schedule"""
    try:
        conflicts = await service.check_schedule_conflicts(week)
        
        return {
            "week": week,
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts,
            "conflict_count": len(conflicts)
        }
        
    except Exception as e:
        logger.error(f"Failed to check conflicts: {e}")
        raise HTTPException(status_code=500, detail=f"Conflict check failed: {str(e)}")