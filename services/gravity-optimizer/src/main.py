"""
Gravity Flow Optimizer Service
Optimizes water delivery using only gravity in the Munbon irrigation system
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info(f"Starting {settings.service_name} v{settings.version} on port {settings.port}")
    logger.info(f"Configured for {len(settings.zone_elevations)} zones")
    logger.info(f"Automated gates: {settings.automated_gates_count}")
    
    # Initialize service registry
    try:
        from clients.service_registry import service_registry
        await service_registry.connect()
        await service_registry.register_gravity_optimizer()
        logger.info("Service registered successfully")
    except Exception as e:
        logger.warning(f"Service registry connection failed: {e}")
    
    # Initialize database
    try:
        from services.database import db_service
        await db_service.connect()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.warning(f"Database connection failed, using mock data: {e}")
    
    # TODO: Initialize Redis cache
    
    yield
    
    # Shutdown
    logger.info("Shutting down gravity optimizer service")
    
    # Deregister service
    try:
        from clients.service_registry import service_registry
        await service_registry.deregister('gravity-optimizer')
        await service_registry.disconnect()
    except Exception:
        pass
    
    # Close database connections
    try:
        from services.database import db_service
        await db_service.disconnect()
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title=settings.service_name,
    version=settings.version,
    description="Gravity flow optimization service for Munbon irrigation system",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.version,
        "description": "Gravity flow optimizer for irrigation water delivery",
        "api_docs": "/docs",
        "api_prefix": settings.api_prefix
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # TODO: Add actual health checks (database, redis, etc.)
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "checks": {
            "database": "ok",  # TODO: Implement actual check
            "redis": "ok",     # TODO: Implement actual check
            "network_topology": "loaded"  # TODO: Implement actual check
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )