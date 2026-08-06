from typing import Literal

from api.routes.planning_depths import (
    NoStorePlanningDepthRoute,
    get_bearer_token,
    get_database_manager,
    get_scheduler_principal_client,
    load_operator_principal,
)
from clients.scheduler_principal_client import SchedulerPrincipalClient
from config import settings
from db.planning_depth_repository import (
    PlanningDepthConflictError,
    create_planning_depth_submission_v2,
    get_active_planning_depth_submission_v2,
    load_planning_depth_roster_snapshot,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from schemas.planning_depth_v2 import (
    RID_WEEK_KEY_PATTERN,
    PlanningDepthActiveSubmissionV2,
    PlanningDepthSubmissionReceiptV2,
    PlanningDepthSubmissionRequestV2,
    parse_rid_week_key,
)
from services.planning_depth_submission import (
    PlanningDepthRateLimitExceeded,
    PlanningDepthValidationError,
    consume_planning_depth_write_limit,
    expand_planning_depth_values,
)

router = APIRouter(
    prefix="/api/v2/water-planning/planning-depth-submissions",
    tags=["planning-depth-submissions-v2"],
    route_class=NoStorePlanningDepthRoute,
)


def get_supported_rid_week_key(
    week_key: str = Query(pattern=RID_WEEK_KEY_PATTERN),
) -> str:
    try:
        parse_rid_week_key(week_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="week_key_outside_supported_rid_calendar",
        ) from exc
    return week_key


@router.post(
    "",
    response_model=PlanningDepthSubmissionReceiptV2,
    status_code=status.HTTP_201_CREATED,
)
async def submit_planning_depth_v2(
    request: PlanningDepthSubmissionRequestV2,
    response: Response,
    bearer_token: str = Depends(get_bearer_token),
    principal_client: SchedulerPrincipalClient = Depends(
        get_scheduler_principal_client
    ),
    database_manager=Depends(get_database_manager),
):
    principal = await load_operator_principal(bearer_token, principal_client)
    if settings.planning_depth_writes_enabled != "true":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="planning_depth_writes_disabled",
        )
    try:
        async with database_manager.get_connection() as connection:
            roster = await load_planning_depth_roster_snapshot(connection)
        expand_planning_depth_values(request.levels, roster.sections)
    except PlanningDepthValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.code,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="canonical_roster_unavailable",
        ) from exc

    try:
        await consume_planning_depth_write_limit(
            database_manager.get_redis_client(),
            principal.subject,
            limit=settings.planning_depth_write_limit,
            window_seconds=settings.planning_depth_write_window_seconds,
        )
    except PlanningDepthRateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="planning_depth_write_rate_limited",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="planning_depth_write_limiter_unavailable",
        ) from exc

    try:
        async with database_manager.get_connection() as connection:
            receipt = await create_planning_depth_submission_v2(
                connection,
                request,
                principal,
                roster,
            )
    except PlanningDepthConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="planning_depth_database_unavailable",
        ) from exc
    response.status_code = 200 if receipt.replayed else 201
    return receipt


@router.get("/active", response_model=PlanningDepthActiveSubmissionV2)
async def get_active_planning_depth_v2(
    project_key: Literal["mun-bon"] = Query(),
    calendar_system: Literal["rid-irrigation-v1"] = Query(),
    week_key: str = Depends(get_supported_rid_week_key),
    bearer_token: str = Depends(get_bearer_token),
    principal_client: SchedulerPrincipalClient = Depends(
        get_scheduler_principal_client
    ),
    database_manager=Depends(get_database_manager),
) -> PlanningDepthActiveSubmissionV2:
    await load_operator_principal(bearer_token, principal_client)
    try:
        async with database_manager.get_connection() as connection:
            active = await get_active_planning_depth_submission_v2(
                connection,
                project_key,
                calendar_system,
                week_key,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="planning_depth_database_unavailable",
        ) from exc
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="planning_depth_submission_not_found",
        )
    return active
