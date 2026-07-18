from typing import AsyncGenerator, Dict, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from .database import SessionLocal
from .redis import RedisClient, get_redis as _get_redis
from .config import settings
from .logger import get_logger
from .auth import (
    InvalidClaimsError,
    policy_from_settings,
    token_revocation_key,
    validate_access_token_claims,
)

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer()

# Role hierarchy: a higher role satisfies every lower requirement.
_ROLE_IMPLICATIONS = {
    "admin": {"admin", "supervisor", "operator", "field_team"},
    "supervisor": {"supervisor", "operator", "field_team"},
    "operator": {"operator", "field_team"},
    "field_team": {"field_team"},
}


def expand_effective_roles(roles) -> set:
    """Expand held roles into every role they satisfy via the hierarchy."""
    effective: set = set()
    for role in roles:
        effective |= _ROLE_IMPLICATIONS.get(role, {role})
    return effective


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database dependency"""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> RedisClient:
    """Redis dependency"""
    return await _get_redis()


async def verify_token(token: str) -> Optional[Dict]:
    """Verify a JWT and its claim shape, returning the raw payload or None.

    The HS256 algorithm is pinned from settings — NEVER read from the token
    header — ``exp`` is required, and the claim shape is validated against the
    active claim policy. Any failure returns None (the caller maps to 401).
    """
    try:
        # Audience/issuer/type are validated in a mode-aware way by
        # validate_access_token_claims (compat may omit them), so PyJWT's own
        # aud check is disabled here — but exp is always required and the
        # algorithm is pinned from settings, never from the token header.
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp"], "verify_aud": False},
            leeway=settings.jwt_clock_skew_seconds,
        )
        validate_access_token_claims(payload, policy_from_settings(settings))
        return payload
    except InvalidClaimsError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    redis: RedisClient = Depends(get_redis)
) -> Dict:
    """Get the current authenticated user, fail-closed on the revocation store.

    Decode FIRST (a garbage token is 401 before any store I/O), then look up a
    HASHED revocation key. A missing/erroring/timing-out revocation store is a
    503 — a store outage must NEVER let a token through.
    """
    token = credentials.credentials

    payload = await verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if getattr(redis, "client", None) is None:
        logger.error(
            "revocation store is not connected; refusing the token (fail-closed)"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="token revocation store is unavailable",
        )
    try:
        revoked = await _token_is_revoked(redis, token, payload)
    except Exception as error:  # noqa: BLE001 — any store error must fail closed
        logger.error(
            "revocation store lookup failed; refusing the token (fail-closed)",
            error=str(error),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="token revocation store is unavailable",
        )
    if revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    return payload


async def _token_is_revoked(
    redis: RedisClient, token: str, payload: Dict
) -> bool:
    """Dual-read the hardened hashed key AND the legacy raw-token key.

    A revocation written by an as-yet-unmigrated logout/auth service (the old
    ``token:blacklist:<raw-token>`` scheme) must still deny the token, so BOTH
    key schemes are consulted; either hit revokes. Raises on store error so the
    caller can fail closed.
    """
    for key in (
        token_revocation_key(token, payload),
        f"token:blacklist:{token}",
    ):
        if await redis.exists(key):
            return True
    return False


async def get_current_active_user(
    current_user: Dict = Depends(get_current_user)
) -> Dict:
    """Get current active user"""

    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return current_user


async def verify_websocket_token(
    token: str,
    redis: RedisClient
) -> Optional[Dict]:
    """Verify token for WebSocket connections (fail-closed revocation)."""

    payload = await verify_token(token)
    if not payload:
        return None
    if getattr(redis, "client", None) is None:
        return None
    try:
        if await _token_is_revoked(redis, token, payload):
            return None
    except Exception:  # noqa: BLE001 — a store outage denies the connection
        return None
    return payload


def require_strict_approval_policy() -> None:
    """Fail closed when the service is not running the strict claim policy.

    In compat mode approve-for-shadow is UNAVAILABLE (503) so a compat token can
    read/draft but can never mint a trusted (strict-policy) shadow approval.
    """
    if settings.jwt_claim_policy_mode != "strict":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "approve-for-shadow requires the strict claim policy; the "
                "service is running in compat mode"
            ),
        )


class RoleChecker:
    """Role-based access control with a role hierarchy.

    A higher role satisfies a lower requirement (admin > supervisor > operator
    > field_team). Authorization ALWAYS requires a matching effective role: a
    role-less token is 403 even in compat mode. Compat relaxes only the token
    CLAIM SHAPE (missing iss/aud/jti), never the RBAC decision — the current
    issuer already emits roles, so a role-less principal on a control-plane
    mutation route is a bypass, not a legacy caller. A present-but-insufficient
    role is always 403.
    """

    def __init__(self, allowed_roles) -> None:
        self.allowed_roles = set(allowed_roles)

    def __call__(
        self,
        request: Request,
        user: Dict = Depends(get_current_user),
    ) -> Dict:
        roles = user.get("roles")
        if not isinstance(roles, list):
            roles = []
        roles = [role for role in roles if isinstance(role, str)]

        if roles and expand_effective_roles(roles) & self.allowed_roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


# Convenience role checkers — declare the MINIMUM role; the hierarchy grants
# every higher role automatically.
require_admin = RoleChecker({"admin"})
require_operator = RoleChecker({"operator"})
require_supervisor = RoleChecker({"supervisor"})
require_field_team = RoleChecker({"field_team"})


# Staged rollout guard: strict mode requires the issuer to already emit a
# non-blank `jti` (and roles). Ship compat first, upgrade the issuer, THEN flip
# to strict — see the PR 4.4a-1 external-ops runbook. Warn loudly if strict is
# active so a premature flip (which 401s every current no-jti token) is visible.
if settings.jwt_claim_policy_mode == "strict":
    logger.warning(
        "jwt_claim_policy_mode=strict is active: every access token MUST carry "
        "a non-blank jti and roles or it will be rejected (401). Confirm the "
        "issuer emits jti before enabling strict."
    )
