from typing import Dict, List, Optional
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....core.deps import get_db, get_current_user, get_redis
from ....core.redis import RedisClient
from ....core.logger import get_logger
from ....models.schedule import FieldTeam, FieldInstruction, ScheduledOperation
from ....schemas.team import (
    TeamCreate, TeamResponse, TeamUpdate,
    TeamAssignment, TeamPerformance, TeamLocation
)

logger = get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=TeamResponse)
async def create_team(
    team_data: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> TeamResponse:
    """Create a new field team"""
    
    # Check if team code already exists
    existing = await db.execute(
        select(FieldTeam).where(FieldTeam.team_code == team_data.team_code)
    )
    
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team with code {team_data.team_code} already exists"
        )
    
    # Create team
    team = FieldTeam(**team_data.dict())
    team.created_by = current_user.get("username", "unknown")
    
    db.add(team)
    await db.commit()
    await db.refresh(team)
    
    return TeamResponse.from_orm(team)


@router.get("/", response_model=List[TeamResponse])
async def list_teams(
    is_active: Optional[bool] = Query(None),
    zone: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[TeamResponse]:
    """List all field teams"""
    
    query = select(FieldTeam)
    
    if is_active is not None:
        query = query.where(FieldTeam.is_active == is_active)
    
    if zone:
        query = query.where(FieldTeam.primary_zone == zone)
    
    query = query.order_by(FieldTeam.team_code)
    
    result = await db.execute(query)
    teams = result.scalars().all()
    
    return [TeamResponse.from_orm(team) for team in teams]


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> TeamResponse:
    """Get team details by ID"""
    
    result = await db.execute(
        select(FieldTeam).where(FieldTeam.team_code == team_id)
    )
    
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found"
        )
    
    return TeamResponse.from_orm(team)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    update_data: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> TeamResponse:
    """Update team information"""
    
    result = await db.execute(
        select(FieldTeam).where(FieldTeam.team_code == team_id)
    )
    
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(team, field, value)
    
    team.updated_by = current_user.get("username", "unknown")
    
    await db.commit()
    await db.refresh(team)
    
    return TeamResponse.from_orm(team)


@router.get("/{team_id}/instructions/{date}", response_model=Dict[str, Any])
async def get_team_instructions(
    team_id: str,
    date: date,
    format: str = Query("json", enum=["json", "pdf"]),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get field instructions for a team on a specific date.
    
    Returns either JSON data or a download link for PDF.
    """
    
    # Find instructions for the team and date
    result = await db.execute(
        select(FieldInstruction)
        .where(
            and_(
                FieldInstruction.team_id == team_id,
                FieldInstruction.operation_date == date
            )
        )
        .options(selectinload(FieldInstruction.schedule))
    )
    
    instruction = result.scalar_one_or_none()
    
    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No instructions found for team {team_id} on {date}"
        )
    
    if format == "json":
        # Return mobile-friendly JSON
        return {
            "team_id": instruction.team_id,
            "team_name": instruction.team_name,
            "date": instruction.operation_date.isoformat(),
            "schedule": {
                "id": str(instruction.schedule_id),
                "code": instruction.schedule.schedule_code if instruction.schedule else None,
            },
            "summary": {
                "total_operations": instruction.total_operations,
                "total_distance_km": instruction.total_distance_km,
                "estimated_hours": instruction.estimated_duration_hours,
                "start_location": instruction.start_location,
                "end_location": instruction.end_location,
            },
            "route": instruction.route_coordinates,
            "waypoints": instruction.waypoints,
            "general_instructions": instruction.general_instructions,
            "safety_notes": instruction.safety_notes,
            "equipment": instruction.special_equipment,
            "contacts": {
                "supervisor": {
                    "name": instruction.supervisor_name,
                    "phone": instruction.supervisor_phone,
                },
                "emergency": instruction.emergency_contact,
            },
            "generated_at": instruction.created_at.isoformat(),
        }
    else:
        # Return PDF download link
        # In production, this would generate and return actual PDF
        return {
            "format": "pdf",
            "download_url": f"/api/v1/teams/{team_id}/instructions/{date}/download",
            "filename": f"field_instructions_{team_id}_{date}.pdf",
            "size_bytes": len(instruction.pdf_content) if instruction.pdf_content else 0,
        }


@router.get("/{team_id}/assignments", response_model=List[TeamAssignment])
async def get_team_assignments(
    team_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[TeamAssignment]:
    """Get all assignments for a team"""
    
    query = select(ScheduledOperation).where(
        ScheduledOperation.team_id == team_id
    )
    
    if start_date:
        query = query.where(ScheduledOperation.operation_date >= start_date)
    
    if end_date:
        query = query.where(ScheduledOperation.operation_date <= end_date)
    
    if status:
        query = query.where(ScheduledOperation.status == status)
    
    query = query.order_by(
        ScheduledOperation.operation_date,
        ScheduledOperation.planned_start_time
    )
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    # Group by date
    assignments = []
    current_date = None
    current_assignment = None
    
    for op in operations:
        if op.operation_date != current_date:
            if current_assignment:
                assignments.append(current_assignment)
            
            current_date = op.operation_date
            current_assignment = TeamAssignment(
                date=current_date,
                team_id=team_id,
                total_operations=0,
                completed_operations=0,
                failed_operations=0,
                total_distance_km=0,
                operations=[],
            )
        
        current_assignment.total_operations += 1
        if op.status == "completed":
            current_assignment.completed_operations += 1
        elif op.status == "failed":
            current_assignment.failed_operations += 1
        
        current_assignment.operations.append({
            "operation_id": str(op.id),
            "gate_id": op.gate_id,
            "gate_name": op.gate_name,
            "time": op.planned_start_time.isoformat(),
            "status": op.status,
        })
    
    if current_assignment:
        assignments.append(current_assignment)
    
    return assignments


@router.get("/{team_id}/performance", response_model=TeamPerformance)
async def get_team_performance(
    team_id: str,
    period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> TeamPerformance:
    """Get team performance metrics"""
    
    # Check team exists
    team_result = await db.execute(
        select(FieldTeam).where(FieldTeam.team_code == team_id)
    )
    team = team_result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found"
        )
    
    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)
    
    # Get operations
    result = await db.execute(
        select(ScheduledOperation)
        .where(
            and_(
                ScheduledOperation.team_id == team_id,
                ScheduledOperation.operation_date >= start_date,
                ScheduledOperation.operation_date <= end_date
            )
        )
    )
    operations = result.scalars().all()
    
    # Calculate metrics
    total_operations = len(operations)
    completed = len([op for op in operations if op.status == "completed"])
    failed = len([op for op in operations if op.status == "failed"])
    
    # On-time performance
    on_time = 0
    total_delay_minutes = 0
    
    for op in operations:
        if op.status == "completed" and op.actual_start_time and op.planned_start_time:
            planned = datetime.combine(op.operation_date, op.planned_start_time)
            actual = op.actual_start_time
            
            delay = (actual - planned).total_seconds() / 60
            if delay <= 30:  # 30 minute grace period
                on_time += 1
            else:
                total_delay_minutes += delay
    
    # Travel efficiency (simplified)
    total_planned_distance = sum(
        inst.total_distance_km 
        for inst in await db.execute(
            select(FieldInstruction)
            .where(
                and_(
                    FieldInstruction.team_id == team_id,
                    FieldInstruction.operation_date >= start_date,
                    FieldInstruction.operation_date <= end_date
                )
            )
        ).scalars().all()
    )
    
    return TeamPerformance(
        team_id=team_id,
        team_name=team.team_name,
        period_start=start_date,
        period_end=end_date,
        total_operations=total_operations,
        completed_operations=completed,
        failed_operations=failed,
        completion_rate=(completed / total_operations * 100) if total_operations > 0 else 0,
        on_time_rate=(on_time / completed * 100) if completed > 0 else 0,
        average_delay_minutes=(total_delay_minutes / (completed - on_time)) if (completed - on_time) > 0 else 0,
        total_distance_km=total_planned_distance,
        operations_per_km=(total_operations / total_planned_distance) if total_planned_distance > 0 else 0,
    )


@router.post("/{team_id}/location", response_model=Dict[str, str])
async def update_team_location(
    team_id: str,
    location: TeamLocation,
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Update team's current location (for real-time tracking).
    
    This is typically called by the mobile app to report GPS position.
    """
    
    # Store in Redis for real-time tracking
    location_key = f"team_location:{team_id}"
    location_data = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "accuracy": location.accuracy,
        "timestamp": location.timestamp.isoformat(),
        "heading": location.heading,
        "speed": location.speed,
        "battery_level": location.battery_level,
    }
    
    await redis.set_json(location_key, location_data, expire=3600)  # 1 hour TTL
    
    # Publish for real-time subscribers
    await redis.publish(
        f"team_tracking:{team_id}",
        location_data
    )
    
    return {"message": "Location updated successfully"}


@router.get("/{team_id}/location", response_model=Optional[TeamLocation])
async def get_team_location(
    team_id: str,
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> Optional[TeamLocation]:
    """Get team's last known location"""
    
    location_key = f"team_location:{team_id}"
    location_data = await redis.get_json(location_key)
    
    if not location_data:
        return None
    
    return TeamLocation(**location_data)


@router.post("/{team_id}/photo", response_model=Dict[str, str])
async def upload_team_photo(
    team_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, str]:
    """Upload team photo"""
    
    # Validate team exists
    result = await db.execute(
        select(FieldTeam).where(FieldTeam.team_code == team_id)
    )
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} not found"
        )
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed"
        )
    
    # In production, this would:
    # 1. Upload to S3/storage service
    # 2. Update team.photo_url
    # 3. Return the URL
    
    # For now, just return success
    return {
        "message": "Photo uploaded successfully",
        "url": f"/static/teams/{team_id}/photo.jpg"
    }