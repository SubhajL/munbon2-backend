import redis.asyncio as redis
from typing import Optional, Any, Dict
import json
from datetime import timedelta

from .config import settings


class RedisClient:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        
    async def connect(self):
        """Initialize Redis connection"""
        self.client = await redis.from_url(
            settings.redis_url,
            password=settings.redis_password,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis_pool_size,
        )
        
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        if not self.client:
            return None
        return await self.client.get(key)
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        """Set value in Redis with optional expiration"""
        if not self.client:
            return
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        if expire:
            await self.client.setex(key, expire, value)
        else:
            await self.client.set(key, value)
    
    async def delete(self, key: str):
        """Delete key from Redis"""
        if self.client:
            await self.client.delete(key)
    
    async def get_json(self, key: str) -> Optional[Dict]:
        """Get JSON value from Redis"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    async def set_json(self, key: str, value: Dict, expire: Optional[int] = None):
        """Set JSON value in Redis"""
        await self.set(key, json.dumps(value), expire)
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value"""
        if not self.client:
            return None
        return await self.client.hget(name, key)
    
    async def hset(self, name: str, key: str, value: Any):
        """Set hash field value"""
        if self.client:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await self.client.hset(name, key, value)
    
    async def hgetall(self, name: str) -> Dict:
        """Get all hash fields"""
        if not self.client:
            return {}
        return await self.client.hgetall(name)
    
    async def publish(self, channel: str, message: Any):
        """Publish message to channel"""
        if self.client:
            if isinstance(message, dict):
                message = json.dumps(message)
            await self.client.publish(channel, message)
    
    async def subscribe(self, *channels):
        """Subscribe to channels"""
        if self.client:
            pubsub = self.client.pubsub()
            await pubsub.subscribe(*channels)
            return pubsub
        return None


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency to get Redis client"""
    return redis_client