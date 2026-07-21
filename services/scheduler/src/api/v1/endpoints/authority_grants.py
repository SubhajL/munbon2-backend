"""Authority-grant REST surface (PR 7.1a) — represent authority, execute nothing.

AUTHZ (safety valence): review/grant/renew require supervisor + the STRICT
claim policy (503 in compat — no grant can be issued in any tracked
deployment); revoke requires only supervisor and deliberately works in compat
(the safety brake precedes the external trust cutover, mirroring the 5.2b hold
precedent); reads are operator. Fail-closed taxonomy: corruption → 503, never
a best-effort body.
"""

from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import (
    build_authorization_evidence,
    policy_from_settings,
    principal_from_user,
)
from core.authority_grant import (
    AuthorityEvidenceCorruptError,
    AuthorityEvidenceError,
    AuthorityHistoryCorruptError,
    ExecutionAuthorityError,
)
from core.config import settings
from core.control_plan_lifecycle import LifecycleHistoryCorruptError
from core.deps import (
    get_current_user,
    get_db,
    require_operator,
    require_strict_approval_policy,
    require_supervisor,
)
from core.device_capabilities import empty_device_capability_snapshot
from core.logger import get_logger
from repositories.control_plan_repository import (
    AuthorityEvidenceStoreCorruptError,
    AuthorityGrantConflictError,
    AuthorityGrantCorruptError,
    DraftStoreCorruptError,
    PlanNotShadowActiveForAuthorityError,
    PostgresControlPlanRepository,
)
from schemas.authority_grant import (
    AuthorityGrantRenewalRequest,
    AuthorityGrantRequest,
    AuthorityGrantResponse,
    AuthorityGrantReviewResponse,
    AuthorityGrantRevocationRequest,
    build_grant_response,
)
from services.authority_grant_service import (
    AuthorityGrantService,
    RenewalNotAllowedError,
    UnknownAuthorityGrantError,
    UnknownPlanForGrantError,
)

router = APIRouter()
logger = get_logger(__name__)


def get_authority_grant_service(request: Request) -> AuthorityGrantService:
    # The 6.1a snapshot loaded once at startup; an unwired app state degrades to
    # the empty dark default (zero grantable gates -> every scope validation
    # fails closed), never an AttributeError.
    snapshot = getattr(request.app.state, "device_capability_snapshot", None)
    if snapshot is None:
        snapshot = empty_device_capability_snapshot()
    return AuthorityGrantService(PostgresControlPlanRepository(), snapshot=snapshot)


def _actor_subject(current_user: Dict) -> str:
    subject = current_user.get("sub") or current_user.get("user_id")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token carries no subject",
        )
    return str(subject)


def _map_authority_errors(error: Exception) -> HTTPException:
    if isinstance(error, (UnknownPlanForGrantError, UnknownAuthorityGrantError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, ExecutionAuthorityError) and error.reason_code in {
        "evidence_corrupt",
        "intent_evidence_corrupt",
    }:
        logger.error("authority grant evidence corruption: {}", error.reason_code)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="authority grant evidence is unavailable",
        )
    if isinstance(error, (AuthorityEvidenceError, ExecutionAuthorityError)):
        # Both are bounded validation refusals of the would-be grant (the
        # execution predicate runs as grant/review preflight) -> 422, never 500.
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        )
    if isinstance(
        error,
        (
            AuthorityGrantConflictError,
            RenewalNotAllowedError,
            PlanNotShadowActiveForAuthorityError,
        ),
    ):
        # PlanNotShadowActive... = the plan's lifecycle changed concurrently
        # under the authority lock: an honest state conflict, not a 500.
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(
        error,
        (
            AuthorityHistoryCorruptError,
            AuthorityEvidenceCorruptError,
            AuthorityEvidenceStoreCorruptError,
            AuthorityGrantCorruptError,
            DraftStoreCorruptError,
            LifecycleHistoryCorruptError,
        ),
    ):
        # Stored-evidence corruption is an availability fault, never a 500 that
        # leaks internals and never a trusted-looking body.
        logger.error("authority grant store corruption: {}", type(error).__name__)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="authority grant evidence is unavailable",
        )
    raise error


async def _run(action):
    try:
        return await action()
    except Exception as error:  # noqa: BLE001 - mapped to the bounded taxonomy
        raise _map_authority_errors(error)


def _build_evidence(request: Request, current_user: Dict, evidence_refs):
    return build_authorization_evidence(
        principal=principal_from_user(current_user),
        request_id=getattr(request.state, "request_id", None),
        policy=policy_from_settings(settings),
        evidence_refs=evidence_refs,
    )


@router.post(
    "/reviews",
    response_model=AuthorityGrantReviewResponse,
    dependencies=[
        Depends(require_supervisor),
        Depends(require_strict_approval_policy),
    ],
)
async def review_authority_grant(
    body: AuthorityGrantRequest,
    db: AsyncSession = Depends(get_db),
    service: AuthorityGrantService = Depends(get_authority_grant_service),
):
    """Dry-run the FULL grant validation; persists nothing."""
    digest = await _run(lambda: service.review_authority_grant(db, body.to_candidate()))
    return AuthorityGrantReviewResponse(would_grant_content_sha256=digest)


@router.post(
    "",
    response_model=AuthorityGrantResponse,
    dependencies=[
        Depends(require_supervisor),
        Depends(require_strict_approval_policy),
    ],
)
async def grant_execution_authority(
    body: AuthorityGrantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: AuthorityGrantService = Depends(get_authority_grant_service),
):
    view = await _run(
        lambda: service.grant_execution_authority(
            db,
            body.to_candidate(),
            actor_subject=_actor_subject(current_user),
            reason=body.reason,
            authorization_evidence=_build_evidence(
                request, current_user, body.evidence_manifest.refs
            ),
        )
    )
    return build_grant_response(view)


@router.post(
    "/{grant_id}/renewals",
    response_model=AuthorityGrantResponse,
    dependencies=[
        Depends(require_supervisor),
        Depends(require_strict_approval_policy),
    ],
)
async def renew_authority_grant(
    grant_id: UUID,
    body: AuthorityGrantRenewalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: AuthorityGrantService = Depends(get_authority_grant_service),
):
    view = await _run(
        lambda: service.renew_authority_grant(
            db,
            grant_id,
            new_expires_at=body.new_expires_at,
            shadow_evidence_sha256=body.shadow_evidence_sha256,
            hold_drill_evidence_sha256=body.hold_drill_evidence_sha256,
            rollback_drill_evidence_sha256=body.rollback_drill_evidence_sha256,
            evidence_manifest=body.evidence_manifest.model_dump(),
            reason=body.reason,
            actor_subject=_actor_subject(current_user),
            authorization_evidence=_build_evidence(
                request, current_user, body.evidence_manifest.refs
            ),
        )
    )
    return build_grant_response(view)


@router.post(
    "/{grant_id}/revocations",
    response_model=AuthorityGrantResponse,
    dependencies=[Depends(require_supervisor)],
)
async def revoke_authority_grant(
    grant_id: UUID,
    body: AuthorityGrantRevocationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: AuthorityGrantService = Depends(get_authority_grant_service),
):
    """Terminal + idempotent; NO strict-policy gate (safety brake in compat)."""
    view = await _run(
        lambda: service.revoke_authority_grant(
            db,
            grant_id,
            reason=body.reason,
            actor_subject=_actor_subject(current_user),
            authorization_evidence=_build_evidence(request, current_user, []),
        )
    )
    return build_grant_response(view)


@router.get(
    "/{grant_id}",
    response_model=AuthorityGrantResponse,
    dependencies=[Depends(require_operator)],
)
async def get_authority_grant(
    grant_id: UUID,
    response: Response,
    db: AsyncSession = Depends(get_db),
    service: AuthorityGrantService = Depends(get_authority_grant_service),
):
    view = await _run(lambda: service.get_authority_grant(db, grant_id))
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"authority grant {grant_id} does not exist",
        )
    response.headers["Cache-Control"] = "no-store"
    return build_grant_response(view)


@router.get(
    "",
    response_model=AuthorityGrantResponse,
    dependencies=[Depends(require_operator)],
)
async def get_authority_grant_for_plan(
    response: Response,
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    service: AuthorityGrantService = Depends(get_authority_grant_service),
):
    view = await _run(
        lambda: service.get_authority_grant_for_plan(db, plan_id, plan_version)
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"plan {plan_id} v{plan_version} holds no authority grant",
        )
    response.headers["Cache-Control"] = "no-store"
    return build_grant_response(view)
