from __future__ import annotations

from typing import Awaitable, Callable, Literal, Optional

from clients.scheduler_principal_client import (
    SchedulerPrincipalAuthError,
    SchedulerPrincipalClient,
    SchedulerPrincipalContractError,
    SchedulerPrincipalUnavailableError,
)
from config import settings
from db.planning_depth_repository import (
    PlanningDepthConflictError,
    create_planning_depth_submission,
    get_active_planning_depth_submission,
    load_planning_depth_roster_snapshot,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from schemas.planning_depth import (
    EffectivePrincipalProjection,
    PlanningDepthActiveSubmission,
    PlanningDepthSubmissionReceipt,
    PlanningDepthSubmissionRequest,
)
from services.planning_depth_submission import (
    PlanningDepthRateLimitExceeded,
    PlanningDepthValidationError,
    consume_planning_depth_write_limit,
    expand_planning_depth_values,
)
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response


class NoStorePlanningDepthRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        route_handler = super().get_route_handler()

        async def no_store_route_handler(request: Request) -> Response:
            try:
                response = await route_handler(request)
            except RequestValidationError as exc:
                response = await request_validation_exception_handler(request, exc)
            except StarletteHTTPException as exc:
                headers = dict(exc.headers or {})
                headers["Cache-Control"] = "no-store"
                raise HTTPException(
                    status_code=exc.status_code,
                    detail=exc.detail,
                    headers=headers,
                ) from exc
            response.headers["Cache-Control"] = "no-store"
            return response

        return no_store_route_handler


router = APIRouter(
    prefix="/api/v1/water-planning/planning-depth-submissions",
    tags=["planning-depth-submissions"],
    route_class=NoStorePlanningDepthRoute,
)
security = HTTPBearer(auto_error=False)


def get_database_manager(request: Request):
    manager = getattr(request.app.state, "db_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="planning_depth_database_unavailable",
        )
    return manager


def get_scheduler_principal_client(request: Request) -> SchedulerPrincipalClient:
    return SchedulerPrincipalClient(
        http_client=getattr(request.app.state, "http_client", None)
    )


def get_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return credentials.credentials


async def load_operator_principal(
    bearer_token: str,
    client: SchedulerPrincipalClient,
) -> EffectivePrincipalProjection:
    try:
        principal = await client.load_effective_principal(bearer_token)
    except SchedulerPrincipalAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
    except SchedulerPrincipalUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="scheduler_principal_unavailable",
        ) from exc
    except SchedulerPrincipalContractError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="scheduler_principal_contract_error",
        ) from exc
    if "operator" not in principal.effective_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return principal


@router.post(
    "",
    response_model=PlanningDepthSubmissionReceipt,
    status_code=status.HTTP_201_CREATED,
)
async def submit_planning_depth(
    request: PlanningDepthSubmissionRequest,
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
            receipt = await create_planning_depth_submission(
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


@router.get("/active", response_model=PlanningDepthActiveSubmission)
async def get_active_planning_depth(
    project_key: Literal["mun-bon"] = Query(),
    week_key: str = Query(pattern=r"^[0-9]{4}-W[0-9]{2}$"),
    bearer_token: str = Depends(get_bearer_token),
    principal_client: SchedulerPrincipalClient = Depends(
        get_scheduler_principal_client
    ),
    database_manager=Depends(get_database_manager),
) -> PlanningDepthActiveSubmission:
    await load_operator_principal(bearer_token, principal_client)
    try:
        async with database_manager.get_connection() as connection:
            active = await get_active_planning_depth_submission(
                connection,
                project_key,
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
