"""
Cache Manager Service
Implements caching strategies for performance optimization
"""

import json
import hashlib
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from functools import wraps
import pickle

from core import get_logger
from config import settings

logger = get_logger(__name__)


class CacheManager:
    """Manages caching for the ROS-GIS Integration service"""
    
    def __init__(self):
        self.logger = logger.bind(service="cache_manager")
        self.redis_client = None
        self._connected = False
        
        # Cache TTL configuration
        self.ttl_config = {
            "section_data": 3600,  # 1 hour
            "water_demands": 1800,  # 30 minutes
            "delivery_paths": 3600,  # 1 hour
            "gate_mappings": 7200,  # 2 hours
            "weather_forecast": 10800,  # 3 hours
            "crop_calendar": 86400,  # 24 hours
            "spatial_data": 3600,  # 1 hour
            "aggregated_demands": 900,  # 15 minutes
            "performance_metrics": 300,  # 5 minutes
        }
    
    async def connect(self) -> bool:
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=False  # We'll handle encoding/decoding
            )
            
            # Test connection
            await self.redis_client.ping()
            self._connected = True
            self.logger.info("Connected to Redis cache")
            return True
            
        except Exception as e:
            self.logger.error("Failed to connect to Redis", error=str(e))
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
    
    def _generate_key(self, namespace: str, identifier: Union[str, Dict]) -> str:
        """Generate cache key with namespace"""
        if isinstance(identifier, dict):
            # Sort dict keys for consistent hashing
            sorted_dict = json.dumps(identifier, sort_keys=True)
            hash_value = hashlib.md5(sorted_dict.encode()).hexdigest()
            return f"{settings.service_name}:{namespace}:{hash_value}"
        else:
            return f"{settings.service_name}:{namespace}:{identifier}"
    
    async def get(self, namespace: str, identifier: Union[str, Dict]) -> Optional[Any]:
        """Get value from cache"""
        if not self._connected:
            return None
        
        try:
            key = self._generate_key(namespace, identifier)
            value = await self.redis_client.get(key)
            
            if value:
                # Deserialize the value
                return pickle.loads(value)
            
            return None
            
        except Exception as e:
            self.logger.error("Cache get error", error=str(e), namespace=namespace)
            return None
    
    async def set(
        self,
        namespace: str,
        identifier: Union[str, Dict],
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        if not self._connected:
            return False
        
        try:
            key = self._generate_key(namespace, identifier)
            
            # Use configured TTL if not specified
            if ttl is None:
                ttl = self.ttl_config.get(namespace, settings.cache_ttl_seconds)
            
            # Serialize the value
            serialized = pickle.dumps(value)
            
            # Set with expiration
            await self.redis_client.set(key, serialized, ex=ttl)
            
            return True
            
        except Exception as e:
            self.logger.error("Cache set error", error=str(e), namespace=namespace)
            return False
    
    async def delete(self, namespace: str, identifier: Union[str, Dict]) -> bool:
        """Delete value from cache"""
        if not self._connected:
            return False
        
        try:
            key = self._generate_key(namespace, identifier)
            await self.redis_client.delete(key)
            return True
            
        except Exception as e:
            self.logger.error("Cache delete error", error=str(e), namespace=namespace)
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self._connected:
            return 0
        
        try:
            # Find all matching keys
            keys = []
            async for key in self.redis_client.scan_iter(match=f"{settings.service_name}:{pattern}*"):
                keys.append(key)
            
            # Delete in batch
            if keys:
                return await self.redis_client.delete(*keys)
            
            return 0
            
        except Exception as e:
            self.logger.error("Cache pattern delete error", error=str(e), pattern=pattern)
            return 0
    
    async def cache_water_demand(
        self,
        section_id: str,
        week: int,
        year: int,
        demand_data: Dict
    ) -> bool:
        """Cache water demand calculation"""
        identifier = {
            "section_id": section_id,
            "week": week,
            "year": year
        }
        
        return await self.set("water_demands", identifier, demand_data)
    
    async def get_cached_water_demand(
        self,
        section_id: str,
        week: int,
        year: int
    ) -> Optional[Dict]:
        """Get cached water demand"""
        identifier = {
            "section_id": section_id,
            "week": week,
            "year": year
        }
        
        return await self.get("water_demands", identifier)
    
    async def cache_delivery_path(
        self,
        source: str,
        target: str,
        constraints: Optional[Dict],
        path_data: Dict
    ) -> bool:
        """Cache delivery path calculation"""
        identifier = {
            "source": source,
            "target": target,
            "constraints": constraints or {}
        }
        
        return await self.set("delivery_paths", identifier, path_data)
    
    async def get_cached_delivery_path(
        self,
        source: str,
        target: str,
        constraints: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Get cached delivery path"""
        identifier = {
            "source": source,
            "target": target,
            "constraints": constraints or {}
        }
        
        return await self.get("delivery_paths", identifier)
    
    async def cache_aggregated_demands(
        self,
        zone: int,
        week: str,
        demands: List[Dict]
    ) -> bool:
        """Cache aggregated demands for a zone/week"""
        identifier = f"zone_{zone}_week_{week}"
        return await self.set("aggregated_demands", identifier, demands)
    
    async def get_cached_aggregated_demands(
        self,
        zone: int,
        week: str
    ) -> Optional[List[Dict]]:
        """Get cached aggregated demands"""
        identifier = f"zone_{zone}_week_{week}"
        return await self.get("aggregated_demands", identifier)
    
    async def invalidate_zone_cache(self, zone: int) -> None:
        """Invalidate all cache entries for a zone"""
        patterns = [
            f"*zone_{zone}*",
            f"*Zone_{zone}*"
        ]
        
        for pattern in patterns:
            deleted = await self.delete_pattern(pattern)
            if deleted > 0:
                self.logger.info(
                    "Invalidated zone cache",
                    zone=zone,
                    pattern=pattern,
                    deleted_keys=deleted
                )
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self._connected:
            return {"status": "disconnected"}
        
        try:
            info = await self.redis_client.info()
            
            # Count keys by namespace
            namespace_counts = {}
            for namespace in self.ttl_config.keys():
                pattern = f"{settings.service_name}:{namespace}:*"
                count = 0
                async for _ in self.redis_client.scan_iter(match=pattern):
                    count += 1
                namespace_counts[namespace] = count
            
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "unknown"),
                "total_keys": info.get("db2", {}).get("keys", 0),  # DB 2 as per redis_url
                "namespace_counts": namespace_counts,
                "hit_rate": self._calculate_hit_rate(info),
                "evicted_keys": info.get("evicted_keys", 0)
            }
            
        except Exception as e:
            self.logger.error("Failed to get cache stats", error=str(e))
            return {"status": "error", "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate"""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        
        total = hits + misses
        if total == 0:
            return 0.0
        
        return (hits / total) * 100


# Cache decorator for async functions
def cached(namespace: str, ttl: Optional[int] = None):
    """Decorator for caching async function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache manager instance
            cache = CacheManager()
            if not cache._connected:
                await cache.connect()
            
            # Generate cache key from function arguments
            cache_key = {
                "func": func.__name__,
                "args": str(args),
                "kwargs": str(sorted(kwargs.items()))
            }
            
            # Try to get from cache
            cached_result = await cache.get(namespace, cache_key)
            if cached_result is not None:
                logger.debug(
                    "Cache hit",
                    function=func.__name__,
                    namespace=namespace
                )
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache the result
            await cache.set(namespace, cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Singleton instance
_cache_manager_instance = None


async def get_cache_manager() -> CacheManager:
    """Get singleton cache manager instance"""
    global _cache_manager_instance
    
    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()
        await _cache_manager_instance.connect()
    
    return _cache_manager_instance