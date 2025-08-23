import asyncio
import asyncpg
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager

from core import get_logger
from config import settings
from .models import Base
from .repository import (
    SectionRepository, DemandRepository, PerformanceRepository,
    GateMappingRepository, GateDemandRepository
)

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self):
        self.logger = logger.bind(component="database_manager")
        self._pg_pool: Optional[asyncpg.Pool] = None
        self._redis_client: Optional[redis.Redis] = None
        self.engine = None
        self.async_session = None
    
    async def initialize(self):
        """Initialize database connections"""
        try:
            # URL-encode the password if needed
            from urllib.parse import urlparse, urlunparse, quote
            parsed = urlparse(settings.postgres_url)
            
            # Encode the password if it contains special characters
            if parsed.password:
                encoded_password = quote(parsed.password, safe='')
                netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                
                encoded_postgres_url = urlunparse((
                    parsed.scheme,
                    netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
            else:
                encoded_postgres_url = settings.postgres_url
            
            # PostgreSQL connection pool for raw queries
            self._pg_pool = await asyncpg.create_pool(
                encoded_postgres_url,
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                max_queries=settings.db_pool_max_queries,
                max_inactive_connection_lifetime=settings.db_pool_max_inactive_connection_lifetime,
                command_timeout=60
            )
            
            # SQLAlchemy async engine for ORM
            # Note: When using NullPool, we can't specify pool_size or max_overflow
            self.engine = create_async_engine(
                encoded_postgres_url.replace('postgresql://', 'postgresql+asyncpg://'),
                echo=settings.environment == "development",
                pool_pre_ping=True,
                poolclass=NullPool
            )
            
            # Create async session factory
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Redis connection
            self._redis_client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Create tables if they don't exist (for development)
            if settings.environment == "development":
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            
            # Test connections
            await self._test_connections()
            
            self.logger.info("Database connections initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize databases", error=str(e))
            raise
    
    async def close(self):
        """Close database connections"""
        if self._pg_pool:
            await self._pg_pool.close()
        
        if self.engine:
            await self.engine.dispose()
        
        if self._redis_client:
            await self._redis_client.close()
        
        self.logger.info("Database connections closed")
    
    async def _test_connections(self):
        """Test database connections"""
        # Test PostgreSQL
        async with self._pg_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1
        
        # Test Redis
        await self._redis_client.ping()
    
    async def check_health(self) -> Dict[str, bool]:
        """Check health of all database connections"""
        health = {
            "postgres": False,
            "redis": False
        }
        
        try:
            # Check PostgreSQL
            if self._pg_pool:
                async with self._pg_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                    health["postgres"] = True
        except Exception as e:
            self.logger.error("PostgreSQL health check failed", error=str(e))
        
        try:
            # Check Redis
            if self._redis_client:
                await self._redis_client.ping()
                health["redis"] = True
        except Exception as e:
            self.logger.error("Redis health check failed", error=str(e))
        
        return health
    
    # Section operations
    async def get_section(self, section_id: str) -> Optional[Dict]:
        """Get section details from database"""
        query = """
        SELECT 
            section_id,
            zone,
            area_hectares,
            crop_type,
            soil_type,
            elevation_m,
            delivery_gate,
            ST_AsGeoJSON(geometry) as geometry,
            created_at,
            updated_at
        FROM sections
        WHERE section_id = $1
        """
        
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, section_id)
            if row:
                return dict(row)
            return None
    
    async def get_sections_by_zone(self, zone: int) -> List[Dict]:
        """Get all sections in a zone"""
        query = """
        SELECT 
            section_id,
            zone,
            area_hectares,
            crop_type,
            soil_type,
            elevation_m,
            delivery_gate,
            ST_AsGeoJSON(geometry) as geometry
        FROM sections
        WHERE zone = $1
        ORDER BY section_id
        """
        
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, zone)
            return [dict(row) for row in rows]
    
    # Cache operations
    async def get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self._redis_client.get(key)
            return value
        except Exception as e:
            self.logger.error("Cache get failed", key=key, error=str(e))
            return None
    
    async def set_cached(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with optional TTL"""
        try:
            if ttl is None:
                ttl = settings.cache_ttl_seconds
            
            await self._redis_client.setex(key, ttl, value)
        except Exception as e:
            self.logger.error("Cache set failed", key=key, error=str(e))
    
    async def delete_cached(self, pattern: str):
        """Delete cached values matching pattern"""
        try:
            keys = await self._redis_client.keys(pattern)
            if keys:
                await self._redis_client.delete(*keys)
        except Exception as e:
            self.logger.error("Cache delete failed", pattern=pattern, error=str(e))
    
    # Demand operations
    async def save_demand(self, demand: Dict) -> str:
        """Save demand to database"""
        query = """
        INSERT INTO demands (
            section_id,
            week,
            volume_m3,
            priority,
            priority_class,
            crop_type,
            growth_stage,
            created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING demand_id
        """
        
        async with self._pg_pool.acquire() as conn:
            demand_id = await conn.fetchval(
                query,
                demand["section_id"],
                demand["week"],
                demand["volume_m3"],
                demand["final_priority"],
                demand["priority_class"],
                demand["crop_type"],
                demand["growth_stage"],
                datetime.utcnow()
            )
            return demand_id
    
    # Performance operations
    async def save_performance(self, performance: Dict) -> str:
        """Save section performance data"""
        query = """
        INSERT INTO section_performance (
            section_id,
            week,
            planned_m3,
            delivered_m3,
            efficiency,
            deficit_m3,
            created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING performance_id
        """
        
        async with self._pg_pool.acquire() as conn:
            performance_id = await conn.fetchval(
                query,
                performance["section_id"],
                performance["week"],
                performance["planned_m3"],
                performance["delivered_m3"],
                performance["efficiency"],
                performance["deficit_m3"],
                datetime.utcnow()
            )
            return performance_id
    
    async def get_performance_history(
        self,
        section_id: str,
        weeks: int = 4
    ) -> List[Dict]:
        """Get historical performance for a section"""
        query = """
        SELECT 
            week,
            planned_m3,
            delivered_m3,
            efficiency,
            deficit_m3,
            created_at
        FROM section_performance
        WHERE section_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """
        
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, section_id, weeks)
            return [dict(row) for row in rows]
    
    # Spatial operations
    async def find_sections_near_point(
        self,
        latitude: float,
        longitude: float,
        radius_km: float
    ) -> List[Dict]:
        """Find sections within radius of a point"""
        query = """
        SELECT 
            section_id,
            zone,
            area_hectares,
            ST_Distance(
                geometry::geography,
                ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography
            ) / 1000 as distance_km
        FROM sections
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint($2, $1), 4326)::geography,
            $3 * 1000
        )
        ORDER BY distance_km
        """
        
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, latitude, longitude, radius_km)
            return [dict(row) for row in rows]
    
    async def get_delivery_path(
        self,
        section_id: str,
        gate_id: str
    ) -> Optional[List[str]]:
        """Get optimal delivery path from gate to section"""
        # In production, would use PostGIS routing functions
        # For now, return simple path
        zone = int(section_id.split("_")[1])
        path = [
            "Source",
            "M(0,0)",
            "M(0,2)" if zone in [2, 3] else "M(0,5)",
            gate_id,
            f"Zone_{zone}_Node",
            section_id
        ]
        return path
    
    # Repository access methods
    @asynccontextmanager
    async def get_session(self):
        """Get database session for repository operations"""
        async with self.async_session() as session:
            yield session
    
    async def get_section_repository(self):
        """Get section repository with session"""
        async with self.get_session() as session:
            yield SectionRepository(session)
    
    async def get_demand_repository(self):
        """Get demand repository with session"""
        async with self.get_session() as session:
            yield DemandRepository(session)
    
    async def get_performance_repository(self):
        """Get performance repository with session"""
        async with self.get_session() as session:
            yield PerformanceRepository(session)
    
    async def get_gate_mapping_repository(self):
        """Get gate mapping repository with session"""
        async with self.get_session() as session:
            yield GateMappingRepository(session)
    
    async def get_gate_demand_repository(self):
        """Get gate demand repository with session"""
        async with self.get_session() as session:
            yield GateDemandRepository(session)