from typing import Any, Dict
from functools import partial
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from core.config import settings
from core.database import Base, engine
from core.redis import get_redis
from core.logger import setup_logging, get_logger
from api.v1.routes import api_router
from models import *  # noqa: F401,F403
from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info(
        f"Starting {settings.service_name} service on port {settings.service_port}"
    )

    # Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")

    # Connect to Redis
    redis_client = await get_redis()  # get singleton
    await redis_client.connect()
    logger.info("Redis client initialized")

    yield

    # Shutdown
    logger.info("Shutting down service")
    logger.info("Service stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Weekly batch scheduler with real-time adaptation for Munbon Irrigation System",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.state.optimize_limited_adjustment_plan = partial(
    optimize_limited_adjustment_plan,
    model_step_seconds=settings.control_model_step_seconds,
    max_intermediate_trims=settings.control_max_intermediate_trims,
    solver_timeout_seconds=settings.optimization_timeout_seconds,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/", response_model=Dict[str, Any])
async def root():
    """Root endpoint"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "docs": "/docs",
    }


# Health check endpoint
@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


# Readiness check endpoint
@app.get("/ready", response_model=Dict[str, Any])
async def readiness_check():
    """Readiness check endpoint"""
    # Check database connection
    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        db_status = "disconnected"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not ready",
                "database": db_status,
                "error": str(e),
            },
        )

    return {
        "status": "ready",
        "database": db_status,
    }


# Include API routes
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
