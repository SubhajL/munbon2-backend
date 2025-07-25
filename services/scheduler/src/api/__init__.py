from fastapi import APIRouter
from .schedule import router as schedule_router
from .demands import router as demands_router
from .field_ops import router as field_ops_router

# Create main API router
router = APIRouter()

# Include sub-routers
router.include_router(schedule_router, prefix="/schedule", tags=["Schedule Management"])
router.include_router(demands_router, prefix="/scheduler", tags=["Demand Processing"])
router.include_router(field_ops_router, prefix="/field-ops", tags=["Field Operations"])

__all__ = ["router"]