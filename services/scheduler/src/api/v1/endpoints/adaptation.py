from typing import Dict, List, Optional, Any
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.deps import get_db, get_current_user, get_redis
from ....core.redis import RedisClient
from ....core.logger import get_logger
from ....models.schedule import WeeklySchedule, ScheduledOperation
from ....schemas.adaptation import (
    AdaptationRequest, AdaptationResponse, AdaptationStrategy,
    GateFailureEvent, WeatherChangeEvent, DemandChangeEvent,
    ReoptimizationRequest, EmergencyOverride
)
from ....services.real_time_adapter import RealTimeAdapter
from ....services.clients import ROSClient, GISClient, FlowMonitoringClient

logger = get_logger(__name__)
router = APIRouter()


@router.post("/gate-failure", response_model=AdaptationResponse)
async def handle_gate_failure(
    event: GateFailureEvent,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> AdaptationResponse:
    """
    Handle automated gate failure and adapt schedule.
    
    This endpoint:
    1. Marks affected operations as failed
    2. Calculates impact on water delivery
    3. Identifies alternative gates
    4. Reschedules operations
    5. Notifies affected teams
    """
    
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active schedule found"
        )
    
    # Initialize adapter
    ros_client = ROSClient()
    gis_client = GISClient()
    flow_client = FlowMonitoringClient()
    
    adapter = RealTimeAdapter(db, redis, ros_client, gis_client, flow_client)
    
    # Handle gate failure
    adaptation = await adapter.handle_gate_failure(
        schedule_id=schedule.id,
        gate_id=event.gate_id,
        failure_type=event.failure_type,
        estimated_repair_hours=event.estimated_repair_hours,
        timestamp=event.timestamp or datetime.utcnow()
    )
    
    return AdaptationResponse(
        adaptation_id=adaptation["id"],
        event_type="gate_failure",
        event_data=event.dict(),
        strategy=adaptation["strategy"],
        affected_operations=adaptation["affected_operations"],
        new_operations=adaptation["new_operations"],
        impact_assessment={
            "water_shortage_m3": adaptation["water_impact"],
            "affected_zones": adaptation["affected_zones"],
            "delay_hours": adaptation["delay_hours"],
        },
        notifications_sent=adaptation["notifications"],
        timestamp=datetime.utcnow(),
    )


@router.post("/weather-change", response_model=AdaptationResponse)
async def handle_weather_change(
    event: WeatherChangeEvent,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> AdaptationResponse:
    """
    Handle weather changes and adapt irrigation schedule.
    
    Adjusts water demands based on:
    - Rainfall events (reduce irrigation)
    - Temperature changes (adjust ET rates)
    - Wind conditions (adjust application efficiency)
    """
    
    # Get active schedule
    result = await db.execute(
        select(WeeklySchedule)
        .where(WeeklySchedule.status == "active")
        .order_by(WeeklySchedule.created_at.desc())
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active schedule found"
        )
    
    # Initialize adapter
    ros_client = ROSClient()
    gis_client = GISClient()
    flow_client = FlowMonitoringClient()
    
    adapter = RealTimeAdapter(db, redis, ros_client, gis_client, flow_client)
    
    # Handle weather change
    adaptation = await adapter.handle_weather_change(
        schedule_id=schedule.id,
        weather_data=event.dict()
    )
    
    # Determine strategy based on changes
    strategy = AdaptationStrategy.NONE
    if event.rainfall_mm > 10:
        strategy = AdaptationStrategy.REDUCE_DEMAND
    elif event.temperature_change > 5:
        strategy = AdaptationStrategy.ADJUST_TIMING
    
    return AdaptationResponse(
        adaptation_id=adaptation["id"],
        event_type="weather_change",
        event_data=event.dict(),
        strategy=strategy,
        affected_operations=adaptation["affected_operations"],
        new_operations=adaptation.get("modified_operations", []),
        impact_assessment={
            "demand_adjustment_percent": adaptation["demand_adjustment"],
            "water_saved_m3": adaptation["water_saved"],
            "operations_modified": len(adaptation["affected_operations"]),
        },
        notifications_sent=adaptation["notifications"],
        timestamp=datetime.utcnow(),
    )


@router.post("/demand-change", response_model=AdaptationResponse)
async def handle_demand_change(
    event: DemandChangeEvent,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> AdaptationResponse:
    """
    Handle sudden demand changes (e.g., emergency water requests).
    
    This can be triggered by:
    - Farmer requests for additional water
    - Crop stress detection
    - Emergency situations
    """
    
    # Validate active schedule
    result = await db.execute(
        select(WeeklySchedule).where(WeeklySchedule.status == "active")
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active schedule found"
        )
    
    # Initialize adapter
    ros_client = ROSClient()
    gis_client = GISClient()
    flow_client = FlowMonitoringClient()
    
    adapter = RealTimeAdapter(db, redis, ros_client, gis_client, flow_client)
    
    # Handle demand change
    adaptation = await adapter.handle_demand_change(
        schedule_id=schedule.id,
        zone_id=event.zone_id,
        plot_ids=event.plot_ids,
        demand_change_m3=event.additional_demand_m3,
        urgency=event.urgency,
        reason=event.reason
    )
    
    # Determine strategy
    strategy = AdaptationStrategy.INCREASE_FLOW
    if event.urgency == "emergency":
        strategy = AdaptationStrategy.EMERGENCY_OVERRIDE
    
    return AdaptationResponse(
        adaptation_id=adaptation["id"],
        event_type="demand_change",
        event_data=event.dict(),
        strategy=strategy,
        affected_operations=adaptation["affected_operations"],
        new_operations=adaptation["new_operations"],
        impact_assessment={
            "additional_water_m3": event.additional_demand_m3,
            "gates_adjusted": len(adaptation["gates_adjusted"]),
            "delivery_time": adaptation["estimated_delivery_time"],
        },
        notifications_sent=adaptation["notifications"],
        timestamp=datetime.utcnow(),
    )


@router.post("/reoptimize", response_model=Dict[str, Any])
async def reoptimize_schedule(
    request: ReoptimizationRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Trigger full reoptimization of remaining schedule.
    
    Use when:
    - Multiple failures/changes accumulate
    - Manual intervention is needed
    - Significant deviation from plan
    """
    
    # Get schedule
    result = await db.execute(
        select(WeeklySchedule).where(WeeklySchedule.id == request.schedule_id)
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {request.schedule_id} not found"
        )
    
    if schedule.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only reoptimize active schedules"
        )
    
    # Get remaining operations
    remaining_ops = await db.execute(
        select(ScheduledOperation)
        .where(
            and_(
                ScheduledOperation.schedule_id == schedule.id,
                ScheduledOperation.status == "scheduled",
                ScheduledOperation.operation_date >= request.from_date
            )
        )
    )
    operations = remaining_ops.scalars().all()
    
    # Initialize services
    ros_client = ROSClient()
    gis_client = GISClient()
    flow_client = FlowMonitoringClient()
    
    adapter = RealTimeAdapter(db, redis, ros_client, gis_client, flow_client)
    
    # Trigger reoptimization
    result = await adapter.reoptimize_schedule(
        schedule_id=schedule.id,
        from_date=request.from_date,
        constraints=request.constraints,
        reason=request.reason
    )
    
    return {
        "status": "success",
        "schedule_id": str(schedule.id),
        "operations_reoptimized": len(operations),
        "new_version": result["new_version"],
        "changes_summary": result["changes"],
        "optimization_metrics": result["metrics"],
        "initiated_by": current_user.get("username", "unknown"),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/emergency-override", response_model=Dict[str, Any])
async def emergency_override(
    override: EmergencyOverride,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Emergency override for immediate gate control.
    
    Bypasses schedule for emergency situations:
    - Flooding risk
    - Infrastructure damage
    - Safety concerns
    """
    
    # Validate authorization
    if not current_user.get("roles", []).intersection(["admin", "emergency_operator"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for emergency override"
        )
    
    # Log emergency action
    logger.warning(
        f"EMERGENCY OVERRIDE: Gate {override.gate_id} to {override.target_opening}% "
        f"by {current_user.get('username')} - Reason: {override.reason}"
    )
    
    # Send immediate command to Flow Monitoring Service
    flow_client = FlowMonitoringClient()
    
    try:
        # Execute override
        result = await flow_client.emergency_gate_control(
            gate_id=override.gate_id,
            target_opening=override.target_opening,
            override_safety=override.override_safety_checks,
            operator=current_user.get("username", "unknown"),
            reason=override.reason
        )
        
        # Update any affected scheduled operations
        await db.execute(
            update(ScheduledOperation)
            .where(
                and_(
                    ScheduledOperation.gate_id == override.gate_id,
                    ScheduledOperation.operation_date == date.today(),
                    ScheduledOperation.status.in_(["scheduled", "in_progress"])
                )
            )
            .values(
                status="overridden",
                override_reason=override.reason,
                updated_by=current_user.get("username", "unknown")
            )
        )
        
        await db.commit()
        
        # Send alerts
        alert = {
            "type": "emergency_override",
            "severity": "critical",
            "gate_id": override.gate_id,
            "action": f"Gate set to {override.target_opening}%",
            "operator": current_user.get("username"),
            "reason": override.reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await redis.publish("system_alerts", alert)
        
        return {
            "status": "executed",
            "gate_id": override.gate_id,
            "previous_opening": result.get("previous_opening"),
            "new_opening": override.target_opening,
            "execution_time": result.get("execution_time"),
            "alerts_sent": True,
            "operator": current_user.get("username"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Emergency override failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency override failed: {str(e)}"
        )


@router.get("/adaptation-history", response_model=List[Dict[str, Any]])
async def get_adaptation_history(
    schedule_id: Optional[UUID] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get history of schedule adaptations"""
    
    # Get from Redis (would be in database in production)
    history_key = f"adaptation_history:{schedule_id}" if schedule_id else "adaptation_history:all"
    
    history = await redis.get_list(history_key)
    
    if not history:
        return []
    
    # Filter and format
    filtered = []
    for entry in history[:limit]:
        if event_type and entry.get("event_type") != event_type:
            continue
        
        filtered.append({
            "adaptation_id": entry.get("id"),
            "schedule_id": entry.get("schedule_id"),
            "event_type": entry.get("event_type"),
            "event_data": entry.get("event_data"),
            "strategy": entry.get("strategy"),
            "operations_affected": entry.get("operations_affected", 0),
            "impact": entry.get("impact"),
            "timestamp": entry.get("timestamp"),
            "triggered_by": entry.get("triggered_by", "system"),
        })
    
    return filtered


@router.get("/recommendations", response_model=List[Dict[str, Any]])
async def get_adaptation_recommendations(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
    current_user: Dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get AI-powered recommendations for schedule improvements.
    
    Analyzes:
    - Historical performance
    - Current deviations
    - Weather forecasts
    - System constraints
    """
    
    recommendations = []
    
    # Get active schedule
    result = await db.execute(
        select(WeeklySchedule).where(WeeklySchedule.status == "active")
    )
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        return []
    
    # Analyze current performance
    performance = await redis.get_json(f"schedule_performance:{schedule.id}")
    
    if performance:
        # Check completion rate
        if performance.get("completion_rate", 100) < 80:
            recommendations.append({
                "type": "performance",
                "severity": "medium",
                "title": "Low completion rate detected",
                "description": f"Only {performance['completion_rate']:.1f}% of operations completed on time",
                "recommendation": "Consider reducing daily operation targets or adding more field teams",
                "potential_impact": "Improve completion rate by 15-20%",
            })
        
        # Check water efficiency
        if schedule.efficiency_percent < 85:
            recommendations.append({
                "type": "efficiency",
                "severity": "medium",
                "title": "Water delivery efficiency below target",
                "description": f"Current efficiency: {schedule.efficiency_percent:.1f}%",
                "recommendation": "Review gate opening sequences and timing to reduce transit losses",
                "potential_impact": f"Save up to {(100-schedule.efficiency_percent)*schedule.total_water_demand_m3/100:.0f} m³",
            })
    
    # Weather-based recommendations
    weather_forecast = await redis.get_json("weather_forecast:7day")
    if weather_forecast and weather_forecast.get("rain_probability", 0) > 0.6:
        recommendations.append({
            "type": "weather",
            "severity": "low",
            "title": "Rain expected in next 7 days",
            "description": f"Rain probability: {weather_forecast['rain_probability']*100:.0f}%",
            "recommendation": "Consider reducing irrigation in rain-affected areas",
            "potential_impact": "Reduce water use by 20-30% in affected zones",
        })
    
    return recommendations