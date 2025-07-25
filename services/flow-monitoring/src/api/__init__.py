from fastapi import APIRouter
from .flow import router as flow_router
from .volume import router as volume_router
from .level import router as level_router
from .sensors import router as sensors_router
from .analytics import router as analytics_router
from .hydraulics import router as hydraulics_router
from .gates import router as gates_router
from .gate_config import router as gate_config_router

# Create main API router
router = APIRouter()

# Include sub-routers
router.include_router(flow_router, prefix="/flow", tags=["Flow Data"])
router.include_router(volume_router, prefix="/volume", tags=["Volume Data"])
router.include_router(level_router, prefix="/level", tags=["Water Level"])
router.include_router(sensors_router, prefix="/sensors", tags=["Sensors"])
router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
router.include_router(hydraulics_router, prefix="/hydraulics", tags=["Hydraulic Modeling"])
router.include_router(gates_router, prefix="/gates", tags=["Gate Control"])
router.include_router(gate_config_router, tags=["Gate Configuration"])

__all__ = ["router"]