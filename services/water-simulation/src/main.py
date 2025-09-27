"""
Water Simulation Service - Main Application
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info(f"Starting {settings.service_name} v{settings.version}")
    logger.info(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    logger.info(f"Service endpoints:")
    logger.info(f"  - ROS: {settings.ros_service_url}")
    logger.info(f"  - Flow: {settings.flow_service_url}")
    logger.info(f"  - Gate: {settings.gate_service_url}")
    logger.info(f"  - GIS: {settings.gis_service_url}")
    
    # Initialize database
    from sqlalchemy.ext.asyncio import create_async_engine
    from src.core.models import Base
    
    engine = create_async_engine(settings.database_url)
    
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized")
    
    # Initialize service clients
    from src.clients.ros_client import ROSClient
    from src.clients.flow_client import FlowMonitoringClient
    from src.clients.gate_client import GateControlClient
    from src.clients.gis_client import GISClient
    
    # Test service connections
    service_status = {
        "ROS": False,
        "Flow": False,
        "Gate": False,
        "GIS": False
    }
    
    try:
        ros_client = ROSClient(settings.ros_service_url)
        service_status["ROS"] = await ros_client.health_check()
    except Exception as e:
        logger.warning(f"ROS service not available: {e}")
    
    try:
        flow_client = FlowMonitoringClient(settings.flow_service_url)
        service_status["Flow"] = await flow_client.health_check()
    except Exception as e:
        logger.warning(f"Flow service not available: {e}")
    
    try:
        gate_client = GateControlClient(settings.gate_service_url)
        service_status["Gate"] = await gate_client.health_check()
    except Exception as e:
        logger.warning(f"Gate service not available: {e}")
    
    try:
        gis_client = GISClient(settings.gis_service_url)
        service_status["GIS"] = await gis_client.health_check()
    except Exception as e:
        logger.warning(f"GIS service not available: {e}")
    
    logger.info(f"Service connectivity: {service_status}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Water Simulation Service")
    
    # Close database connections
    await engine.dispose()
    
    # Close service client connections
    for client in [ros_client, flow_client, gate_client, gis_client]:
        try:
            await client.close()
        except:
            pass


# Create FastAPI application
app = FastAPI(
    title=settings.service_name,
    version=settings.version,
    description="""
    Water Simulation Service for irrigation system modeling and optimization.
    
    ## Features
    - Scenario-based water distribution simulation
    - Multi-objective optimization (efficiency, fairness, energy)
    - Integration with ROS, Flow Monitoring, Gate Control, and GIS services
    - Comprehensive analysis and reporting
    - What-if scenario comparison
    
    ## Key Endpoints
    - **Scenarios**: Create and manage simulation scenarios
    - **Simulations**: Run simulations and track progress
    - **Analysis**: Analyze results and generate insights
    - **Forecasting**: Predict water demand patterns
    """,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.version,
        "api_docs": "/docs",
        "api_prefix": settings.api_prefix,
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check database connectivity
    db_healthy = False
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_healthy = True
        await engine.dispose()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    # Check Redis connectivity
    redis_healthy = False
    try:
        import aioredis
        redis = await aioredis.from_url(settings.redis_url)
        await redis.ping()
        redis_healthy = True
        await redis.close()
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
    
    # Overall health status
    is_healthy = db_healthy  # Redis is optional
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": settings.service_name,
        "version": settings.version,
        "checks": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "services": {
                "ros": "unknown",
                "flow": "unknown",
                "gate": "unknown",
                "gis": "unknown"
            }
        }
    }


@app.get("/info")
async def service_info():
    """Get service information and configuration"""
    return {
        "service": settings.service_name,
        "version": settings.version,
        "configuration": {
            "simulation_time_step_minutes": settings.simulation_time_step_minutes,
            "max_simulation_days": settings.max_simulation_days,
            "optimization": {
                "max_iterations": settings.optimization_max_iterations,
                "convergence_threshold": settings.optimization_convergence_threshold
            }
        },
        "integrated_services": {
            "ros": settings.ros_service_url,
            "flow": settings.flow_service_url,
            "gate": settings.gate_service_url,
            "gis": settings.gis_service_url
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )