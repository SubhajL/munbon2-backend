from contextlib import asynccontextmanager
import asyncio
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
from api import schema
from api.routes import admin
from services.ros_sync_service import RosSyncService

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
    logger.info("Starting ROS/GIS Integration Service", port=settings.port)
    await db_manager.initialize()
    logger.info("Database connections initialized")
    
    # Start ROS sync service if not using mock
    if not settings.use_mock_server:
        asyncio.create_task(ros_sync_service.start_periodic_sync())
        logger.info("ROS sync service started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ROS/GIS Integration Service")
    ros_sync_service.stop_periodic_sync()
    await db_manager.close()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="ROS/GIS Integration Service",
    description="Bridges agricultural needs with hydraulic delivery for Munbon Irrigation System",
    version="1.0.0",
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

# Create GraphQL router
graphql_app = GraphQLRouter(
    schema,
    path="/graphql",
    graphiql=settings.environment == "development"
)

# Include GraphQL router
app.include_router(graphql_app, prefix="")

# Include admin routes
app.include_router(admin.router, prefix="/api/v1")

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = await db_manager.check_health()
    
    # Check external service connectivity
    external_health = {
        "flow_monitoring": True,  # Would check actual service
        "scheduler": True,
        "ros": True,
        "gis": True
    }
    
    all_healthy = all(health_status.values()) and all(external_health.values())
    
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "service": settings.service_name,
        "version": "1.0.0",
        "databases": health_status,
        "external_services": external_health
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "description": "ROS/GIS Integration Service - Bridging agricultural needs with hydraulic delivery",
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