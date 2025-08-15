"""
Admin API Routes
Provides administrative endpoints for monitoring and management
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime

from core import get_logger
from services import get_cache_manager, QueryOptimizer

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/cache/stats")
async def get_cache_statistics() -> Dict[str, Any]:
    """Get cache statistics and performance metrics"""
    try:
        cache = await get_cache_manager()
        stats = await cache.get_cache_stats()
        
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics"
        )


@router.post("/cache/clear/{namespace}")
async def clear_cache_namespace(namespace: str) -> Dict[str, Any]:
    """Clear all cache entries for a specific namespace"""
    try:
        cache = await get_cache_manager()
        deleted = await cache.delete_pattern(f"{namespace}:*")
        
        return {
            "status": "success",
            "namespace": namespace,
            "deleted_keys": deleted,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to clear cache", error=str(e), namespace=namespace)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@router.post("/cache/invalidate/zone/{zone}")
async def invalidate_zone_cache(zone: int) -> Dict[str, Any]:
    """Invalidate all cache entries for a specific zone"""
    try:
        cache = await get_cache_manager()
        await cache.invalidate_zone_cache(zone)
        
        return {
            "status": "success",
            "zone": zone,
            "message": f"Cache invalidated for zone {zone}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to invalidate zone cache", error=str(e), zone=zone)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate zone cache"
        )


@router.get("/query/stats")
async def get_query_statistics() -> Dict[str, Any]:
    """Get database query performance statistics"""
    try:
        optimizer = QueryOptimizer()
        stats = await optimizer.analyze_query_performance()
        
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get query stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve query statistics"
        )


@router.post("/optimize/indexes")
async def optimize_database_indexes() -> Dict[str, Any]:
    """Ensure all performance indexes are created"""
    try:
        optimizer = QueryOptimizer()
        await optimizer._ensure_indexes()
        
        return {
            "status": "success",
            "message": "Database indexes optimized",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to optimize indexes", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to optimize indexes"
        )


@router.get("/health/detailed")
async def get_detailed_health() -> Dict[str, Any]:
    """Get detailed health status including cache and database"""
    try:
        # Check cache
        cache = await get_cache_manager()
        cache_connected = cache._connected
        cache_stats = await cache.get_cache_stats() if cache_connected else None
        
        # Check database
        optimizer = QueryOptimizer()
        db_healthy = True
        try:
            await optimizer.db.get_connection()
        except:
            db_healthy = False
        
        return {
            "status": "healthy" if cache_connected and db_healthy else "unhealthy",
            "components": {
                "cache": {
                    "status": "connected" if cache_connected else "disconnected",
                    "stats": cache_stats
                },
                "database": {
                    "status": "connected" if db_healthy else "disconnected"
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Failed to get detailed health", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }