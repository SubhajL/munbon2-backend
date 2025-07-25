import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from config import settings
from api import router as api_router
from api import gates as gates_api
from core.logging import setup_logging
from core.metrics import setup_metrics
from db.connections import DatabaseManager
from services.kafka_consumer import KafkaConsumerService
from controllers.dual_mode_gate_controller import DualModeGateController


# Setup structured logging
setup_logging(settings.log_level)
logger = structlog.get_logger()

# Global instances
db_manager = DatabaseManager()
kafka_consumer = KafkaConsumerService()
gate_controller = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global gate_controller
    
    logger.info("Starting Flow Monitoring Service", port=settings.port)
    
    # Startup
    try:
        # Initialize database connections
        await db_manager.connect_all()
        logger.info("Database connections established")
        
        # Initialize gate controller
        network_file = "src/munbon_network_final.json"
        geometry_file = "canal_geometry_template.json"
        gate_controller = DualModeGateController(db_manager, network_file, geometry_file)
        gates_api.gate_controller = gate_controller
        logger.info("Gate controller initialized")
        
        # Start Kafka consumer
        asyncio.create_task(kafka_consumer.start())
        logger.info("Kafka consumer started")
        
        # Setup metrics
        setup_metrics()
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down Flow Monitoring Service")
        
        # Stop Kafka consumer
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