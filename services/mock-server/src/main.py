"""
Unified Mock Server for Water Planning BFF Development
Provides mock endpoints for all required services in a single server
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from datetime import datetime

from services import (
    ros_mock,
    gis_mock,
    awd_mock,
    flow_mock,
    scheduler_mock,
    weather_mock,
    sensor_mock
)
from data.mock_data import MockDataManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Initialize mock data manager
mock_data_manager = MockDataManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Unified Mock Server on port 3099")
    await mock_data_manager.initialize()
    logger.info("Mock data initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Unified Mock Server")


# Create FastAPI app
app = FastAPI(
    title="Unified Mock Server for WD BFF",
    description="Mock server providing all service endpoints for Water Planning BFF development",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all service routers with their respective prefixes
app.include_router(ros_mock.router, prefix="/ros", tags=["ROS"])
app.include_router(gis_mock.router, prefix="/gis", tags=["GIS"])
app.include_router(awd_mock.router, prefix="/awd", tags=["AWD"])
app.include_router(flow_mock.router, prefix="/flow", tags=["Flow Monitoring"])
app.include_router(scheduler_mock.router, prefix="/scheduler", tags=["Scheduler"])
app.include_router(weather_mock.router, prefix="/weather", tags=["Weather"])
app.include_router(sensor_mock.router, prefix="/sensor", tags=["Sensor Data"])

# Root health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "unified-mock-server",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "ros": "available",
            "gis": "available",
            "awd": "available",
            "flow_monitoring": "available",
            "scheduler": "available",
            "weather": "available",
            "sensor_data": "available"
        }
    }

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Unified Mock Server",
        "description": "Mock server for Water Planning BFF development",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "services": {
                "ros": "/ros/api/v1/*",
                "gis": "/gis/api/v1/*",
                "awd": "/awd/api/v1/*",
                "flow": "/flow/api/v1/*",
                "scheduler": "/scheduler/api/v1/*",
                "weather": "/weather/api/v1/*",
                "sensor": "/sensor/api/v1/*"
            }
        },
        "mock_data_status": {
            "sections": len(mock_data_manager.sections),
            "plots": len(mock_data_manager.plots),
            "water_levels": len(mock_data_manager.water_levels),
            "gates": len(mock_data_manager.gates)
        }
    }

@app.get("/api/v1/mock/reset")
async def reset_mock_data():
    """Reset all mock data to initial state"""
    await mock_data_manager.reset()
    return {"status": "reset", "message": "Mock data reset to initial state"}

@app.get("/api/v1/mock/status")
async def get_mock_status():
    """Get current status of mock data"""
    return {
        "data_counts": {
            "sections": len(mock_data_manager.sections),
            "plots": len(mock_data_manager.plots),
            "water_levels": len(mock_data_manager.water_levels),
            "demands": len(mock_data_manager.demands),
            "gates": len(mock_data_manager.gates),
            "schedules": len(mock_data_manager.schedules)
        },
        "last_reset": mock_data_manager.last_reset,
        "data_version": mock_data_manager.version
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3099,
        reload=True,
        log_level="info"
    )