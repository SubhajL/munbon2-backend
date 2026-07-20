from typing import Any, Dict
from functools import partial
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from core.config import settings
from core.database import Base, engine
from core.redis import get_redis
from core.logger import setup_logging, get_logger
from api.middleware.request_id import RequestIDMiddleware
from api.v1.routes import api_router
from models import *  # noqa: F401,F403
from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from core.device_capabilities import (
    DeviceCapabilityConfigError,
    empty_device_capability_snapshot,
    load_device_capability_snapshot,
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

    # PR 5.2a: rebuild the restart-safe authority mutex from the append-only
    # transition truth. Degrade-on-failure like the device-snapshot loader below: a
    # recovery error (e.g. migrations not yet applied) must NOT boot-loop the pod —
    # `/ready` still gates traffic on the control tables' presence.
    try:
        from core.database import AsyncSessionLocal
        from repositories.control_plan_repository import (
            PostgresControlPlanRepository,
        )
        from services.open_loop_execution_service import OpenLoopExecutionService

        async with AsyncSessionLocal() as session:
            # The service logs the reconcile counts (loguru, correctly formatted).
            await OpenLoopExecutionService(
                PostgresControlPlanRepository()
            ).recover_execution_state(session)
    except Exception as error:
        logger.error(
            "authority recovery failed; continuing, control tables gate "
            "readiness: {}",
            str(error),
        )

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
# PR 4.3c-1: load the device-capability snapshot ONCE at startup. A broken/tampered
# config must NOT take down the whole service (health, draft, list) — it only
# disables ACTIVATION, so log loudly and fall back to the empty dark default (zero
# machine-capable gates ⇒ activation fails closed). An unset path is the same
# default without an error.
try:
    app.state.device_capability_snapshot = load_device_capability_snapshot(
        {
            "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": (
                settings.scheduler_device_capability_snapshot_path or ""
            )
        }
    )
except DeviceCapabilityConfigError as error:
    logger.error(
        "device-capability snapshot failed to load; activation disabled",
        error=str(error),
    )
    app.state.device_capability_snapshot = empty_device_capability_snapshot()

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Bounded request id so approval evidence can capture a safe correlation id.
# (The fail-open AuthMiddleware is intentionally NOT wired.)
app.add_middleware(RequestIDMiddleware)


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
    """Dependency-truth readiness: 503 unless every tracked migration matches,
    all control tables exist, and the Redis revocation store is reachable. The
    body carries only safe status strings (no hostname/cred/exception leaks)."""
    from core.readiness import check_scheduler_readiness

    redis_client = await get_redis()
    result = await check_scheduler_readiness(engine, redis_client)
    body = {
        "status": "ready" if result.ready else "not ready",
        "checks": result.checks,
    }
    if not result.ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body,
        )
    return body


# Prometheus scrape endpoint (PR 6.4). Metrics are DB-derived at scrape time (the dispatch
# tick is a separate short-lived process, so in-process counters would never be scraped).
# Unauthenticated like /health; exposes only aggregate control-plane counts. DEPLOY NOTE:
# restrict the scrape port to the internal monitoring interface at the network layer.
@app.get("/metrics")
async def metrics_endpoint():
    from api.metrics import render_metrics
    from core.control_metrics import METRICS_CONTENT_TYPE

    redis_client = await get_redis()
    body = await render_metrics(engine, redis_client)
    return Response(content=body, media_type=METRICS_CONTENT_TYPE)


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
