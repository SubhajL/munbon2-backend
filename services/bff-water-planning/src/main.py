from contextlib import asynccontextmanager
import asyncio
import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from strawberry.fastapi import GraphQLRouter
from prometheus_client import make_asgi_app
import structlog

from config import settings
from core import get_logger
from db import DatabaseManager
from api.schema import create_graphql_app, register_graphql_context_cleanup
from api.routes import admin
from services.ros_sync_service import RosSyncService
from services.daily_demand_scheduler import daily_demand_scheduler
from config.redis import redis_config

# Configure logging
logger = get_logger(__name__)

# Database manager instance
db_manager = DatabaseManager()

# ROS sync service instance
ros_sync_service = RosSyncService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Water Planning BFF Service", port=settings.port)
    await db_manager.initialize()
    logger.info("Database connections initialized")

    # Lifespan-owned pooled HTTP client (PR 4.4a-2): shared by the scheduler
    # control-plan reads AND the readiness probes so upstream calls reuse one
    # connection pool instead of opening a fresh client per request.
    from services.readiness_service import build_probe_timeout

    app.state.http_client = httpx.AsyncClient(timeout=build_probe_timeout(settings))
    logger.info("Pooled upstream HTTP client initialized")

    # Everything from here on is inside try/finally so a fallible startup step
    # (e.g. the daily-demand scheduler) can never LEAK the pooled client: cleanup
    # runs in `finally` whether startup completed or raised.
    try:
        # Start ROS sync service if not using mock
        if not settings.use_mock_server:
            asyncio.create_task(ros_sync_service.start_periodic_sync())
            logger.info("ROS sync service started")

        # Start daily demand scheduler
        await daily_demand_scheduler.start_scheduler()
        logger.info("Daily demand scheduler started")

        # No weekly demand producer runs here: production is owned by
        # ros-gis-integration (ADR D5, Wave 2.6); the BFF serves read paths only.

        # Initialize Redis for event publishing
        try:
            await redis_config.create_redis_client()
            if redis_config.is_connected:
                logger.info("Redis client initialized for event publishing")
            else:
                logger.warning("Redis not available - event publishing disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            logger.warning("Running without event publishing capability")

        yield
    finally:
        # Shutdown — always runs, even if a startup step above raised.
        logger.info("Shutting down Water Planning BFF Service")
        ros_sync_service.stop_periodic_sync()
        daily_demand_scheduler.stop_scheduler()

        # Close the pooled upstream HTTP client (guarded: it may not exist if an
        # even earlier step failed, though it is created just above the try).
        http_client = getattr(app.state, "http_client", None)
        if http_client is not None:
            await http_client.aclose()
            logger.info("Pooled upstream HTTP client closed")

        # Close Redis connection
        await redis_config.disconnect()
        logger.info("Redis connection closed")

        await db_manager.close()
        logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="Water Planning BFF Service",
    description="Backend for Frontend service optimizing water demand planning with AWD integration",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create and include GraphQL app with enhanced features
graphql_app = create_graphql_app()
app.include_router(graphql_app, prefix="")
register_graphql_context_cleanup(app)

# Include admin routes
app.include_router(admin.router, prefix="/api/v1")

# Include REST API routes
from api.routes import control_plans, crop_season, water_demand, water_demand_v2
app.include_router(crop_season.router)
app.include_router(water_demand.router)
app.include_router(water_demand_v2.router)
app.include_router(control_plans.router)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    """Process liveness ONLY — never claims dependency health. It makes NO DB or
    upstream claim (the old block hardcoded every upstream `True`); dependency
    truth lives at `/ready`. Reports the real app version."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": app.version,
    }


@app.get("/ready")
async def readiness_check(request: Request):
    """Dependency-truth readiness: concurrently probe the required upstreams
    (scheduler /ready, flow /ready, ros /ready) over the pooled client, each
    bounded. 503 unless every upstream is ready; body carries only safe status
    strings (no host/URL/exception leaks)."""
    from services.readiness_service import (
        build_probe_timeout,
        build_probe_wall_clock_seconds,
        build_required_targets,
        probe_required_upstreams,
    )

    result = await probe_required_upstreams(
        getattr(request.app.state, "http_client", None),
        build_required_targets(settings),
        build_probe_timeout(settings),
        build_probe_wall_clock_seconds(settings),
    )
    body = {
        "status": "ready" if result.ready else "not ready",
        "checks": result.checks,
    }
    if not result.ready:
        return JSONResponse(status_code=503, content=body)
    return body


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "description": "Water Planning BFF Service - Optimizing water demand with AWD integration",
        "endpoints": {
            "graphql": "/graphql",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs",
            "graphiql": "/graphql" if settings.environment == "development" else None
        }
    }


@app.get("/api/v1/status")
async def service_status():
    """Detailed service status"""
    return {
        "service": settings.service_name,
        "environment": settings.environment,
        "configuration": {
            "demand_advance_hours": settings.demand_advance_hours,
            "min_demand_m3": settings.min_demand_m3,
            "max_sections_per_gate": settings.max_sections_per_gate,
            "priority_weights": {
                "crop_stage": settings.crop_stage_weight,
                "moisture_deficit": settings.moisture_deficit_weight,
                "economic_value": settings.economic_value_weight,
                "stress_indicator": settings.stress_indicator_weight
            }
        },
        "mock_mode": settings.use_mock_server
    }


# Example REST endpoints for compatibility
@app.get("/api/v1/sections/{section_id}")
async def get_section(section_id: str):
    """REST endpoint for section details"""
    section = await db_manager.get_section(section_id)
    if section:
        return section
    return JSONResponse(
        status_code=404,
        content={"error": f"Section {section_id} not found"}
    )


@app.get("/api/v1/zones/{zone}/sections")
async def get_zone_sections(zone: int):
    """REST endpoint for sections by zone"""
    sections = await db_manager.get_sections_by_zone(zone)
    return {
        "zone": zone,
        "sections": sections,
        "count": len(sections)
    }


@app.post("/api/v1/sync/trigger")
async def trigger_sync(section_ids: Optional[List[str]] = None):
    """Manually trigger ROS sync for specific sections or all"""
    if section_ids:
        result = await ros_sync_service.sync_ros_calculations(section_ids)
    else:
        result = await ros_sync_service.sync_all_sections()
    
    return result


@app.get("/api/v1/sync/status")
async def get_sync_status():
    """Get current sync service status"""
    return await ros_sync_service.get_sync_status()


@app.post("/api/v1/sync/start")
async def start_periodic_sync():
    """Start the periodic sync service"""
    if ros_sync_service.is_running:
        return {
            "status": "already_running",
            "message": "Sync service is already running"
        }
    
    asyncio.create_task(ros_sync_service.start_periodic_sync())
    return {
        "status": "started",
        "message": "Periodic sync service started"
    }


@app.post("/api/v1/sync/stop")
async def stop_periodic_sync():
    """Stop the periodic sync service"""
    ros_sync_service.stop_periodic_sync()
    return {
        "status": "stopped",
        "message": "Periodic sync service stopped"
    }


# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.environment == "development" else "An error occurred"
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )
