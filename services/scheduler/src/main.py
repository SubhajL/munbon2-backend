"""
Weekly Batch Scheduler Service
Coordinates manual field operations with automated gates
"""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from config import settings
from api import router as api_router
from core.logging import setup_logging
from core.metrics import setup_metrics
from db.connections import DatabaseManager
from services.schedule_optimizer import ScheduleOptimizer
from services.demand_aggregator import DemandAggregator
from services.real_time_adapter import RealTimeAdapter

# Setup structured logging
setup_logging(settings.log_level)
logger = structlog.get_logger()

# Global instances
db_manager = DatabaseManager()
schedule_optimizer = None
demand_aggregator = None
real_time_adapter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global schedule_optimizer, demand_aggregator, real_time_adapter
    
    logger.info("Starting Scheduler Service", port=settings.port)
    
    # Startup
    try:
        # Initialize database connections
        await db_manager.connect_all()
        logger.info("Database connections established")
        
        # Initialize services
        schedule_optimizer = ScheduleOptimizer(db_manager)
        demand_aggregator = DemandAggregator(db_manager)
        real_time_adapter = RealTimeAdapter(db_manager, settings.flow_monitoring_url)
        
        # Start background tasks
        asyncio.create_task(real_time_adapter.start_monitoring())
        logger.info("Real-time monitoring started")
        
        # Setup metrics
        setup_metrics()
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down Scheduler Service")
        
        # Stop background tasks
        await real_time_adapter.stop_monitoring()
        
        # Close database connections
        await db_manager.disconnect_all()
        
        logger.info("Cleanup completed")


# Create FastAPI application
app = FastAPI(
    title="Weekly Batch Scheduler Service",
    description="Optimizes weekly irrigation schedules and generates field operation instructions",
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

# Include API routes
app.include_router(api_router, prefix=settings.api_prefix)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = await db_manager.check_health()
    external_services = {
        "flow_monitoring": await real_time_adapter.check_flow_monitoring_health() if real_time_adapter else False
    }
    
    all_healthy = all(health_status.values()) and all(external_services.values())
    
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "service": settings.service_name,
        "version": "1.0.0",
        "databases": health_status,
        "external_services": external_services
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "description": "Weekly Batch Scheduler Service for Munbon Irrigation System",
        "endpoints": {
            "schedule": "/api/v1/schedule/week/{week}",
            "demands": "/api/v1/scheduler/demands",
            "field_ops": "/api/v1/field-ops/instructions/{team}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )