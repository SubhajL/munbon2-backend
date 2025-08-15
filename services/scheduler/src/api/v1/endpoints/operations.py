from typing import Dict, List, Optional
from datetime import datetime, date, time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....core.deps import get_db, get_current_user, get_redis
from ....core.redis import RedisClient
from ....core.logger import get_logger
from ....models.schedule import ScheduledOperation, WeeklySchedule
from ....schemas.operation import (
    OperationResponse, OperationUpdate, OperationStatus,
    OperationSummary, GateOperationHistory
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/schedule/{schedule_id}", response_model=List[OperationResponse])
async def get_schedule_operations(
    schedule_id: UUID,
    team_id: Optional[str] = Query(None, description="Filter by team"),
    gate_id: Optional[str] = Query(None, description="Filter by gate"),
    date: Optional[date] = Query(None, description="Filter by date"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[OperationResponse]:
    """Get all operations for a schedule with filtering"""
    
    query = select(ScheduledOperation).where(
        ScheduledOperation.schedule_id == schedule_id
    )
    
    # Apply filters
    if team_id:
        query = query.where(ScheduledOperation.team_id == team_id)
    
    if gate_id:
        query = query.where(ScheduledOperation.gate_id == gate_id)
    
    if date:
        query = query.where(ScheduledOperation.operation_date == date)
    
    if status:
        query = query.where(ScheduledOperation.status == status)
    
    # Order by date and sequence
    query = query.order_by(
        ScheduledOperation.operation_date,
        ScheduledOperation.operation_sequence
    )
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    return [OperationResponse.from_orm(op) for op in operations]


@router.get("/{operation_id}", response_model=OperationResponse)
async def get_operation(
    operation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> OperationResponse:
    """Get operation details by ID"""
    
    result = await db.execute(
        select(ScheduledOperation)
        .where(ScheduledOperation.id == operation_id)
        .options(selectinload(ScheduledOperation.schedule))
    )
    
    operation = result.scalar_one_or_none()
    
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found"
        )
    
    return OperationResponse.from_orm(operation)


@router.patch("/{operation_id}/status", response_model=OperationResponse)
async def update_operation_status(
    operation_id: UUID,
    status_update: OperationStatus,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> OperationResponse:
    """
    Update operation status (for field teams).
    
    Valid transitions:
    - scheduled -> in_progress
    - in_progress -> completed/failed
    - failed -> rescheduled
    """
    
    result = await db.execute(
        select(ScheduledOperation)
        .where(ScheduledOperation.id == operation_id)
        .options(selectinload(ScheduledOperation.schedule))
    )
    
    operation = result.scalar_one_or_none()
    
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found"
        )
    
    # Validate status transition
    valid_transitions = {
        "scheduled": ["in_progress", "cancelled"],
        "in_progress": ["completed", "failed"],
        "failed": ["rescheduled"],
        "completed": [],  # No transitions from completed
        "cancelled": ["rescheduled"],
    }
    
    current_status = operation.status
    new_status = status_update.status
    
    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {current_status} to {new_status}"
        )
    
    # Update status and related fields
    operation.status = new_status
    operation.updated_by = current_user.get("username", "unknown")
    
    if new_status == "in_progress":
        operation.actual_start_time = status_update.timestamp or datetime.utcnow()
    elif new_status == "completed":
        operation.actual_end_time = status_update.timestamp or datetime.utcnow()
        operation.actual_opening_percent = status_update.actual_opening_percent
        operation.actual_flow_achieved = status_update.actual_flow
        operation.completion_notes = status_update.notes
    elif new_status == "failed":
        operation.failure_reason = status_update.failure_reason
        operation.requires_rescheduling = True
    
    # Add verification data if provided
    if status_update.verification_photos:
        operation.verification_photos = status_update.verification_photos
    
    if status_update.gps_coordinates:
        operation.actual_latitude = status_update.gps_coordinates.get("latitude")
        operation.actual_longitude = status_update.gps_coordinates.get("longitude")
    
    await db.commit()
    await db.refresh(operation)
    
    # Publish status update for real-time monitoring
    await redis.publish(
        f"operation_status:{operation.schedule_id}",
        {
            "operation_id": str(operation_id),
            "gate_id": operation.gate_id,
            "team_id": operation.team_id,
            "old_status": current_status,
            "new_status": new_status,
            "timestamp": datetime.utcnow().isoformat(),
            "updated_by": current_user.get("username", "unknown"),
        }
    )
    
    return OperationResponse.from_orm(operation)


@router.patch("/{operation_id}", response_model=OperationResponse)
async def update_operation(
    operation_id: UUID,
    update_data: OperationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> OperationResponse:
    """Update operation details (for admins)"""
    
    result = await db.execute(
        select(ScheduledOperation).where(ScheduledOperation.id == operation_id)
    )
    
    operation = result.scalar_one_or_none()
    
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found"
        )
    
    # Only allow updates to scheduled operations
    if operation.status not in ["scheduled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update scheduled operations"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(operation, field, value)
    
    operation.updated_by = current_user.get("username", "unknown")
    
    await db.commit()
    await db.refresh(operation)
    
    return OperationResponse.from_orm(operation)


@router.get("/gate/{gate_id}/history", response_model=List[GateOperationHistory])
async def get_gate_operation_history(
    gate_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[GateOperationHistory]:
    """Get operation history for a specific gate"""
    
    query = select(ScheduledOperation).where(
        ScheduledOperation.gate_id == gate_id
    )
    
    if start_date:
        query = query.where(ScheduledOperation.operation_date >= start_date)
    
    if end_date:
        query = query.where(ScheduledOperation.operation_date <= end_date)
    
    query = query.order_by(ScheduledOperation.operation_date.desc()).limit(limit)
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    history = []
    for op in operations:
        history.append(GateOperationHistory(
            operation_id=op.id,
            schedule_id=op.schedule_id,
            operation_date=op.operation_date,
            planned_time=op.planned_start_time,
            actual_time=op.actual_start_time,
            team_id=op.team_id,
            team_name=op.team_name,
            target_opening=op.target_opening_percent,
            actual_opening=op.actual_opening_percent,
            status=op.status,
            notes=op.completion_notes or op.failure_reason,
        ))
    
    return history


@router.get("/today", response_model=List[OperationSummary])
async def get_todays_operations(
    team_id: Optional[str] = Query(None, description="Filter by team"),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> List[OperationSummary]:
    """Get today's scheduled operations"""
    
    today = date.today()
    
    # Get active schedule
    active_schedule_key = f"active_schedule:{today.year}:week_{today.isocalendar()[1]}"
    active_schedule = await redis.get_json(active_schedule_key)
    
    if not active_schedule:
        return []
    
    query = select(ScheduledOperation).where(
        and_(
            ScheduledOperation.schedule_id == active_schedule["id"],
            ScheduledOperation.operation_date == today
        )
    )
    
    if team_id:
        query = query.where(ScheduledOperation.team_id == team_id)
    
    query = query.order_by(
        ScheduledOperation.planned_start_time,
        ScheduledOperation.operation_sequence
    )
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    summaries = []
    for op in operations:
        summary = OperationSummary(
            operation_id=op.id,
            gate_id=op.gate_id,
            gate_name=op.gate_name,
            team_id=op.team_id,
            planned_time=op.planned_start_time,
            status=op.status,
            location={
                "latitude": op.latitude,
                "longitude": op.longitude,
                "description": op.location_description,
            },
            action=f"{op.operation_type} to {op.target_opening_percent}%",
            priority="high" if op.operation_sequence <= 5 else "normal",
        )
        summaries.append(summary)
    
    return summaries


@router.post("/{operation_id}/reschedule", response_model=OperationResponse)
async def reschedule_operation(
    operation_id: UUID,
    new_date: date = Query(...),
    new_time: time = Query(...),
    new_team_id: Optional[str] = Query(None),
    reason: str = Query(..., description="Reason for rescheduling"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> OperationResponse:
    """Reschedule a failed or cancelled operation"""
    
    result = await db.execute(
        select(ScheduledOperation).where(ScheduledOperation.id == operation_id)
    )
    
    operation = result.scalar_one_or_none()
    
    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation {operation_id} not found"
        )
    
    if operation.status not in ["failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only reschedule failed or cancelled operations"
        )
    
    # Update operation
    operation.operation_date = new_date
    operation.planned_start_time = new_time
    operation.planned_end_time = (
        datetime.combine(new_date, new_time) + 
        timedelta(minutes=operation.duration_minutes)
    ).time()
    
    if new_team_id:
        operation.team_id = new_team_id
        # Would need to update team_name from team data
    
    operation.status = "rescheduled"
    operation.reschedule_reason = reason
    operation.rescheduled_by = current_user.get("username", "unknown")
    operation.rescheduled_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(operation)
    
    return OperationResponse.from_orm(operation)


@router.get("/performance/summary", response_model=Dict[str, Any])
async def get_operation_performance_summary(
    schedule_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get operation performance metrics"""
    
    query = select(ScheduledOperation)
    
    if schedule_id:
        query = query.where(ScheduledOperation.schedule_id == schedule_id)
    
    if start_date:
        query = query.where(ScheduledOperation.operation_date >= start_date)
    
    if end_date:
        query = query.where(ScheduledOperation.operation_date <= end_date)
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    # Calculate metrics
    total = len(operations)
    completed = len([op for op in operations if op.status == "completed"])
    failed = len([op for op in operations if op.status == "failed"])
    in_progress = len([op for op in operations if op.status == "in_progress"])
    scheduled = len([op for op in operations if op.status == "scheduled"])
    
    # Calculate on-time performance
    on_time = 0
    delayed = 0
    
    for op in operations:
        if op.status == "completed" and op.actual_start_time and op.planned_start_time:
            planned = datetime.combine(op.operation_date, op.planned_start_time)
            actual = op.actual_start_time
            
            if actual <= planned + timedelta(minutes=30):
                on_time += 1
            else:
                delayed += 1
    
    return {
        "total_operations": total,
        "status_breakdown": {
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "scheduled": scheduled,
        },
        "completion_rate": (completed / total * 100) if total > 0 else 0,
        "failure_rate": (failed / total * 100) if total > 0 else 0,
        "on_time_performance": {
            "on_time": on_time,
            "delayed": delayed,
            "rate": (on_time / (on_time + delayed) * 100) if (on_time + delayed) > 0 else 0,
        },
    }