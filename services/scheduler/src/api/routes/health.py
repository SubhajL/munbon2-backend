from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ...core.database import get_db
from ...core.redis import get_redis, RedisClient
from ...core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": "1.0.0",
        "environment": settings.environment,
    }


@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Detailed health check including dependencies"""
    health_status = {
        "status": "healthy",
        "service": settings.service_name,
        "version": "1.0.0",
        "environment": settings.environment,
        "dependencies": {},
    }
    
    # Check database
    try:
        result = await db.execute(text("SELECT 1"))
        health_status["dependencies"]["database"] = "healthy"
    except Exception as e:
        health_status["dependencies"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        await redis.set("health_check", "ok", expire=10)
        value = await redis.get("health_check")
        if value == "ok":
            health_status["dependencies"]["redis"] = "healthy"
        else:
            health_status["dependencies"]["redis"] = "unhealthy: read/write mismatch"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status