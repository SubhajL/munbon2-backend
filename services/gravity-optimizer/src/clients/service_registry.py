"""Service registry for dynamic service discovery"""

import os
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import asyncio
import aioredis
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ServiceInfo(BaseModel):
    """Service registration information"""
    name: str
    version: str
    url: str
    health_endpoint: str = "/health"
    tags: List[str] = []
    metadata: Dict[str, any] = {}
    registered_at: datetime = None
    last_heartbeat: datetime = None
    
    def __init__(self, **data):
        if 'registered_at' not in data:
            data['registered_at'] = datetime.now()
        if 'last_heartbeat' not in data:
            data['last_heartbeat'] = datetime.now()
        super().__init__(**data)


class ServiceRegistry:
    """Service registry with Redis backend"""
    
    def __init__(
        self,
        redis_url: str = None,
        namespace: str = "munbon:services",
        ttl: int = 300,  # 5 minutes
        heartbeat_interval: int = 60  # 1 minute
    ):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.namespace = namespace
        self.ttl = ttl
        self.heartbeat_interval = heartbeat_interval
        self._redis: Optional[aioredis.Redis] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._local_cache: Dict[str, ServiceInfo] = {}
        self._cache_updated: Optional[datetime] = None
        
        # Service discovery configuration (fallback when Redis unavailable)
        self._static_services = {
            'gis': {
                'url': os.getenv('GIS_SERVICE_URL', 'http://localhost:3007'),
                'version': '1.0.0'
            },
            'ros': {
                'url': os.getenv('ROS_SERVICE_URL', 'http://localhost:3047'),
                'version': '1.0.0'
            },
            'scada': {
                'url': os.getenv('SCADA_SERVICE_URL', 'http://localhost:3008'),
                'version': '1.0.0'
            },
            'weather': {
                'url': os.getenv('WEATHER_SERVICE_URL', 'http://localhost:3009'),
                'version': '1.0.0'
            },
            'sensor-data': {
                'url': os.getenv('SENSOR_DATA_SERVICE_URL', 'http://localhost:3003'),
                'version': '1.0.0'
            },
            'auth': {
                'url': os.getenv('AUTH_SERVICE_URL', 'http://localhost:3001'),
                'version': '1.0.0'
            }
        }
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            logger.info("Connected to Redis service registry")
            
            # Start heartbeat
            await self._start_heartbeat()
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis, using static configuration: {e}")
            self._redis = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    async def register(self, service_info: ServiceInfo):
        """Register a service"""
        if not self._redis:
            logger.warning("Redis not available, registration skipped")
            return
        
        try:
            key = f"{self.namespace}:{service_info.name}"
            value = service_info.model_dump_json()
            
            await self._redis.setex(key, self.ttl, value)
            logger.info(f"Registered service: {service_info.name} at {service_info.url}")
            
            # Update local cache
            self._local_cache[service_info.name] = service_info
            
        except Exception as e:
            logger.error(f"Failed to register service: {e}")
    
    async def deregister(self, service_name: str):
        """Deregister a service"""
        if not self._redis:
            return
        
        try:
            key = f"{self.namespace}:{service_name}"
            await self._redis.delete(key)
            logger.info(f"Deregistered service: {service_name}")
            
            # Update local cache
            self._local_cache.pop(service_name, None)
            
        except Exception as e:
            logger.error(f"Failed to deregister service: {e}")
    
    async def discover(self, service_name: str) -> Optional[ServiceInfo]:
        """Discover a service by name"""
        # Check local cache first
        if self._should_use_cache() and service_name in self._local_cache:
            return self._local_cache[service_name]
        
        # Try Redis
        if self._redis:
            try:
                key = f"{self.namespace}:{service_name}"
                data = await self._redis.get(key)
                
                if data:
                    service_info = ServiceInfo.model_validate_json(data)
                    self._local_cache[service_name] = service_info
                    return service_info
                    
            except Exception as e:
                logger.warning(f"Failed to discover service from Redis: {e}")
        
        # Fall back to static configuration
        if service_name in self._static_services:
            config = self._static_services[service_name]
            return ServiceInfo(
                name=service_name,
                url=config['url'],
                version=config['version']
            )
        
        logger.error(f"Service not found: {service_name}")
        return None
    
    async def discover_all(self, tags: Optional[List[str]] = None) -> List[ServiceInfo]:
        """Discover all services, optionally filtered by tags"""
        services = []
        
        if self._redis:
            try:
                pattern = f"{self.namespace}:*"
                keys = await self._redis.keys(pattern)
                
                for key in keys:
                    data = await self._redis.get(key)
                    if data:
                        service_info = ServiceInfo.model_validate_json(data)
                        
                        # Filter by tags if specified
                        if tags:
                            if any(tag in service_info.tags for tag in tags):
                                services.append(service_info)
                        else:
                            services.append(service_info)
                
                # Update cache
                self._update_cache(services)
                
            except Exception as e:
                logger.warning(f"Failed to discover services from Redis: {e}")
        
        # If no services from Redis, use static configuration
        if not services:
            for name, config in self._static_services.items():
                services.append(ServiceInfo(
                    name=name,
                    url=config['url'],
                    version=config['version']
                ))
        
        return services
    
    async def heartbeat(self, service_name: str):
        """Send heartbeat for a service"""
        if not self._redis:
            return
        
        try:
            key = f"{self.namespace}:{service_name}"
            data = await self._redis.get(key)
            
            if data:
                service_info = ServiceInfo.model_validate_json(data)
                service_info.last_heartbeat = datetime.now()
                
                await self._redis.setex(key, self.ttl, service_info.model_dump_json())
                
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
    
    async def _start_heartbeat(self):
        """Start heartbeat task for gravity optimizer"""
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(self.heartbeat_interval)
                    await self.heartbeat('gravity-optimizer')
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
        
        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
    
    def _should_use_cache(self) -> bool:
        """Check if local cache is still valid"""
        if not self._cache_updated:
            return False
        
        cache_age = datetime.now() - self._cache_updated
        return cache_age < timedelta(seconds=30)  # 30 second cache
    
    def _update_cache(self, services: List[ServiceInfo]):
        """Update local cache"""
        self._local_cache = {s.name: s for s in services}
        self._cache_updated = datetime.now()
    
    async def register_gravity_optimizer(self):
        """Register gravity optimizer service"""
        from ..config.settings import settings
        
        service_info = ServiceInfo(
            name='gravity-optimizer',
            version=settings.version,
            url=f"http://{os.getenv('HOSTNAME', 'localhost')}:{settings.port}",
            health_endpoint="/health",
            tags=['optimization', 'hydraulics', 'gravity'],
            metadata={
                'zones': len(settings.zone_elevations),
                'automated_gates': settings.automated_gates_count,
                'api_prefix': settings.api_prefix
            }
        )
        
        await self.register(service_info)


# Global registry instance
service_registry = ServiceRegistry()