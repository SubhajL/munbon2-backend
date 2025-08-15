from fastapi import APIRouter
from .endpoints import schedule, operations, teams, monitoring, adaptation

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(schedule.router, prefix="/schedule", tags=["schedule"])
api_router.include_router(operations.router, prefix="/operations", tags=["operations"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(adaptation.router, prefix="/adaptation", tags=["adaptation"])