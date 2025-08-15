from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.deps import get_db, get_current_user, get_redis, verify_websocket_token
from ....core.redis import RedisClient
from ....core.logger import get_logger
from ....models.schedule import WeeklySchedule, ScheduledOperation
from ....schemas.monitoring import (
    ScheduleStatus, OperationProgress, TeamStatus,
    AlertMessage, PerformanceMetrics
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/active-schedule", response_model=Optional[ScheduleStatus])
async def get_active_schedule_status(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> Optional[ScheduleStatus]:
    """Get current active schedule status and progress"""
    
    # Get current week
    today = date.today()
    week_number = today.isocalendar()[1]
    year = today.year
    
    # Check Redis cache first
    cache_key = f"active_schedule:{year}:week_{week_number}"
    cached = await redis.get_json(cache_key)
    
    if not cached:
        # Query database
        result = await db.execute(
            select(WeeklySchedule)
            .where(
                and_(
                    WeeklySchedule.week_number == week_number,
                    WeeklySchedule.year == year,
                    WeeklySchedule.status == "active"
                )
            )
        )
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            return None
    else:
        # Get schedule from cache ID
        result = await db.execute(
            select(WeeklySchedule)
            .where(WeeklySchedule.id == cached["id"])
        )
        schedule = result.scalar_one_or_none()
    
    # Get operation statistics
    stats = await db.execute(
        select(
            ScheduledOperation.status,
            func.count(ScheduledOperation.id).label("count")
        )
        .where(ScheduledOperation.schedule_id == schedule.id)
        .group_by(ScheduledOperation.status)
    )
    
    status_counts = {row.status: row.count for row in stats}
    
    # Calculate progress
    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    in_progress = status_counts.get("in_progress", 0)
    
    progress_percent = (completed / total * 100) if total > 0 else 0
    
    return ScheduleStatus(
        schedule_id=schedule.id,
        schedule_code=schedule.schedule_code,
        week_number=schedule.week_number,
        year=schedule.year,
        status=schedule.status,
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        total_operations=total,
        completed_operations=completed,
        failed_operations=failed,
        in_progress_operations=in_progress,
        progress_percent=progress_percent,
        efficiency_percent=schedule.efficiency_percent,
        activated_at=schedule.activated_at,
        last_updated=datetime.utcnow(),
    )


@router.get("/operations/progress", response_model=List[OperationProgress])
async def get_operations_progress(
    schedule_id: Optional[UUID] = Query(None),
    date_filter: Optional[date] = Query(None),
    team_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[OperationProgress]:
    """Get real-time progress of operations"""
    
    query = select(ScheduledOperation)
    
    if schedule_id:
        query = query.where(ScheduledOperation.schedule_id == schedule_id)
    else:
        # Get active schedule operations
        today = date.today()
        query = query.where(ScheduledOperation.operation_date == today)
    
    if date_filter:
        query = query.where(ScheduledOperation.operation_date == date_filter)
    
    if team_id:
        query = query.where(ScheduledOperation.team_id == team_id)
    
    query = query.order_by(
        ScheduledOperation.operation_date,
        ScheduledOperation.planned_start_time
    )
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    progress_list = []
    for op in operations:
        # Calculate time-based progress for in-progress operations
        progress_percent = 0
        if op.status == "completed":
            progress_percent = 100
        elif op.status == "in_progress" and op.actual_start_time:
            elapsed = (datetime.utcnow() - op.actual_start_time).total_seconds() / 60
            progress_percent = min(100, (elapsed / op.duration_minutes) * 100)
        
        progress = OperationProgress(
            operation_id=op.id,
            gate_id=op.gate_id,
            gate_name=op.gate_name,
            team_id=op.team_id,
            team_name=op.team_name,
            status=op.status,
            progress_percent=progress_percent,
            planned_start=datetime.combine(op.operation_date, op.planned_start_time),
            actual_start=op.actual_start_time,
            planned_duration_minutes=op.duration_minutes,
            current_opening=op.current_opening_percent,
            target_opening=op.target_opening_percent,
            actual_opening=op.actual_opening_percent,
            location={
                "latitude": op.latitude,
                "longitude": op.longitude,
            },
            last_updated=op.updated_at or op.created_at,
        )
        progress_list.append(progress)
    
    return progress_list


@router.get("/teams/status", response_model=List[TeamStatus])
async def get_teams_status(
    redis: RedisClient = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[TeamStatus]:
    """Get current status of all active teams"""
    
    # Get all active teams
    result = await db.execute(
        select(FieldTeam).where(FieldTeam.is_active == True)
    )
    teams = result.scalars().all()
    
    status_list = []
    for team in teams:
        # Get current location from Redis
        location_key = f"team_location:{team.team_code}"
        location_data = await redis.get_json(location_key)
        
        # Get current assignment
        today = date.today()
        current_op_result = await db.execute(
            select(ScheduledOperation)
            .where(
                and_(
                    ScheduledOperation.team_id == team.team_code,
                    ScheduledOperation.operation_date == today,
                    ScheduledOperation.status == "in_progress"
                )
            )
            .limit(1)
        )
        current_op = current_op_result.scalar_one_or_none()
        
        # Count today's operations
        today_stats = await db.execute(
            select(
                func.count(ScheduledOperation.id).label("total"),
                func.sum(
                    func.cast(ScheduledOperation.status == "completed", Integer)
                ).label("completed")
            )
            .where(
                and_(
                    ScheduledOperation.team_id == team.team_code,
                    ScheduledOperation.operation_date == today
                )
            )
        )
        stats = today_stats.one()
        
        status = TeamStatus(
            team_id=team.team_code,
            team_name=team.team_name,
            status="active" if current_op else "idle",
            current_location=location_data if location_data else None,
            current_operation={
                "operation_id": str(current_op.id),
                "gate_id": current_op.gate_id,
                "gate_name": current_op.gate_name,
                "started_at": current_op.actual_start_time.isoformat() if current_op.actual_start_time else None,
            } if current_op else None,
            operations_today=stats.total or 0,
            operations_completed=stats.completed or 0,
            last_update=datetime.fromisoformat(location_data["timestamp"]) if location_data else None,
        )
        status_list.append(status)
    
    return status_list


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
):
    """
    WebSocket endpoint for real-time updates.
    
    Subscribes to:
    - Operation status changes
    - Team location updates
    - Schedule modifications
    - System alerts
    """
    
    # Verify token
    user = await verify_websocket_token(token, redis)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await websocket.accept()
    
    # Subscribe to Redis channels
    channels = [
        "operation_status:*",
        "team_tracking:*",
        "schedule_updates",
        "system_alerts",
    ]
    
    try:
        # Create pubsub connection
        pubsub = await redis.subscribe(channels)
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "user": user.get("username"),
        })
        
        # Listen for messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_json({
                    "channel": message["channel"],
                    "data": message["data"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user.get('username')}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        await pubsub.unsubscribe()


@router.get("/alerts", response_model=List[AlertMessage])
async def get_active_alerts(
    severity: Optional[str] = Query(None, enum=["info", "warning", "error", "critical"]),
    limit: int = Query(50, ge=1, le=200),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> List[AlertMessage]:
    """Get active system alerts"""
    
    # Get alerts from Redis
    alerts_key = "system_alerts:active"
    all_alerts = await redis.get_list(alerts_key)
    
    if not all_alerts:
        return []
    
    # Parse and filter alerts
    alerts = []
    for alert_data in all_alerts[:limit]:
        alert = AlertMessage(**alert_data)
        
        if severity and alert.severity != severity:
            continue
        
        alerts.append(alert)
    
    return alerts


@router.post("/alerts", response_model=AlertMessage)
async def create_alert(
    alert: AlertMessage,
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> AlertMessage:
    """Create a new system alert"""
    
    # Add metadata
    alert.id = str(UUID())
    alert.created_at = datetime.utcnow()
    alert.created_by = current_user.get("username", "unknown")
    
    # Store in Redis
    alerts_key = "system_alerts:active"
    await redis.add_to_list(alerts_key, alert.dict())
    
    # Publish for real-time subscribers
    await redis.publish("system_alerts", alert.dict())
    
    # Set expiry for auto-cleanup (24 hours for non-critical)
    if alert.severity != "critical":
        await redis.expire(f"alert:{alert.id}", 86400)
    
    return alert


@router.get("/performance/realtime", response_model=PerformanceMetrics)
async def get_realtime_performance(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> PerformanceMetrics:
    """Get real-time performance metrics"""
    
    # Get active schedule
    today = date.today()
    week_number = today.isocalendar()[1]
    year = today.year
    
    result = await db.execute(
        select(WeeklySchedule)
        .where(
            and_(
                WeeklySchedule.week_number == week_number,
                WeeklySchedule.year == year,
                WeeklySchedule.status == "active"
            )
        )
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        return PerformanceMetrics(
            schedule_id=None,
            water_delivery_efficiency=0,
            operation_completion_rate=0,
            on_time_performance=0,
            resource_utilization=0,
            current_flow_rate_m3s=0,
            target_flow_rate_m3s=0,
            active_gates=0,
            active_teams=0,
            last_updated=datetime.utcnow(),
        )
    
    # Calculate metrics
    # Get operation stats
    op_stats = await db.execute(
        select(
            func.count(ScheduledOperation.id).label("total"),
            func.sum(
                func.cast(ScheduledOperation.status == "completed", Integer)
            ).label("completed"),
            func.sum(
                func.cast(ScheduledOperation.status == "in_progress", Integer)
            ).label("in_progress"),
        )
        .where(
            and_(
                ScheduledOperation.schedule_id == schedule.id,
                ScheduledOperation.operation_date <= today
            )
        )
    )
    stats = op_stats.one()
    
    # Get flow data (would come from Flow Monitoring Service)
    current_flow = await redis.get_json("current_total_flow") or {"flow": 0}
    
    # Calculate metrics
    completion_rate = (stats.completed / stats.total * 100) if stats.total > 0 else 0
    
    # Get active gates count
    active_gates = await db.execute(
        select(func.count(func.distinct(ScheduledOperation.gate_id)))
        .where(
            and_(
                ScheduledOperation.schedule_id == schedule.id,
                ScheduledOperation.operation_date == today,
                ScheduledOperation.status.in_(["in_progress", "completed"])
            )
        )
    )
    
    # Get active teams count
    active_teams = await db.execute(
        select(func.count(func.distinct(ScheduledOperation.team_id)))
        .where(
            and_(
                ScheduledOperation.schedule_id == schedule.id,
                ScheduledOperation.operation_date == today,
                ScheduledOperation.status == "in_progress"
            )
        )
    )
    
    return PerformanceMetrics(
        schedule_id=schedule.id,
        water_delivery_efficiency=schedule.efficiency_percent,
        operation_completion_rate=completion_rate,
        on_time_performance=85.0,  # Would calculate from actual data
        resource_utilization=75.0,  # Would calculate from team capacity
        current_flow_rate_m3s=current_flow.get("flow", 0),
        target_flow_rate_m3s=schedule.total_water_demand_m3 / (7 * 24 * 3600),  # Weekly average
        active_gates=active_gates.scalar() or 0,
        active_teams=active_teams.scalar() or 0,
        last_updated=datetime.utcnow(),
    )


@router.get("/deviations", response_model=List[Dict[str, Any]])
async def get_schedule_deviations(
    threshold_minutes: int = Query(30, description="Deviation threshold in minutes"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get operations that deviate from schedule"""
    
    today = date.today()
    
    # Query operations with deviations
    result = await db.execute(
        select(ScheduledOperation)
        .where(
            and_(
                ScheduledOperation.operation_date == today,
                ScheduledOperation.status.in_(["completed", "in_progress"]),
                ScheduledOperation.actual_start_time != None
            )
        )
    )
    operations = result.scalars().all()
    
    deviations = []
    for op in operations:
        if op.actual_start_time and op.planned_start_time:
            planned = datetime.combine(op.operation_date, op.planned_start_time)
            actual = op.actual_start_time
            
            deviation_minutes = (actual - planned).total_seconds() / 60
            
            if abs(deviation_minutes) >= threshold_minutes:
                deviations.append({
                    "operation_id": str(op.id),
                    "gate_id": op.gate_id,
                    "gate_name": op.gate_name,
                    "team_id": op.team_id,
                    "planned_time": planned.isoformat(),
                    "actual_time": actual.isoformat(),
                    "deviation_minutes": deviation_minutes,
                    "status": op.status,
                    "impact": "high" if abs(deviation_minutes) > 60 else "medium",
                })
    
    return deviations