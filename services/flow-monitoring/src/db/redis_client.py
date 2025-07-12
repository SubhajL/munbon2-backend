from typing import Any, Optional, Dict, List
import json
import structlog
from redis import asyncio as aioredis

from config import settings
from core.metrics import db_operations_total, db_operation_duration_seconds

logger = structlog.get_logger()


class RedisClient:
    """Async Redis client for caching and real-time data"""
    
    def __init__(self):
        self.redis_url = settings.redis_url
        self.client: Optional[aioredis.Redis] = None
        self.default_ttl = settings.cache_ttl_seconds
    
    async def connect(self) -> None:
        """Connect to Redis"""
        try:
            self.client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.ping()
            
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
    
    async def ping(self) -> bool:
        """Check if Redis is reachable"""
        try:
            response = await self.client.ping()
            return response is True
        except Exception as e:
            logger.error("Redis ping failed", error=str(e))
            return False
    
    async def set_latest_flow_data(
        self,
        location_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """Cache latest flow data for a location"""
        with db_operation_duration_seconds.labels(operation="set", database="redis").time():
            try:
                key = f"flow:latest:{location_id}"
                value = json.dumps(data)
                ttl = ttl or self.default_ttl
                
                await self.client.setex(key, ttl, value)
                db_operations_total.labels(operation="set", database="redis", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to set flow data in Redis", error=str(e))
                db_operations_total.labels(operation="set", database="redis", status="error").inc()
                raise
    
    async def get_latest_flow_data(self, location_id: str) -> Optional[Dict[str, Any]]:
        """Get cached latest flow data for a location"""
        with db_operation_duration_seconds.labels(operation="get", database="redis").time():
            try:
                key = f"flow:latest:{location_id}"
                value = await self.client.get(key)
                
                if value:
                    db_operations_total.labels(operation="get", database="redis", status="hit").inc()
                    return json.loads(value)
                
                db_operations_total.labels(operation="get", database="redis", status="miss").inc()
                return None
                
            except Exception as e:
                logger.error("Failed to get flow data from Redis", error=str(e))
                db_operations_total.labels(operation="get", database="redis", status="error").inc()
                raise
    
    async def cache_model_result(
        self,
        model_key: str,
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """Cache model computation results"""
        with db_operation_duration_seconds.labels(operation="set", database="redis").time():
            try:
                key = f"model:result:{model_key}"
                value = json.dumps(result)
                ttl = ttl or self.default_ttl
                
                await self.client.setex(key, ttl, value)
                db_operations_total.labels(operation="set", database="redis", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to cache model result", error=str(e))
                db_operations_total.labels(operation="set", database="redis", status="error").inc()
                raise
    
    async def get_cached_model_result(self, model_key: str) -> Optional[Dict[str, Any]]:
        """Get cached model computation result"""
        with db_operation_duration_seconds.labels(operation="get", database="redis").time():
            try:
                key = f"model:result:{model_key}"
                value = await self.client.get(key)
                
                if value:
                    db_operations_total.labels(operation="get", database="redis", status="hit").inc()
                    return json.loads(value)
                
                db_operations_total.labels(operation="get", database="redis", status="miss").inc()
                return None
                
            except Exception as e:
                logger.error("Failed to get cached model result", error=str(e))
                db_operations_total.labels(operation="get", database="redis", status="error").inc()
                raise
    
    async def publish_flow_update(self, channel: str, data: Dict[str, Any]) -> None:
        """Publish flow update to Redis pub/sub channel"""
        with db_operation_duration_seconds.labels(operation="publish", database="redis").time():
            try:
                message = json.dumps(data)
                await self.client.publish(channel, message)
                db_operations_total.labels(operation="publish", database="redis", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to publish flow update", error=str(e))
                db_operations_total.labels(operation="publish", database="redis", status="error").inc()
                raise
    
    async def set_anomaly_flag(
        self,
        location_id: str,
        anomaly_type: str,
        data: Dict[str, Any]
    ) -> None:
        """Set anomaly detection flag"""
        with db_operation_duration_seconds.labels(operation="set", database="redis").time():
            try:
                key = f"anomaly:{location_id}:{anomaly_type}"
                value = json.dumps(data)
                # Anomaly flags expire after 1 hour
                await self.client.setex(key, 3600, value)
                db_operations_total.labels(operation="set", database="redis", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to set anomaly flag", error=str(e))
                db_operations_total.labels(operation="set", database="redis", status="error").inc()
                raise
    
    async def get_active_anomalies(self, location_id: str) -> List[Dict[str, Any]]:
        """Get all active anomalies for a location"""
        with db_operation_duration_seconds.labels(operation="scan", database="redis").time():
            try:
                pattern = f"anomaly:{location_id}:*"
                anomalies = []
                
                async for key in self.client.scan_iter(match=pattern):
                    value = await self.client.get(key)
                    if value:
                        anomaly_data = json.loads(value)
                        anomaly_type = key.split(":")[-1]
                        anomaly_data["type"] = anomaly_type
                        anomalies.append(anomaly_data)
                
                db_operations_total.labels(operation="scan", database="redis", status="success").inc()
                return anomalies
                
            except Exception as e:
                logger.error("Failed to get active anomalies", error=str(e))
                db_operations_total.labels(operation="scan", database="redis", status="error").inc()
                raise