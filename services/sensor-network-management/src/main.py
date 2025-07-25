from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import os
from dotenv import load_dotenv

from api import sensor_router, placement_router, interpolation_router, movement_router
from db import init_databases
from services.sensor_tracker import SensorTracker
from services.placement_optimizer import PlacementOptimizer
from services.interpolation_engine import InterpolationEngine

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_databases()
    
    # Initialize services
    app.state.sensor_tracker = SensorTracker()
    app.state.placement_optimizer = PlacementOptimizer()
    app.state.interpolation_engine = InterpolationEngine()
    
    yield
    
    # Shutdown
    # Clean up resources if needed

app = FastAPI(
    title="Sensor Network Management Service",
    description="Manages mobile sensor placement and data interpolation for Munbon irrigation system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sensor_router, prefix="/api/v1/sensors", tags=["sensors"])
app.include_router(placement_router, prefix="/api/v1/placement", tags=["placement"])
app.include_router(interpolation_router, prefix="/api/v1/interpolation", tags=["interpolation"])
app.include_router(movement_router, prefix="/api/v1/movement", tags=["movement"])

@app.get("/")
async def root():
    return {
        "service": "Sensor Network Management",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "sensor-network-management",
        "sensors": {
            "water_level": int(os.getenv("MAX_WATER_LEVEL_SENSORS", 6)),
            "moisture": int(os.getenv("MAX_MOISTURE_SENSORS", 1))
        }
    }

if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", 3023))
    uvicorn.run(app, host="0.0.0.0", port=port)