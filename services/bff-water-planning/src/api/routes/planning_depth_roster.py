from __future__ import annotations

from api.routes.planning_depths import (
    NoStorePlanningDepthRoute,
    get_bearer_token,
    get_database_manager,
    get_scheduler_principal_client,
    load_operator_principal,
)
from clients.scheduler_principal_client import SchedulerPrincipalClient
from db.planning_depth_repository import load_authoritative_planning_depth_roster
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.planning_depth_roster import PlanningDepthRosterProjection


router = APIRouter(
    prefix="/api/v1/water-planning/planning-depth-roster",
    tags=["planning-depth-roster"],
    route_class=NoStorePlanningDepthRoute,
)


@router.get("/v1", response_model=PlanningDepthRosterProjection)
async def get_planning_depth_roster(
    bearer_token: str = Depends(get_bearer_token),
    principal_client: SchedulerPrincipalClient = Depends(
        get_scheduler_principal_client
    ),
    database_manager=Depends(get_database_manager),
) -> PlanningDepthRosterProjection:
    await load_operator_principal(bearer_token, principal_client)
    try:
        async with database_manager.get_connection() as connection:
            return await load_authoritative_planning_depth_roster(connection)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="canonical_roster_unavailable",
        ) from exc
