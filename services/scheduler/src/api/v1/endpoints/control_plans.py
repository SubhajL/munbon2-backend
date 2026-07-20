"""Draft control-plan endpoints (PR 4.3a) — non-commanding, immutable drafts."""

import json
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from algorithms.hydraulic_schedule_optimizer import HydraulicScheduleError
from core.config import settings
from core.control_plan_cursor import CursorError
from core.control_plan import (
    DraftInputError,
    InternalPlanInvariantError,
    UpstreamContractError,
)
from core.predicted_delivery_ledger import (
    LedgerProjectionError,
)
from core.auth import (
    build_authorization_evidence,
    policy_from_settings,
    principal_from_user,
)
from core.deps import (
    get_current_user,
    get_db,
    require_operator,
    require_strict_approval_policy,
    require_supervisor,
)
from core.logger import get_logger
from repositories.control_plan_repository import (
    DraftPlanRecord,
    DraftStoreCorruptError,
    PlanContentConflictError,
    PostgresControlPlanRepository,
    UnknownCampaignError,
)
from repositories.control_plan_projection_repository import (
    PostgresControlPlanProjectionRepository,
    ProjectionCorruptError,
)
from services.open_loop_execution_service import (
    ExecutionModeNotEnabledError,
    HoldNotAllowedError,
    OpenLoopExecutionService,
    OpenLoopPlanNotFoundError,
)
from schemas.control_plan import (
    ActivateRequest,
    ControlPlanExecutionStateResponse,
    ControlPlanIntentTimelineResponse,
    ControlPlanLedgerResponse,
    ControlPlanLifecycleHistoryResponse,
    ControlPlanListFilters,
    ControlPlanListPage,
    ControlPlanPredictionCoverageResponse,
    ControlPlanReadbackObservationsResponse,
    DraftControlPlanRequest,
    DraftControlPlanResponse,
    GatePlanEventOut,
    LifecycleActionRequest,
    PlanRequirementOut,
    PlanTransitionOut,
    PredictionMemberStatusOut,
    ReasonedActionRequest,
    ShadowApprovalRequest,
    SupersedeRequest,
)
from core.command_intent import NonActivatablePlanError
from core.open_loop_execution import IntentExecutionCorruptError
from core.device_capabilities import (
    CapabilityMembershipError,
    DeviceCapabilityConfigError,
)
from services.clients.control_client_errors import (
    FlowLineageConflictError,
    PredictionRequestRejectedError,
    RequirementStateError,
    UpstreamContractViolation,
    UpstreamUnavailableError,
)
from services.clients.control_flow_client import ControlFlowClient
from services.clients.ros_gis_requirements_client import (
    RosGisRequirementsClient,
)
from services.control_plan_service import (
    ControlPlanDraftService,
    ModelIncompleteError,
    PlanNotFoundError,
    parse_member_summaries,
)
from services.control_plan_lifecycle_service import (
    ActivationNotAllowedError,
    ControlPlanLifecycleService,
    HandoverUnsafeError,
    PlanNotFoundError as LifecyclePlanNotFoundError,
    SupersedeScopeError,
    current_lifecycle_state,
)
from core.control_plan_lifecycle import (
    ApprovalCoverageError,
    ApprovalFreezeMismatchError,
    IllegalTransitionError,
    LifecycleHistoryCorruptError,
)
from repositories.control_plan_repository import (
    ScopeConflictError,
    TransitionConflictError,
)

router = APIRouter()
logger = get_logger(__name__)


async def get_control_plan_service(request: Request):
    ros_client = RosGisRequirementsClient(settings.ros_gis_url)
    flow_client = ControlFlowClient(settings.flow_monitoring_url)
    try:
        yield ControlPlanDraftService(
            ros_client=ros_client,
            flow_client=flow_client,
            repository=PostgresControlPlanRepository(),
            optimizer=request.app.state.optimize_limited_adjustment_plan,
            run_blocking=run_in_threadpool,
            model_step_seconds=settings.control_model_step_seconds,
            max_intermediate_trims=settings.control_max_intermediate_trims,
            solver_timeout_seconds=settings.optimization_timeout_seconds,
        )
    finally:
        await ros_client.aclose()
        await flow_client.aclose()


def get_lifecycle_service(request: Request) -> ControlPlanLifecycleService:
    # The 6.1a snapshot loaded once at startup. getattr guards any wiring that
    # mounts this router without main.py's startup assignment; the service turns a
    # None into the empty dark default, so no lifecycle endpoint can AttributeError.
    snapshot = getattr(request.app.state, "device_capability_snapshot", None)
    return ControlPlanLifecycleService(
        repository=PostgresControlPlanRepository(),
        device_capability_snapshot=snapshot,
    )


def get_control_plan_projection_repository() -> (
    PostgresControlPlanProjectionRepository
):
    return PostgresControlPlanProjectionRepository()


def get_open_loop_service() -> OpenLoopExecutionService:
    # PR 5.2b: reads execution mode / pre-move window from settings; the worker only
    # claims in shadow mode and NEVER dispatches.
    return OpenLoopExecutionService(repository=PostgresControlPlanRepository())


class StoredDocumentError(Exception):
    """A stored canonical document could not be parsed (corruption → 503)."""


def _parse_stored_json(text):
    try:
        return json.loads(text)
    except ValueError as error:
        raise StoredDocumentError(
            f"a stored control-plan document is corrupt: {error}"
        ) from error


def _build_or_503(builder, record):
    """Build a response, mapping a corrupt stored document to a 503 rather than
    letting it escape the handler as an opaque 500."""
    try:
        return builder(record)
    except StoredDocumentError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        )


def _actor_subject(current_user: Dict) -> str:
    subject = current_user.get("sub") or current_user.get("user_id")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token carries no subject",
        )
    return str(subject)


def _response_from_record(record: DraftPlanRecord) -> DraftControlPlanResponse:
    return DraftControlPlanResponse(
        plan_id=record.plan_id,
        plan_version=record.plan_version,
        campaign_id=record.campaign_id,
        # The current lifecycle state is DERIVED from the append-only transition
        # history; the run header's lifecycle_state is frozen creation metadata.
        lifecycle_state=current_lifecycle_state(record),
        input_content_hash=record.input_content_hash,
        draft_content_hash=record.draft_content_hash,
        requirement_run_id=record.requirement_run_id,
        requirement_version=record.requirement_version,
        model_snapshot_id=record.model_snapshot_id,
        model_release_id=record.model_release_id,
        model_release_content_hash=record.model_release_content_hash,
        optimizer_status=record.optimizer_status,
        prediction_status=record.prediction_status,
        prediction_run_id=record.prediction_run_id,
        prediction_member_statuses=[
            PredictionMemberStatusOut(**entry)
            for entry in parse_member_summaries(record)
        ],
        horizon_start=record.horizon_start,
        horizon_end=record.horizon_end,
        model_step_seconds=record.model_step_seconds,
        max_intermediate_trims=record.max_intermediate_trims,
        optimizer_result=_parse_stored_json(record.optimizer_result_document_text),
        requirements=[
            PlanRequirementOut(
                requirement_id=str(entry.requirement_id),
                run_id=str(entry.run_id),
                source_version=entry.source_version,
                service_date=entry.service_date,
                section_id=entry.section_id,
                zone=entry.zone,
                required_volume_m3=entry.required_volume_m3,
                window_start=entry.window_start,
                window_end=entry.window_end,
                quality=entry.quality,
                published_at=entry.published_at,
                as_of_date=entry.as_of_date,
                source_data_status=entry.source_data_status,
                planning_disposition=entry.planning_disposition,
                delivery_node_id=entry.delivery_node_id,
                gate_id=entry.gate_id,
                maximum_delivery_m3s=entry.maximum_delivery_m3s,
                approved_excess_m3=entry.approved_excess_m3,
                travel_delay_seconds=entry.travel_delay_seconds,
                minimum_delivery_fraction=entry.minimum_delivery_fraction,
                maximum_delivery_fraction=entry.maximum_delivery_fraction,
                path_reach_ids=(
                    None
                    if entry.path_reach_ids_document_text is None
                    else _parse_stored_json(entry.path_reach_ids_document_text)
                ),
                rotation_windows=(
                    None
                    if entry.rotation_windows_document_text is None
                    else _parse_stored_json(entry.rotation_windows_document_text)
                ),
            )
            for entry in record.requirements
        ],
        events=[
            GatePlanEventOut(
                event_sequence=entry.event_sequence,
                gate_id=entry.gate_id,
                event_kind=entry.event_kind,
                planned_at=entry.planned_at,
                target_position_m=entry.target_position_m,
                source_flow_m3s=entry.source_flow_m3s,
                gate_event_sequence=entry.gate_event_sequence,
                trim_ordinal=entry.trim_ordinal,
            )
            for entry in record.events
        ],
        transitions=[
            PlanTransitionOut(
                transition_sequence=entry.transition_sequence,
                transition_type=entry.transition_type,
                from_state=entry.from_state,
                to_state=entry.to_state,
                actor_subject=entry.actor_subject,
                reason=entry.reason,
                transition_document=(
                    None
                    if entry.transition_document_text is None
                    else _parse_stored_json(entry.transition_document_text)
                ),
                occurred_at=entry.occurred_at,
            )
            for entry in record.transitions
        ],
        created_by_subject=record.created_by_subject,
        created_at=record.created_at,
    )


@router.post(
    "/drafts",
    response_model=DraftControlPlanResponse,
    dependencies=[Depends(require_operator)],
)
async def post_draft_control_plan(
    request_body: DraftControlPlanRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanDraftService = Depends(get_control_plan_service),
):
    actor = _actor_subject(current_user)
    try:
        record, replayed = await service.create_draft(db, request_body, actor)
    except UnknownCampaignError as error:
        # A present campaign_id that references no existing campaign: fail closed
        # (never auto-create a campaign under a caller-chosen id).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        )
    except DraftInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )
    except RequirementStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": error.reason, **error.detail},
        )
    except (PlanContentConflictError, FlowLineageConflictError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        )
    except (
        UpstreamUnavailableError,
        ModelIncompleteError,
        DraftStoreCorruptError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        )
    except (
        UpstreamContractViolation,
        UpstreamContractError,
        LedgerProjectionError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)
        )
    except SQLAlchemyError as error:
        logger.error("draft persistence failed", error=str(error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="draft store is unavailable",
        )
    except (
        PredictionRequestRejectedError,
        InternalPlanInvariantError,
        HydraulicScheduleError,
    ) as error:
        logger.error("draft composition invariant broke", error=str(error))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="draft composition failed on an internal invariant",
        )
    response.status_code = (
        status.HTTP_200_OK if replayed else status.HTTP_201_CREATED
    )
    response.headers["Idempotent-Replay"] = "true" if replayed else "false"
    return _build_or_503(_response_from_record, record)


@router.get(
    "",
    response_model=ControlPlanListPage,
    dependencies=[Depends(require_operator)],
)
async def list_control_plans(
    limit: int = Query(25, ge=1, le=50),
    cursor: Optional[str] = Query(default=None),
    lifecycle_state: Optional[str] = Query(default=None),
    horizon_start_gte: Optional[datetime] = Query(default=None),
    horizon_end_lte: Optional[datetime] = Query(default=None),
    requirement_run_id: Optional[UUID] = Query(default=None),
    requirement_version: Optional[int] = Query(default=None),
    input_content_hash: Optional[str] = Query(default=None),
    model_snapshot_id: Optional[str] = Query(default=None),
    model_release_content_hash: Optional[str] = Query(default=None),
    prediction_run_id: Optional[str] = Query(default=None),
    prediction_content_sha256: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    repository: PostgresControlPlanProjectionRepository = Depends(
        get_control_plan_projection_repository
    ),
):
    """Cursor-paginated, header-only list of control plans (require_operator).

    The response is a BOUNDED projection — no optimizer_result, no prediction
    response, no requirements/events/transitions/ledger, no trajectory. The
    cursor is opaque and bound to this exact filter set: replaying it against a
    different filter set is a 422 (CursorError), never a silently-wrong page.
    """
    _actor_subject(current_user)
    try:
        filters = ControlPlanListFilters(
            lifecycle_state=lifecycle_state,
            horizon_start_gte=horizon_start_gte,
            horizon_end_lte=horizon_end_lte,
            requirement_run_id=requirement_run_id,
            requirement_version=requirement_version,
            input_content_hash=input_content_hash,
            model_snapshot_id=model_snapshot_id,
            model_release_content_hash=model_release_content_hash,
            prediction_run_id=prediction_run_id,
            prediction_content_sha256=prediction_content_sha256,
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid list filter: {error.errors()[0]['msg']}",
        )
    try:
        return await repository.list_plan_summaries(
            db, filters=filters, cursor=cursor, limit=limit
        )
    except CursorError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        )
    except LifecycleHistoryCorruptError as error:
        # A corrupt derived history is fail-closed corruption (503), matching the
        # detail/lifecycle read paths — never an opaque 500.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        )
    except SQLAlchemyError as error:
        logger.error("control-plan list failed", error=str(error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="control-plan store is unavailable",
        )


@router.get(
    "/{plan_id}/versions/{plan_version}",
    response_model=DraftControlPlanResponse,
    dependencies=[Depends(require_operator)],
)
async def get_control_plan_version(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanDraftService = Depends(get_control_plan_service),
):
    _actor_subject(current_user)
    try:
        record = await service.get_draft(db, plan_id, plan_version)
    except PlanNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        )
    except DraftStoreCorruptError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        )
    except SQLAlchemyError as error:
        logger.error("draft load failed", error=str(error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="draft store is unavailable",
        )
    return _build_or_503(_response_from_record, record)


def _projection_or_error(projection, plan_id: UUID, plan_version: int):
    """A bounded read returned None → the plan does not exist (404). A present
    projection is served as-is."""
    if projection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"control plan {plan_id} v{plan_version} not found",
        )
    return projection


def _map_projection_errors(error: Exception, action: str) -> HTTPException:
    """A stored document a bounded read loaded is corrupt (bad hash / bad JSON /
    a null derived history) → fail closed with a 503, matching the detail read
    paths; a store outage is also a 503. Never an opaque 500, never a partial
    projection."""
    if isinstance(error, (ProjectionCorruptError, LifecycleHistoryCorruptError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        )
    if isinstance(error, SQLAlchemyError):
        # loguru positional (an `error=` kwarg with no {error} placeholder is silently dropped).
        logger.error("{} load failed: {}", action, str(error))
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="control-plan store is unavailable",
        )
    raise error


@router.get(
    "/{plan_id}/versions/{plan_version}/prediction-coverage",
    response_model=ControlPlanPredictionCoverageResponse,
    dependencies=[Depends(require_operator)],
)
async def get_control_plan_prediction_coverage(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    repository: PostgresControlPlanProjectionRepository = Depends(
        get_control_plan_projection_repository
    ),
):
    """Bounded prediction-coverage read (require_operator): prediction lineage +
    exact per-member statuses, projected WITHOUT loading the full aggregate. It
    returns the same coverage data as projecting from the full detail."""
    _actor_subject(current_user)
    try:
        coverage = await repository.load_prediction_coverage(
            db, plan_id, plan_version
        )
    except Exception as error:  # noqa: BLE001 — remapped to a typed HTTP status
        raise _map_projection_errors(error, "prediction-coverage")
    return _projection_or_error(coverage, plan_id, plan_version)


@router.get(
    "/{plan_id}/versions/{plan_version}/lifecycle-history",
    response_model=ControlPlanLifecycleHistoryResponse,
    dependencies=[Depends(require_operator)],
)
async def get_control_plan_lifecycle_history(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    repository: PostgresControlPlanProjectionRepository = Depends(
        get_control_plan_projection_repository
    ),
):
    """Bounded lifecycle-history read (require_operator): plan identity + derived
    lifecycle state + the COMPLETE ordered transition history (documents verbatim),
    without loading the run's large documents."""
    _actor_subject(current_user)
    try:
        history = await repository.load_lifecycle_history(
            db, plan_id, plan_version
        )
    except Exception as error:  # noqa: BLE001 — remapped to a typed HTTP status
        raise _map_projection_errors(error, "lifecycle-history")
    return _projection_or_error(history, plan_id, plan_version)


@router.get(
    "/{plan_id}/versions/{plan_version}/ledger",
    response_model=ControlPlanLedgerResponse,
    dependencies=[Depends(require_operator)],
)
async def get_control_plan_ledger(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    repository: PostgresControlPlanProjectionRepository = Depends(
        get_control_plan_projection_repository
    ),
):
    """Bounded predicted-delivery ledger read (require_operator): the EXACT ledger
    response the full ``_assemble`` path produced, projected from the bounded
    ledger/requirement/event rows — never the run's large documents."""
    _actor_subject(current_user)
    try:
        ledger = await repository.load_ledger_projection(
            db, plan_id, plan_version
        )
    except Exception as error:  # noqa: BLE001 — remapped to a typed HTTP status
        raise _map_projection_errors(error, "ledger")
    return _projection_or_error(ledger, plan_id, plan_version)


@router.get(
    "/{plan_id}/versions/{plan_version}/intent-timeline",
    response_model=ControlPlanIntentTimelineResponse,
    dependencies=[Depends(require_operator)],
)
async def get_control_plan_intent_timeline(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    repository: PostgresControlPlanProjectionRepository = Depends(
        get_control_plan_projection_repository
    ),
):
    """Bounded per-intent claimed→dispatched→validated timeline (require_operator):
    the outbox intent + its execution state + its validation receipt. Read-only; no
    command affordance. Delivery is PREDICTED evidence, never observed device state."""
    _actor_subject(current_user)
    try:
        timeline = await repository.load_intent_timeline_projection(
            db, plan_id, plan_version
        )
    except Exception as error:  # noqa: BLE001 — remapped to a typed HTTP status
        raise _map_projection_errors(error, "intent-timeline")
    return _projection_or_error(timeline, plan_id, plan_version)


@router.get(
    "/{plan_id}/versions/{plan_version}/readback-observations",
    response_model=ControlPlanReadbackObservationsResponse,
    dependencies=[Depends(require_operator)],
)
async def get_control_plan_readback_observations(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    repository: PostgresControlPlanProjectionRepository = Depends(
        get_control_plan_projection_repository
    ),
):
    """Bounded shadow readback observations (require_operator): the durable evidence
    behind any drift hold. `unavailable`/null observed level is explicit — never masked."""
    _actor_subject(current_user)
    try:
        observations = await repository.load_readback_observations_projection(
            db, plan_id, plan_version
        )
    except Exception as error:  # noqa: BLE001 — remapped to a typed HTTP status
        raise _map_projection_errors(error, "readback-observations")
    return _projection_or_error(observations, plan_id, plan_version)


@router.get(
    "/{plan_id}/versions/{plan_version}/execution-state",
    response_model=ControlPlanExecutionStateResponse,
    dependencies=[Depends(require_operator)],
)
async def get_control_plan_execution_state(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    repository: PostgresControlPlanProjectionRepository = Depends(
        get_control_plan_projection_repository
    ),
):
    """Bounded plan-level execution posture (require_operator): the DERIVED hold state
    + the ordered held/resumed history. A hold pauses claiming without releasing authority."""
    _actor_subject(current_user)
    try:
        state = await repository.load_execution_state_projection(
            db, plan_id, plan_version
        )
    except Exception as error:  # noqa: BLE001 — remapped to a typed HTTP status
        raise _map_projection_errors(error, "execution-state")
    return _projection_or_error(state, plan_id, plan_version)


def _map_lifecycle_errors(error: Exception) -> HTTPException:
    if isinstance(error, LifecyclePlanNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(
        error,
        (
            IllegalTransitionError,
            TransitionConflictError,
            ApprovalCoverageError,
            SupersedeScopeError,
            ApprovalFreezeMismatchError,
            # PR 4.3c-1 activation conflicts (all fail-closed 409, never 500):
            ActivationNotAllowedError,
            ScopeConflictError,
            CapabilityMembershipError,
            NonActivatablePlanError,
            # PR 4.3c-2 graceful supersede: an unsafe handover is a 409.
            HandoverUnsafeError,
        ),
    ):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    # Corruption of stored evidence (bad hash, malformed history/document) or a
    # broken device-capability config is a fail-closed 503 — never an opaque 500.
    if isinstance(
        error,
        (
            LifecycleHistoryCorruptError,
            DraftStoreCorruptError,
            StoredDocumentError,
            DeviceCapabilityConfigError,
            # A corrupt stored projection reached the safe-handover builder during a
            # supersede-of-active: fail closed with a 503 like the ledger route, not
            # an opaque 500.
            ProjectionCorruptError,
        ),
    ):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        )
    if isinstance(error, SQLAlchemyError):
        # loguru positional (the `error=` kwarg was silently dropped — no cause was logged).
        logger.error("lifecycle store failed: {}", str(error))
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="control-plan store is unavailable",
        )
    raise error


async def _run_lifecycle(action):
    try:
        return _response_from_record(await action())
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001 — remapped to typed HTTP status
        raise _map_lifecycle_errors(error)


@router.post(
    "/{plan_id}/versions/{plan_version}/review",
    response_model=DraftControlPlanResponse,
    dependencies=[Depends(require_supervisor)],
)
async def review_control_plan(
    plan_id: UUID,
    plan_version: int,
    body: LifecycleActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanLifecycleService = Depends(get_lifecycle_service),
):
    actor = _actor_subject(current_user)
    return await _run_lifecycle(
        lambda: service.review_control_plan(
            db, plan_id, plan_version, actor, body.reason
        )
    )


@router.post(
    "/{plan_id}/versions/{plan_version}/approve-for-shadow",
    response_model=DraftControlPlanResponse,
    dependencies=[
        Depends(require_supervisor),
        Depends(require_strict_approval_policy),
    ],
)
async def approve_shadow_plan(
    plan_id: UUID,
    plan_version: int,
    body: ShadowApprovalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanLifecycleService = Depends(get_lifecycle_service),
):
    actor = _actor_subject(current_user)
    policy = policy_from_settings(settings)
    authorization_evidence = build_authorization_evidence(
        principal=principal_from_user(current_user),
        request_id=getattr(request.state, "request_id", None),
        policy=policy,
        evidence_refs=body.evidence_refs,
    )
    return await _run_lifecycle(
        lambda: service.approve_shadow_plan(
            db,
            plan_id,
            plan_version,
            actor,
            body.reason,
            authorization_evidence=authorization_evidence,
            evidence_refs=body.evidence_refs,
        )
    )


@router.post(
    "/{plan_id}/versions/{plan_version}/activate",
    response_model=DraftControlPlanResponse,
    dependencies=[
        Depends(require_supervisor),
        Depends(require_strict_approval_policy),
    ],
)
async def activate_shadow_plan(
    plan_id: UUID,
    plan_version: int,
    body: ActivateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanLifecycleService = Depends(get_lifecycle_service),
):
    """Activate a strict-TRUSTED approved v2 plan: compile its command intents into
    the append-only outbox, take the one-per-scope authority mutex, and grant machine
    authority (shadow mode — nothing dispatches). Dark by default: unreachable in the
    compat claim policy (route + document trust gates) and fails closed on a
    non-member position or an occupied scope."""
    actor = _actor_subject(current_user)
    policy = policy_from_settings(settings)
    authorization_evidence = build_authorization_evidence(
        principal=principal_from_user(current_user),
        request_id=getattr(request.state, "request_id", None),
        policy=policy,
        evidence_refs=body.evidence_refs,
    )
    return await _run_lifecycle(
        lambda: service.activate_control_plan(
            db,
            plan_id,
            plan_version,
            actor,
            body.reason,
            authorization_evidence=authorization_evidence,
        )
    )


@router.post(
    "/{plan_id}/versions/{plan_version}/cancel",
    response_model=DraftControlPlanResponse,
    dependencies=[Depends(require_operator)],
)
async def cancel_control_plan(
    plan_id: UUID,
    plan_version: int,
    body: ReasonedActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanLifecycleService = Depends(get_lifecycle_service),
):
    actor = _actor_subject(current_user)
    return await _run_lifecycle(
        lambda: service.cancel_control_plan(
            db, plan_id, plan_version, actor, body.reason
        )
    )


@router.post(
    "/{plan_id}/versions/{plan_version}/invalidate",
    response_model=DraftControlPlanResponse,
    dependencies=[Depends(require_supervisor)],
)
async def invalidate_control_plan(
    plan_id: UUID,
    plan_version: int,
    body: ReasonedActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanLifecycleService = Depends(get_lifecycle_service),
):
    actor = _actor_subject(current_user)
    return await _run_lifecycle(
        lambda: service.invalidate_control_plan(
            db, plan_id, plan_version, actor, body.reason
        )
    )


@router.post(
    "/{plan_id}/versions/{plan_version}/supersede",
    response_model=DraftControlPlanResponse,
    dependencies=[Depends(require_supervisor)],
)
async def supersede_control_plan(
    plan_id: UUID,
    plan_version: int,
    body: SupersedeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: ControlPlanLifecycleService = Depends(get_lifecycle_service),
):
    actor = _actor_subject(current_user)
    return await _run_lifecycle(
        lambda: service.supersede_control_plan(
            db,
            plan_id,
            plan_version,
            body.successor_plan_id,
            body.successor_plan_version,
            actor,
            body.reason,
        )
    )


@router.post(
    "/{plan_id}/versions/{plan_version}/hold",
    dependencies=[Depends(require_supervisor)],
)
async def hold_control_plan(
    plan_id: UUID,
    plan_version: int,
    body: ReasonedActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: OpenLoopExecutionService = Depends(get_open_loop_service),
):
    """PR 5.2b: place a shadow_active plan on operator hold — pauses local claiming
    WITHOUT a lifecycle transition (the plan keeps its authority mutex). Nothing
    dispatches or actuates."""
    actor = _actor_subject(current_user)
    try:
        await service.hold_control_plan(db, plan_id, plan_version, actor, body.reason)
    except OpenLoopPlanNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    except HoldNotAllowedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    except LifecycleHistoryCorruptError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except SQLAlchemyError as error:
        logger.error("hold store failed: {}", str(error))
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="control-plan store is unavailable",
        )
    return {"plan_id": str(plan_id), "plan_version": plan_version, "status": "held"}


@router.post(
    "/{plan_id}/versions/{plan_version}/resume",
    dependencies=[Depends(require_supervisor)],
)
async def resume_control_plan(
    plan_id: UUID,
    plan_version: int,
    body: ReasonedActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: OpenLoopExecutionService = Depends(get_open_loop_service),
):
    """PR 5.2b: lift an operator hold so local claiming can proceed again. Symmetric
    with hold; also not a lifecycle transition."""
    actor = _actor_subject(current_user)
    try:
        await service.resume_control_plan(db, plan_id, plan_version, actor, body.reason)
    except OpenLoopPlanNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    except HoldNotAllowedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    except LifecycleHistoryCorruptError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except SQLAlchemyError as error:
        logger.error("resume store failed: {}", str(error))
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="control-plan store is unavailable",
        )
    return {"plan_id": str(plan_id), "plan_version": plan_version, "status": "resumed"}


@router.post(
    "/{plan_id}/versions/{plan_version}/advance",
    dependencies=[Depends(require_supervisor)],
)
async def advance_control_plan_execution(
    plan_id: UUID,
    plan_version: int,
    db: AsyncSession = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    service: OpenLoopExecutionService = Depends(get_open_loop_service),
):
    """PR 5.2b: run ONE open-loop worker tick for a plan (the 6.3 dispatcher will
    drive this on a loop). In shadow mode it claims due intents or, on a missed
    deadline, invalidates the remaining campaign and releases authority — all LOCAL,
    NEVER dispatching. Dark in the default 'disabled' execution mode."""
    actor = _actor_subject(current_user)
    try:
        result = await service.advance_open_loop_execution(
            db, plan_id, plan_version, worker_id=actor
        )
    except OpenLoopPlanNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    except ExecutionModeNotEnabledError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    except TransitionConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    except (LifecycleHistoryCorruptError, IntentExecutionCorruptError) as error:
        # A corrupt derived transition history, or a shadow_active plan missing its
        # authority row / a contradictory per-intent history, is fail-closed
        # corruption — a 503 that alarms the dispatcher and triggers recovery, never
        # an opaque 500 (or a 404 that would drop a still-live campaign).
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except SQLAlchemyError as error:
        logger.error("advance store failed: {}", str(error))
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="control-plan store is unavailable",
        )
    return {
        "plan_id": str(plan_id),
        "plan_version": plan_version,
        "action": result.action,
        "claimed": [str(intent_id) for intent_id in result.claimed_intent_ids],
        "invalidated": result.invalidated,
    }
