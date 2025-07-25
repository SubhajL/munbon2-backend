import os
import json
from typing import Dict, List, Optional
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

redis_client = None

async def get_redis_client():
    """Get or create Redis client"""
    global redis_client
    
    if redis_client is None:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD") or None,
            decode_responses=True
        )
    
    return redis_client

async def cache_sensor_location(sensor_id: str, lat: float, lon: float, 
                               section_id: str, ttl: int = 3600):
    """Cache sensor location in Redis"""
    client = await get_redis_client()
    
    key = f"sensor:location:{sensor_id}"
    value = json.dumps({
        "lat": lat,
        "lon": lon,
        "section_id": section_id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    await client.setex(key, ttl, value)

async def get_cached_locations() -> Dict[str, Dict]:
    """Get all cached sensor locations"""
    client = await get_redis_client()
    
    locations = {}
    async for key in client.scan_iter("sensor:location:*"):
        sensor_id = key.split(":")[-1]
        value = await client.get(key)
        if value:
            locations[sensor_id] = json.loads(value)
    
    return locations

async def cache_interpolation_result(section_id: str, parameter: str, 
                                   value: float, confidence: float, ttl: int = 900):
    """Cache interpolation result for quick access"""
    client = await get_redis_client()
    
    key = f"interpolation:{section_id}:{parameter}"
    value = json.dumps({
        "value": value,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    await client.setex(key, ttl, value)

async def get_cached_interpolation(section_id: str, parameter: str) -> Optional[Dict]:
    """Get cached interpolation result"""
    client = await get_redis_client()
    
    key = f"interpolation:{section_id}:{parameter}"
    value = await client.get(key)
    
    return json.loads(value) if value else None

from datetime import datetime