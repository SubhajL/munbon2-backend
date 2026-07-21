"""Shared Scheduler-side guards for operator control mutations."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from typing import Optional

from fastapi import HTTPException, Request, status

from core.config import settings
from core.device_capabilities import empty_device_capability_snapshot
from core.operator_confirmation import (
    OperatorConfirmationError,
    require_exact_confirmation,
)
from core.redis import RedisClient
from services.clients.auth_step_up_client import (
    AuthStepUpClient,
    StepUpContractError,
    StepUpRejectedError,
    StepUpUnavailableError,
)
from services.clients.scada_operator_client import (
    ScadaOperatorClient,
    ScadaOperatorContractError,
    ScadaOperatorUnavailableError,
)

_STEP_UP_REPLAY_TTL_SECONDS = 120
_OPERATOR_UPSTREAM_TIMEOUT_SECONDS = 5.0


async def get_auth_step_up_client():
    try:
        client = AuthStepUpClient(settings.auth_service_url)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth step-up configuration is invalid",
        ) from error
    try:
        yield client
    finally:
        await client.close()


async def get_scada_operator_client():
    if not settings.scheduler_scada_base_url:
        yield None
        return
    try:
        client = ScadaOperatorClient(settings.scheduler_scada_base_url)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="live SCADA configuration is invalid",
        ) from error
    try:
        yield client
    finally:
        await client.close()


def require_operator_confirmation(
    presented: Optional[str],
    action: str,
    identity: str,
    version: Optional[int] = None,
) -> None:
    try:
        require_exact_confirmation(presented, action, identity, version)
    except OperatorConfirmationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


def _access_token(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token is required for step-up",
        )
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token is required for step-up",
        )
    return token.strip()


async def require_operator_step_up(
    request: Request, presented_code: Optional[str], client: AuthStepUpClient
) -> str:
    access_token = _access_token(request)
    try:
        await client.verify_step_up(access_token, presented_code or "")
    except StepUpRejectedError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operator step-up was rejected",
        ) from error
    except (StepUpUnavailableError, StepUpContractError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="operator step-up is unavailable",
        ) from error
    return access_token


async def consume_operator_step_up(
    replay_store: RedisClient, actor_subject: str, presented_code: str
) -> None:
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        f"{actor_subject}\0{presented_code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    try:
        consumed = await replay_store.set_if_absent(
            f"operator-step-up-used:{digest}",
            "1",
            expire=_STEP_UP_REPLAY_TTL_SECONDS,
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="operator step-up replay protection is unavailable",
        ) from error
    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operator step-up code was already used",
        )


async def require_live_scada_capability(
    request: Request,
    access_token: str,
    client: Optional[ScadaOperatorClient],
) -> None:
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="live SCADA capability evidence is unavailable",
        )
    try:
        async with asyncio.timeout(_OPERATOR_UPSTREAM_TIMEOUT_SECONDS):
            _, live = await asyncio.gather(
                client.is_healthy(),
                client.get_device_capabilities(access_token),
            )
    except (
        TimeoutError,
        ScadaOperatorUnavailableError,
        ScadaOperatorContractError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="live SCADA capability evidence is unavailable",
        ) from error
    pinned = getattr(request.app.state, "device_capability_snapshot", None)
    if pinned is None:
        pinned = empty_device_capability_snapshot()
    if (
        live.capability_release_id != pinned.capability_release_id
        or live.capability_hash != pinned.capability_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="live SCADA capability does not match Scheduler capability",
        )


async def require_positive_operator_action(
    *,
    request: Request,
    action: str,
    identity: str,
    version: Optional[int],
    confirmation: Optional[str],
    step_up_code: Optional[str],
    step_up_client: AuthStepUpClient,
    replay_store: RedisClient,
    actor_subject: str,
    scada_client: Optional[ScadaOperatorClient],
    require_live_scada: bool,
) -> None:
    require_operator_confirmation(confirmation, action, identity, version)
    access_token = await require_operator_step_up(request, step_up_code, step_up_client)
    if require_live_scada:
        await require_live_scada_capability(request, access_token, scada_client)
    await consume_operator_step_up(replay_store, actor_subject, step_up_code or "")
