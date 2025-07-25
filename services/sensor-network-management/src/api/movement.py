from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta

from db import get_db
from models.movement import (
    MovementSchedule, MovementTask, MovementOptimizationRequest,
    MovementStatus, FieldTeam
)
from services.movement_scheduler import MovementScheduler

router = APIRouter()

@router.post("/schedule", response_model=MovementSchedule)
async def create_movement_schedule(
    request: MovementOptimizationRequest,
    req: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Create optimized movement schedule for sensor relocations"""
    scheduler = MovementScheduler()
    
    try:
        schedule = await scheduler.create_schedule(request, db)
        return schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schedule/current", response_model=MovementSchedule)
async def get_current_schedule(
    db: AsyncSession = Depends(get_db)
):
    """Get current week's movement schedule"""
    scheduler = MovementScheduler()
    
    schedule = await scheduler.get_current_schedule(db)
    if not schedule:
        raise HTTPException(status_code=404, detail="No active schedule found")
    
    return schedule

@router.get("/tasks", response_model=List[MovementTask])
async def get_movement_tasks(
    status: Optional[MovementStatus] = None,
    team_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get movement tasks with optional filtering"""
    scheduler = MovementScheduler()
    
    tasks = await scheduler.get_tasks(
        status=status,
        team_id=team_id,
        db=db
    )
    
    return tasks

@router.put("/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    status: MovementStatus,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Update movement task status"""
    scheduler = MovementScheduler()
    
    try:
        updated = await scheduler.update_task_status(
            task_id=task_id,
            status=status,
            notes=notes,
            db=db
        )
        return {"status": "updated", "task": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/teams", response_model=List[FieldTeam])
async def get_field_teams(
    available_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get field teams information"""
    scheduler = MovementScheduler()
    
    teams = await scheduler.get_teams(
        available_only=available_only,
        db=db
    )
    
    return teams

@router.post("/tasks/{task_id}/assign")
async def assign_task_to_team(
    task_id: str,
    team_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Assign movement task to a field team"""
    scheduler = MovementScheduler()
    
    try:
        result = await scheduler.assign_task(
            task_id=task_id,
            team_id=team_id,
            db=db
        )
        return {"status": "assigned", "task": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schedule/optimization-score")
async def get_schedule_optimization_score(
    schedule_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get optimization score for movement schedule"""
    scheduler = MovementScheduler()
    
    score = await scheduler.calculate_optimization_score(
        schedule_id=schedule_id,
        db=db
    )
    
    return {
        "optimization_score": score["overall"],
        "distance_efficiency": score["distance"],
        "time_efficiency": score["time"],
        "coverage_score": score["coverage"]
    }

@router.get("/history")
async def get_movement_history(
    sensor_id: Optional[str] = None,
    days_back: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Get sensor movement history"""
    scheduler = MovementScheduler()
    
    history = await scheduler.get_movement_history(
        sensor_id=sensor_id,
        days_back=days_back,
        db=db
    )
    
    return history