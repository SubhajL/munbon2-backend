"""Read-only operator projections over the scheduler control-plan lifecycle (PR 4.4 / 4.4a-3).

Authenticated GETs — a cursor-paginated LIST plus per-plan detail, prediction
coverage, ledger, and lifecycle history — let operator clients inspect exact
shadow-plan state without direct scheduler DB access. Everything is validated
pass-through: upstream `unavailable | infeasible | invalidated | stale` states
are preserved, never collapsed to zero/empty/success. There are NO writes. The
list page is BOUNDED (header columns + a derived lifecycle/approval-trust flag —
never optimizer_result / requirements / events / transitions / ledger /
trajectory) and, on any upstream failure, fails closed rather than fabricating an
empty page.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from core import get_logger
from clients.scheduler_client import (
    SchedulerAuthError,
    SchedulerBadRequestError,
    SchedulerClient,
    SchedulerContractError,
    SchedulerControlPlanError,
    SchedulerControlPlanNotFoundError,
    SchedulerUnavailableError,
)
from schemas.control_plan import (
    ControlPlanLedgerProjection,
    ControlPlanLifecycleHistory,
    ControlPlanListPageProjection,
    ControlPlanPredictionCoverage,
    ControlPlanProjection,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/control-plans", tags=["control-plans"])

# The scheduler remains the JWT + Redis-blacklist authority; the BFF forwards the
# operator's bearer token and never issues a service token of its own.
security = HTTPBearer(auto_error=True)


def get_scheduler_client(request: Request) -> SchedulerClient:
    # Reuse the lifespan-owned pooled AsyncClient (PR 4.4a-2) so control-plan
    # reads share one connection pool with the readiness probes instead of
    # opening a fresh client per request.
    http_client = getattr(request.app.state, "http_client", None)
    return SchedulerClient(http_client=http_client)


def get_operator_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    return credentials.credentials


def _raise_for_client_error(exc: SchedulerControlPlanError) -> "HTTPException":
    """Map a fail-closed scheduler client error to the BFF status that preserves
    the upstream state (404 stays 404, auth stays 401/403, client 400/422 stay
    400/422, unavailable → 503, malformed/other → 502). Never leaks transport/host
    internals."""
    if isinstance(exc, SchedulerControlPlanNotFoundError):
        return HTTPException(status_code=404, detail=exc.detail)
    if isinstance(exc, SchedulerAuthError):
        return HTTPException(status_code=exc.status_code, detail=exc.detail)
    if isinstance(exc, SchedulerBadRequestError):
        # A CLIENT error (stale/cross-filter cursor, invalid filter) — forward the
        # exact status so it is NOT misreported as an upstream outage (502/503).
        return HTTPException(status_code=exc.status_code, detail=exc.detail)
    if isinstance(exc, SchedulerUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, SchedulerContractError):
        return HTTPException(
            status_code=502,
            detail="scheduler returned a malformed control-plan response",
        )
    # SchedulerUpstreamError and any other control-plan error.
    return HTTPException(status_code=502, detail=str(exc))


def _verify_identity(
    returned_plan_id: UUID,
    returned_plan_version: int,
    requested_plan_id: UUID,
    requested_plan_version: int,
) -> None:
    """Fail closed if the scheduler returns a plan other than the one requested.

    The scheduler keys these routes by (plan_id, plan_version), so a mismatch can
    only come from an upstream cache/routing defect — surfacing the wrong plan as
    a confident 200 would corrupt exact inspection, so treat it as contract drift
    (502) rather than trusting it."""
    if returned_plan_id != requested_plan_id or (
        returned_plan_version != requested_plan_version
    ):
        logger.warning(
            "scheduler returned a mismatched control-plan identity",
            requested_plan_id=str(requested_plan_id),
            requested_plan_version=requested_plan_version,
            returned_plan_id=str(returned_plan_id),
            returned_plan_version=returned_plan_version,
        )
        raise HTTPException(
            status_code=502,
            detail="scheduler returned a mismatched control-plan identity",
        )


async def _load_control_plan_projection(
    client: SchedulerClient, plan_id: UUID, plan_version: int, token: str
) -> ControlPlanProjection:
    """Fetch + strictly validate the plan detail; drift → 502 (fail-closed)."""
    try:
        payload = await client.get_control_plan_projection(plan_id, plan_version, token)
    except SchedulerControlPlanError as exc:
        raise _raise_for_client_error(exc) from exc
    try:
        projection = ControlPlanProjection.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "scheduler plan projection failed strict validation",
            plan_id=str(plan_id),
            plan_version=plan_version,
        )
        raise HTTPException(
            status_code=502,
            detail="scheduler control-plan response failed validation",
        ) from exc
    _verify_identity(projection.plan_id, projection.plan_version, plan_id, plan_version)
    return projection


async def _load_prediction_coverage(
    client: SchedulerClient, plan_id: UUID, plan_version: int, token: str
) -> ControlPlanPredictionCoverage:
    """Fetch + strictly validate the scheduler's DEDICATED bounded coverage read
    (PR 4.4b-3), not a projection of the full detail; drift → 502 (fail-closed)."""
    try:
        payload = await client.get_prediction_coverage(plan_id, plan_version, token)
    except SchedulerControlPlanError as exc:
        raise _raise_for_client_error(exc) from exc
    try:
        coverage = ControlPlanPredictionCoverage.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "scheduler prediction coverage failed strict validation",
            plan_id=str(plan_id),
            plan_version=plan_version,
        )
        raise HTTPException(
            status_code=502,
            detail="scheduler control-plan response failed validation",
        ) from exc
    _verify_identity(coverage.plan_id, coverage.plan_version, plan_id, plan_version)
    return coverage


async def _load_lifecycle_history(
    client: SchedulerClient, plan_id: UUID, plan_version: int, token: str
) -> ControlPlanLifecycleHistory:
    """Fetch + strictly validate the scheduler's DEDICATED bounded lifecycle-history
    read (PR 4.4b-3), not a projection of the full detail; drift → 502."""
    try:
        payload = await client.get_lifecycle_history(plan_id, plan_version, token)
    except SchedulerControlPlanError as exc:
        raise _raise_for_client_error(exc) from exc
    try:
        history = ControlPlanLifecycleHistory.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "scheduler lifecycle history failed strict validation",
            plan_id=str(plan_id),
            plan_version=plan_version,
        )
        raise HTTPException(
            status_code=502,
            detail="scheduler control-plan response failed validation",
        ) from exc
    _verify_identity(history.plan_id, history.plan_version, plan_id, plan_version)
    return history


async def _load_control_plan_ledger(
    client: SchedulerClient, plan_id: UUID, plan_version: int, token: str
) -> ControlPlanLedgerProjection:
    try:
        payload = await client.get_control_plan_ledger(plan_id, plan_version, token)
    except SchedulerControlPlanError as exc:
        raise _raise_for_client_error(exc) from exc
    try:
        ledger = ControlPlanLedgerProjection.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "scheduler ledger projection failed strict validation",
            plan_id=str(plan_id),
            plan_version=plan_version,
        )
        raise HTTPException(
            status_code=502,
            detail="scheduler control-plan ledger failed validation",
        ) from exc
    _verify_identity(ledger.plan_id, ledger.plan_version, plan_id, plan_version)
    return ledger


@router.get("", response_model=ControlPlanListPageProjection)
async def list_control_plans(
    limit: int = Query(25, ge=1, le=50),
    cursor: Optional[str] = Query(default=None),
    lifecycle_state: Optional[str] = Query(default=None),
    horizon_start_gte: Optional[str] = Query(default=None),
    horizon_end_lte: Optional[str] = Query(default=None),
    requirement_run_id: Optional[str] = Query(default=None),
    requirement_version: Optional[int] = Query(default=None),
    input_content_hash: Optional[str] = Query(default=None),
    model_snapshot_id: Optional[str] = Query(default=None),
    model_release_content_hash: Optional[str] = Query(default=None),
    prediction_run_id: Optional[str] = Query(default=None),
    prediction_content_sha256: Optional[str] = Query(default=None),
    token: str = Depends(get_operator_bearer_token),
    client: SchedulerClient = Depends(get_scheduler_client),
) -> ControlPlanListPageProjection:
    """Bearer-forwarded, strict-validated pass-through of one bounded list page.

    Fails closed: any upstream failure raises through the scheduler taxonomy (it
    is NEVER turned into an empty page), and a page that fails strict validation
    (added/renamed/retyped field) is a 502, not a partial projection."""
    filters = {
        "lifecycle_state": lifecycle_state,
        "horizon_start_gte": horizon_start_gte,
        "horizon_end_lte": horizon_end_lte,
        "requirement_run_id": requirement_run_id,
        "requirement_version": requirement_version,
        "input_content_hash": input_content_hash,
        "model_snapshot_id": model_snapshot_id,
        "model_release_content_hash": model_release_content_hash,
        "prediction_run_id": prediction_run_id,
        "prediction_content_sha256": prediction_content_sha256,
    }
    try:
        payload = await client.list_control_plans(
            filters=filters, cursor=cursor, limit=limit, bearer_token=token
        )
    except SchedulerControlPlanError as exc:
        raise _raise_for_client_error(exc) from exc
    try:
        return ControlPlanListPageProjection.model_validate(payload)
    except ValidationError as exc:
        logger.warning("scheduler control-plan list failed strict validation")
        raise HTTPException(
            status_code=502,
            detail="scheduler control-plan list failed validation",
        ) from exc


@router.get(
    "/{plan_id}/versions/{plan_version}",
    response_model=ControlPlanProjection,
)
async def get_control_plan_projection(
    plan_id: UUID,
    plan_version: int = Path(gt=0),
    token: str = Depends(get_operator_bearer_token),
    client: SchedulerClient = Depends(get_scheduler_client),
) -> ControlPlanProjection:
    return await _load_control_plan_projection(client, plan_id, plan_version, token)


@router.get(
    "/{plan_id}/versions/{plan_version}/prediction-coverage",
    response_model=ControlPlanPredictionCoverage,
)
async def get_prediction_coverage(
    plan_id: UUID,
    plan_version: int = Path(gt=0),
    token: str = Depends(get_operator_bearer_token),
    client: SchedulerClient = Depends(get_scheduler_client),
) -> ControlPlanPredictionCoverage:
    # PR 4.4b-3: read the scheduler's DEDICATED bounded coverage endpoint rather
    # than projecting a subset out of the full detail. Deployment ordering (no
    # feature flag): the scheduler must ship this endpoint before the BFF calls it
    # — otherwise the 404 fails closed here rather than fabricating coverage.
    return await _load_prediction_coverage(client, plan_id, plan_version, token)


@router.get(
    "/{plan_id}/versions/{plan_version}/ledger",
    response_model=ControlPlanLedgerProjection,
)
async def get_control_plan_ledger(
    plan_id: UUID,
    plan_version: int = Path(gt=0),
    token: str = Depends(get_operator_bearer_token),
    client: SchedulerClient = Depends(get_scheduler_client),
) -> ControlPlanLedgerProjection:
    return await _load_control_plan_ledger(client, plan_id, plan_version, token)


@router.get(
    "/{plan_id}/versions/{plan_version}/lifecycle-history",
    response_model=ControlPlanLifecycleHistory,
)
async def get_lifecycle_history(
    plan_id: UUID,
    plan_version: int = Path(gt=0),
    token: str = Depends(get_operator_bearer_token),
    client: SchedulerClient = Depends(get_scheduler_client),
) -> ControlPlanLifecycleHistory:
    # PR 4.4b-3: read the scheduler's DEDICATED bounded lifecycle-history endpoint
    # rather than projecting the full detail (same deployment ordering as coverage).
    return await _load_lifecycle_history(client, plan_id, plan_version, token)
