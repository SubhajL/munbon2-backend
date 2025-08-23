import strawberry
from typing import AsyncGenerator, Optional
import asyncio
import redis.asyncio as redis
import json
from datetime import datetime

from ..context import GraphQLContext
from config import settings
from core import get_logger

logger = get_logger(__name__)


@strawberry.type
class DemandUpdate:
    """Real-time demand calculation update"""
    section_id: str
    level_type: str  # plot, section, zone
    method: str  # ROS, RID-MS
    gross_demand_m3: float
    net_demand_m3: float
    calculation_time: datetime
    trigger: str  # scheduled, manual, rainfall_update


@strawberry.type
class AWDRecommendation:
    """Real-time AWD recommendation"""
    zone_id: str
    plot_id: Optional[str]
    recommended_state: str  # activate, deactivate, maintain
    moisture_level: Optional[float]
    reason: str
    expected_impact_m3: float
    timestamp: datetime


@strawberry.type
class CalculationProgress:
    """Progress update for long-running calculations"""
    job_id: str
    job_type: str  # demand_calculation, what_if_scenario, optimization
    percentage: float
    current_step: str
    estimated_completion: Optional[datetime]
    message: str


@strawberry.type
class SystemAlert:
    """System-wide alerts"""
    alert_id: str
    severity: str  # info, warning, critical
    category: str  # demand, supply, infrastructure, weather
    title: str
    message: str
    affected_zones: list[str]
    timestamp: datetime


@strawberry.type
class Subscription:
    """GraphQL subscriptions for real-time updates"""
    
    @strawberry.subscription
    async def demand_updates(
        self,
        info: strawberry.Info[GraphQLContext],
        section_id: Optional[str] = None,
        zone_id: Optional[str] = None
    ) -> AsyncGenerator[DemandUpdate, None]:
        """Subscribe to real-time demand calculation updates"""
        redis_client = await redis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        
        # Subscribe to appropriate channels
        channels = []
        if section_id:
            channels.append(f"demand:section:{section_id}")
        if zone_id:
            channels.append(f"demand:zone:{zone_id}")
        if not channels:
            channels.append("demand:all")  # Subscribe to all updates
        
        await pubsub.subscribe(*channels)
        
        logger.info(
            "Subscription started",
            type="demand_updates",
            channels=channels,
            client_type=info.context.client_type
        )
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield DemandUpdate(
                            section_id=data["section_id"],
                            level_type=data["level_type"],
                            method=data["method"],
                            gross_demand_m3=data["gross_demand_m3"],
                            net_demand_m3=data["net_demand_m3"],
                            calculation_time=datetime.fromisoformat(data["calculation_time"]),
                            trigger=data.get("trigger", "unknown")
                        )
                    except Exception as e:
                        logger.error("Failed to parse demand update", error=str(e))
        finally:
            await pubsub.unsubscribe(*channels)
            await redis_client.close()
    
    @strawberry.subscription
    async def awd_recommendations(
        self,
        info: strawberry.Info[GraphQLContext],
        zone_id: str
    ) -> AsyncGenerator[AWDRecommendation, None]:
        """Subscribe to AWD recommendation changes"""
        redis_client = await redis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        
        channel = f"awd:zone:{zone_id}"
        await pubsub.subscribe(channel)
        
        logger.info(
            "Subscription started",
            type="awd_recommendations",
            zone_id=zone_id,
            client_type=info.context.client_type
        )
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield AWDRecommendation(
                            zone_id=zone_id,
                            plot_id=data.get("plot_id"),
                            recommended_state=data["recommended_state"],
                            moisture_level=data.get("moisture_level"),
                            reason=data["reason"],
                            expected_impact_m3=data.get("expected_impact_m3", 0),
                            timestamp=datetime.fromisoformat(data["timestamp"])
                        )
                    except Exception as e:
                        logger.error("Failed to parse AWD recommendation", error=str(e))
        finally:
            await pubsub.unsubscribe(channel)
            await redis_client.close()
    
    @strawberry.subscription
    async def calculation_progress(
        self,
        info: strawberry.Info[GraphQLContext],
        job_id: str
    ) -> AsyncGenerator[CalculationProgress, None]:
        """Track progress of long-running calculations"""
        redis_client = await redis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        
        channel = f"job:progress:{job_id}"
        await pubsub.subscribe(channel)
        
        logger.info(
            "Subscription started",
            type="calculation_progress",
            job_id=job_id,
            client_type=info.context.client_type
        )
        
        try:
            # Send initial status
            yield CalculationProgress(
                job_id=job_id,
                job_type="initializing",
                percentage=0.0,
                current_step="Starting calculation",
                estimated_completion=None,
                message="Job initialized"
            )
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        
                        # Check if job is complete
                        if data.get("status") == "complete":
                            yield CalculationProgress(
                                job_id=job_id,
                                job_type=data["job_type"],
                                percentage=100.0,
                                current_step="Complete",
                                estimated_completion=datetime.now(),
                                message=data.get("message", "Job completed successfully")
                            )
                            break
                        
                        yield CalculationProgress(
                            job_id=job_id,
                            job_type=data["job_type"],
                            percentage=data["percentage"],
                            current_step=data["current_step"],
                            estimated_completion=datetime.fromisoformat(data["eta"]) if data.get("eta") else None,
                            message=data.get("message", "")
                        )
                    except Exception as e:
                        logger.error("Failed to parse progress update", error=str(e))
        finally:
            await pubsub.unsubscribe(channel)
            await redis_client.close()
    
    @strawberry.subscription
    async def system_alerts(
        self,
        info: strawberry.Info[GraphQLContext],
        severity_filter: Optional[str] = None,
        category_filter: Optional[str] = None
    ) -> AsyncGenerator[SystemAlert, None]:
        """Subscribe to system-wide alerts"""
        redis_client = await redis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        
        # Subscribe to alert channel
        await pubsub.subscribe("alerts:system")
        
        logger.info(
            "Subscription started",
            type="system_alerts",
            severity_filter=severity_filter,
            category_filter=category_filter,
            client_type=info.context.client_type
        )
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        
                        # Apply filters
                        if severity_filter and data["severity"] != severity_filter:
                            continue
                        if category_filter and data["category"] != category_filter:
                            continue
                        
                        yield SystemAlert(
                            alert_id=data["alert_id"],
                            severity=data["severity"],
                            category=data["category"],
                            title=data["title"],
                            message=data["message"],
                            affected_zones=data.get("affected_zones", []),
                            timestamp=datetime.fromisoformat(data["timestamp"])
                        )
                    except Exception as e:
                        logger.error("Failed to parse system alert", error=str(e))
        finally:
            await pubsub.unsubscribe("alerts:system")
            await redis_client.close()
    
    @strawberry.subscription
    async def water_flow_updates(
        self,
        info: strawberry.Info[GraphQLContext],
        gate_id: str
    ) -> AsyncGenerator[dict, None]:
        """Subscribe to real-time water flow measurements"""
        redis_client = await redis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        
        channel = f"flow:gate:{gate_id}"
        await pubsub.subscribe(channel)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield {
                            "gate_id": gate_id,
                            "flow_rate_m3s": data["flow_rate"],
                            "total_volume_m3": data["total_volume"],
                            "timestamp": datetime.fromisoformat(data["timestamp"])
                        }
                    except Exception as e:
                        logger.error("Failed to parse flow update", error=str(e))
        finally:
            await pubsub.unsubscribe(channel)
            await redis_client.close()


# Helper function to publish updates (used by background services)
async def publish_demand_update(
    section_id: str,
    level_type: str,
    method: str,
    gross_demand_m3: float,
    net_demand_m3: float,
    trigger: str = "scheduled"
):
    """Publish demand update to Redis"""
    redis_client = await redis.from_url(settings.redis_url)
    
    data = {
        "section_id": section_id,
        "level_type": level_type,
        "method": method,
        "gross_demand_m3": gross_demand_m3,
        "net_demand_m3": net_demand_m3,
        "calculation_time": datetime.utcnow().isoformat(),
        "trigger": trigger
    }
    
    # Publish to multiple channels
    channels = [
        f"demand:{level_type}:{section_id}",
        "demand:all"
    ]
    
    for channel in channels:
        await redis_client.publish(channel, json.dumps(data))
    
    await redis_client.close()