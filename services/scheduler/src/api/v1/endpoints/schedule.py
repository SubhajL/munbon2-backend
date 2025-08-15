from typing import Dict, List, Optional, Any
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.deps import get_db, get_current_user, get_redis
from ....core.redis import RedisClient
from ....core.logger import get_logger
from ....models.schedule import WeeklySchedule, ScheduledOperation
from ....schemas.schedule import (
    ScheduleCreate, ScheduleResponse, ScheduleUpdate,
    ScheduleGenerateRequest, ScheduleSummary
)
from ....services.schedule_optimizer import ScheduleOptimizer
from ....services.clients import ROSClient, GISClient, FlowMonitoringClient

logger = get_logger(__name__)
router = APIRouter()


@router.post("/generate", response_model=ScheduleResponse)
async def generate_schedule(
    request: ScheduleGenerateRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> ScheduleResponse:
    """
    Generate an optimized weekly schedule.
    
    This endpoint:
    1. Aggregates water demands from ROS service
    2. Retrieves network topology from GIS/Flow services
    3. Runs MILP optimization
    4. Creates schedule with field instructions
    5. Returns the draft schedule for review
    """
    try:
        # Check if schedule already exists
        existing = await db.execute(
            select(WeeklySchedule).where(
                and_(
                    WeeklySchedule.week_number == request.week_number,
                    WeeklySchedule.year == request.year,
                    WeeklySchedule.status.in_(["draft", "approved", "active"])
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Schedule for week {request.week_number}, {request.year} already exists"
            )
        
        # Initialize service clients
        ros_client = ROSClient()
        gis_client = GISClient()
        flow_client = FlowMonitoringClient()
        
        # Initialize optimizer
        optimizer = ScheduleOptimizer(
            db, redis, ros_client, gis_client, flow_client
        )
        
        # Generate schedule
        schedule = await optimizer.generate_weekly_schedule(
            week_number=request.week_number,
            year=request.year,
            constraints=request.constraints
        )
        
        # Convert to response
        return ScheduleResponse.from_orm(schedule)
        
    except Exception as e:
        logger.error(f"Failed to generate schedule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate schedule: {str(e)}"
        )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    include_operations: bool = Query(True, description="Include detailed operations"),
    include_instructions: bool = Query(False, description="Include field instructions"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> ScheduleResponse:
    """Get schedule details by ID"""
    
    # Build query
    query = select(WeeklySchedule).where(WeeklySchedule.id == schedule_id)
    
    if include_operations:
        query = query.options(selectinload(WeeklySchedule.operations))
    
    if include_instructions:
        query = query.options(selectinload(WeeklySchedule.field_instructions))
    
    result = await db.execute(query)
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    return ScheduleResponse.from_orm(schedule)


@router.get("/week/{week_number}/{year}", response_model=ScheduleResponse)
async def get_schedule_by_week(
    week_number: int = Query(..., ge=1, le=53),
    year: int = Query(..., ge=2024, le=2030),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> ScheduleResponse:
    """Get schedule for a specific week"""
    
    result = await db.execute(
        select(WeeklySchedule)
        .where(
            and_(
                WeeklySchedule.week_number == week_number,
                WeeklySchedule.year == year,
                WeeklySchedule.status.in_(["draft", "approved", "active"])
            )
        )
        .options(
            selectinload(WeeklySchedule.operations),
            selectinload(WeeklySchedule.field_instructions)
        )
        .order_by(WeeklySchedule.version.desc())
    )
    
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No schedule found for week {week_number}, {year}"
        )
    
    return ScheduleResponse.from_orm(schedule)


@router.get("/", response_model=List[ScheduleSummary])
async def list_schedules(
    status: Optional[str] = Query(None, description="Filter by status"),
    year: Optional[int] = Query(None, description="Filter by year"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[ScheduleSummary]:
    """List schedules with filtering"""
    
    query = select(WeeklySchedule)
    
    if status:
        query = query.where(WeeklySchedule.status == status)
    
    if year:
        query = query.where(WeeklySchedule.year == year)
    
    query = query.order_by(
        WeeklySchedule.year.desc(),
        WeeklySchedule.week_number.desc()
    ).limit(limit).offset(offset)
    
    result = await db.execute(query)
    schedules = result.scalars().all()
    
    return [ScheduleSummary.from_orm(s) for s in schedules]


@router.post("/{schedule_id}/approve", response_model=ScheduleResponse)
async def approve_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> ScheduleResponse:
    """
    Approve a draft schedule for execution.
    
    This will:
    1. Change status to 'approved'
    2. Notify all assigned field teams
    3. Enable the schedule for real-time monitoring
    """
    
    # Initialize service clients
    ros_client = ROSClient()
    gis_client = GISClient()
    flow_client = FlowMonitoringClient()
    
    # Initialize optimizer (for approval logic)
    optimizer = ScheduleOptimizer(
        db, redis, ros_client, gis_client, flow_client
    )
    
    try:
        schedule = await optimizer.approve_schedule(
            schedule_id,
            approver=current_user.get("username", "unknown")
        )
        
        return ScheduleResponse.from_orm(schedule)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to approve schedule: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve schedule"
        )


@router.post("/{schedule_id}/activate", response_model=ScheduleResponse)
async def activate_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> ScheduleResponse:
    """
    Activate an approved schedule for execution.
    
    This will:
    1. Change status to 'active'
    2. Deactivate any other active schedules for the same week
    3. Start real-time monitoring
    """
    
    result = await db.execute(
        select(WeeklySchedule).where(WeeklySchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    if schedule.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only approved schedules can be activated"
        )
    
    # Deactivate other schedules for the same week
    await db.execute(
        update(WeeklySchedule)
        .where(
            and_(
                WeeklySchedule.week_number == schedule.week_number,
                WeeklySchedule.year == schedule.year,
                WeeklySchedule.status == "active",
                WeeklySchedule.id != schedule_id
            )
        )
        .values(status="completed")
    )
    
    # Activate this schedule
    schedule.status = "active"
    schedule.activated_at = datetime.utcnow()
    schedule.updated_by = current_user.get("username", "unknown")
    
    await db.commit()
    await db.refresh(schedule)
    
    # Start monitoring
    await redis.set_json(
        f"active_schedule:{schedule.year}:week_{schedule.week_number}",
        {
            "id": str(schedule.id),
            "code": schedule.schedule_code,
            "activated_at": schedule.activated_at.isoformat(),
        }
    )
    
    return ScheduleResponse.from_orm(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    update_data: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> ScheduleResponse:
    """Update schedule metadata"""
    
    result = await db.execute(
        select(WeeklySchedule).where(WeeklySchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    if schedule.status not in ["draft"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update draft schedules"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(schedule, field, value)
    
    schedule.updated_by = current_user.get("username", "unknown")
    
    await db.commit()
    await db.refresh(schedule)
    
    return ScheduleResponse.from_orm(schedule)


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, str]:
    """Delete a draft schedule"""
    
    result = await db.execute(
        select(WeeklySchedule).where(WeeklySchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    if schedule.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete draft schedules"
        )
    
    await db.delete(schedule)
    await db.commit()
    
    return {"message": f"Schedule {schedule_id} deleted successfully"}


@router.post("/{schedule_id}/clone", response_model=ScheduleResponse)
async def clone_schedule(
    schedule_id: UUID,
    target_week: int = Query(..., ge=1, le=53),
    target_year: int = Query(..., ge=2024, le=2030),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> ScheduleResponse:
    """Clone an existing schedule to a new week"""
    
    # Get source schedule
    result = await db.execute(
        select(WeeklySchedule)
        .where(WeeklySchedule.id == schedule_id)
        .options(
            selectinload(WeeklySchedule.operations),
            selectinload(WeeklySchedule.field_instructions)
        )
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    # Check if target week already has a schedule
    existing = await db.execute(
        select(WeeklySchedule).where(
            and_(
                WeeklySchedule.week_number == target_week,
                WeeklySchedule.year == target_year,
                WeeklySchedule.status.in_(["draft", "approved", "active"])
            )
        )
    )
    
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule for week {target_week}, {target_year} already exists"
        )
    
    # Create cloned schedule
    new_schedule = WeeklySchedule(
        schedule_code=f"SCH-{target_year}-W{target_week:02d}",
        week_number=target_week,
        year=target_year,
        status="draft",
        version=1,
        # Copy relevant fields
        total_water_demand_m3=source.total_water_demand_m3,
        field_days=source.field_days,
        optimization_constraints=source.optimization_constraints,
        created_by=current_user.get("username", "unknown"),
    )
    
    # Note: Operations and instructions would need date adjustments
    # This is a simplified clone that creates a new draft based on the source
    
    db.add(new_schedule)
    await db.commit()
    await db.refresh(new_schedule)
    
    return ScheduleResponse.from_orm(new_schedule)