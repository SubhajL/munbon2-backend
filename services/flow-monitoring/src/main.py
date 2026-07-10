import asyncio
import os

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from config import settings
from api import router as api_router
from api import gates as gates_api
from api import control as control_api
from api import hydraulics as hydraulics_api
from core.logging import setup_logging
from core.metrics import setup_metrics
from core.network_flow_controller import NetworkFlowController
from db.connections import DatabaseManager
# Kafka consumer is optional; import lazily when configured
from controllers.dual_mode_gate_controller import DualModeGateController


# Setup structured logging
setup_logging(settings.log_level)
logger = structlog.get_logger()

# Global instances
db_manager = DatabaseManager()
kafka_consumer = None
gate_controller = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global gate_controller, kafka_consumer
    
    logger.info("Starting Flow Monitoring Service", port=settings.port)
    
    # Startup
    try:
        # Initialize database connections
        await db_manager.connect_all()
        logger.info("Database connections established")
        
        # Canonical configs, anchored to this file (the old cwd-relative paths only
        # worked when booted from the service root).
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        network_file = os.path.join(config_dir, "network.json")
        geometry_file = os.path.join(config_dir, "canal_geometry.json")

        # Legacy dual-stack quarantine (Wave 1.5, Decision 2): /api/v1/gates/* stays
        # OFF unless explicitly enabled, and when enabled it runs on the canonical
        # configs — never the fragmented munbon_network_final.json (2/57 reachable).
        if settings.gates_api_enabled:
            gate_controller = DualModeGateController(db_manager, network_file, geometry_file)
            gates_api.gate_controller = gate_controller
            gates_api.disabled_reason = None
            logger.info("Gate controller initialized (legacy stack, canonical configs)")
        else:
            gates_api.gate_controller = None
            gates_api.disabled_reason = (
                "legacy gates API disabled by default (PROGRAM_REVIEW_2026-07-09 "
                "decision 2); set GATES_API_ENABLED=true to re-enable it until the "
                "F-02 SCADA bridge replaces this surface"
            )
            logger.info("Legacy gates API disabled (GATES_API_ENABLED=false)")

        # Wire the canonical demand->flow engine (A1-A3 / F-11b / B5) for /api/v1/control/plan.
        control_api.flow_controller = NetworkFlowController(network_file, geometry_file)
        logger.info("Flow controller (demand->reach aggregation) initialized")

        # App-scoped hydraulics service on the same canonical configs (Wave 1.3);
        # replaces per-request construction with a never-connected DatabaseManager.
        from services.hydraulic_service import HydraulicService
        hydraulics_api.hydraulic_service = HydraulicService(db_manager)
        logger.info("Hydraulic service initialized (app-scoped)")
        
        # Start Kafka consumer only if configured
        if settings.kafka_brokers:
            from services.kafka_consumer import KafkaConsumerService
            kafka_consumer = KafkaConsumerService()
            asyncio.create_task(kafka_consumer.start())
            logger.info("Kafka consumer started")
        else:
            logger.info("Kafka disabled (no KAFKA_BROKERS configured)")
        
        # Setup metrics
        setup_metrics()
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down Flow Monitoring Service")
        
        # Stop Kafka consumer
        if kafka_consumer:
            await kafka_consumer.stop()
        
        # Close database connections
        await db_manager.disconnect_all()
        
        logger.info("Cleanup completed")


# Create FastAPI application
app = FastAPI(
    title="Flow Monitoring Service",
    description="Comprehensive hydraulic monitoring including flow rates, water volumes, and levels",
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
    return {
        "status": "healthy" if all(health_status.values()) else "unhealthy",
        "service": settings.service_name,
        "version": "1.0.0",
        "databases": health_status
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "description": "Flow Monitoring Service for Munbon Irrigation System"
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