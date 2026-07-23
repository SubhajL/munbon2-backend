from typing import Awaitable, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from core.auth import principal_from_user
from core.deps import (
    expand_effective_roles,
    get_current_user,
    get_redis,
    require_field_team,
)
from core.redis import RedisClient
from schemas.auth import (
    CANONICAL_EFFECTIVE_ROLES,
    EffectivePrincipalProjection,
)


class NoStoreAuthRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        route_handler = super().get_route_handler()

        async def no_store_route_handler(request: Request) -> Response:
            try:
                response = await route_handler(request)
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


router = APIRouter(route_class=NoStoreAuthRoute)
principal_security = HTTPBearer(auto_error=False)


async def get_principal_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(principal_security),
    redis: RedisClient = Depends(get_redis),
) -> Dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await get_current_user(credentials=credentials, redis=redis)


def require_principal_field_team(
    request: Request,
    current_user: Dict = Depends(get_principal_current_user),
) -> Dict:
    return require_field_team(request, current_user)


@router.get("/principal", response_model=EffectivePrincipalProjection)
async def get_effective_principal(
    current_user: Dict = Depends(require_principal_field_team),
) -> EffectivePrincipalProjection:
    principal = principal_from_user(current_user)
    effective_roles = sorted(
        expand_effective_roles(principal["roles"]) & CANONICAL_EFFECTIVE_ROLES
    )
    return EffectivePrincipalProjection(
        subject=principal["subject"],
        effective_roles=effective_roles,
    )
