from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup
    print(f"Starting {settings.SERVICE_NAME} service...")
    yield
    # Shutdown
    print(f"Shutting down {settings.SERVICE_NAME} service...")


app = FastAPI(
    title=settings.SERVICE_NAME,
    description=settings.SERVICE_DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
    }


@app.get("/health/ready")
async def readiness_check() -> dict:
    # Add readiness checks here
    checks = {
        "database": True,  # Replace with actual check
        "external_service": True,  # Replace with actual check
    }
    
    is_ready = all(checks.values())
    
    return {
        "status": "ready" if is_ready else "not_ready",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "checks": checks,
    }