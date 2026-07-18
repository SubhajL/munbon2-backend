"""Draft control-plan endpoints (PR 4.3a) — non-commanding, immutable drafts."""

import json
from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from algorithms.hydraulic_schedule_optimizer import HydraulicScheduleError
from core.config import settings
from core.control_plan import (
    DraftInputError,
    InternalPlanInvariantError,
    UpstreamContractError,
)
from core.predicted_delivery_ledger import (
    GateEvent,
    LedgerProjectionError,
    ScheduledRequirement,
    evaluate_safe_handover,
    predicted_delivery_ledger_sha256,
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
)
from schemas.control_plan import (
    ControlPlanLedgerResponse,
    DraftControlPlanRequest,
    DraftControlPlanResponse,
    GatePlanEventOut,
    HandoverVerdictOut,
    LedgerEntryOut,
    LifecycleActionRequest,
    MemberBoundsOut,
    PlanRequirementOut,
    PlanTransitionOut,
    PredictionMemberStatusOut,
    ReasonedActionRequest,
    ShadowApprovalRequest,
    SupersedeRequest,
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
    ControlPlanLifecycleService,
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
from repositories.control_plan_repository import TransitionConflictError

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


def get_lifecycle_service() -> ControlPlanLifecycleService:
    return ControlPlanLifecycleService(
        repository=PostgresControlPlanRepository()
    )


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
        logger.error("ledger load failed", error=str(error))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="draft store is unavailable",
        )
    return _build_or_503(_ledger_response_from_record, record)


def _bounds(values: list) -> MemberBoundsOut:
    present = [v for v in values if v is not None]
    lower = min(present) if present else None
    upper = max(present) if present else None
    nominal = values[1] if len(values) == 3 else None
    return MemberBoundsOut(lower_bound=lower, nominal=nominal, upper_bound=upper)


def _ledger_response_from_record(record) -> ControlPlanLedgerResponse:
    entries = []
    for entry in record.ledger_entries:
        delivered = _bounds(
            [
                entry.lower_delivered_m3,
                entry.nominal_delivered_m3,
                entry.upper_delivered_m3,
            ]
        )
        # remaining is a bound: worst case (most remaining) comes from the
        # least-delivered member, best case from the most-delivered member.
        def _remaining(delivered_value):
            return (
                None
                if delivered_value is None
                else max(0.0, entry.required_volume_m3 - delivered_value)
            )

        remaining = MemberBoundsOut(
            lower_bound=_remaining(delivered.upper_bound),
            nominal=_remaining(delivered.nominal),
            upper_bound=_remaining(delivered.lower_bound),
        )
        entries.append(
            LedgerEntryOut(
                requirement_id=entry.requirement_id,
                section_id=entry.section_id,
                checkpoint_index=entry.checkpoint_index,
                checkpoint_at=entry.checkpoint_at,
                status=entry.status,
                required_volume_m3=entry.required_volume_m3,
                approved_excess_m3=entry.approved_excess_m3,
                delivered_m3=delivered,
                path_in_transit_m3=_bounds(
                    [
                        entry.lower_path_in_transit_m3,
                        entry.nominal_path_in_transit_m3,
                        entry.upper_path_in_transit_m3,
                    ]
                ),
                remaining_m3=remaining,
                checkpoint_reasons=list(entry.checkpoint_reasons),
            )
        )
    handover = [
        HandoverVerdictOut(
            gate_id=gate_id,
            requirement_ids=requirement_ids,
            is_safe=verdict.is_safe,
            reasons=list(verdict.reasons),
        )
        for gate_id, requirement_ids, verdict in _handover_verdicts(record)
    ]
    return ControlPlanLedgerResponse(
        plan_id=record.plan_id,
        plan_version=record.plan_version,
        prediction_run_id=record.prediction_run_id,
        prediction_status=record.prediction_status,
        ledger_sha256=predicted_delivery_ledger_sha256(record.ledger_entries),
        entries=entries,
        handover=handover,
    )


def _handover_verdicts(record):
    gate_events = [
        GateEvent(
            gate_id=event.gate_id,
            kind=event.event_kind,
            planned_at=event.planned_at,
            target_position_m=event.target_position_m,
        )
        for event in record.events
    ]
    all_completed = record.prediction_status == "completed"
    by_gate: dict = {}
    for requirement in record.requirements:
        if requirement.planning_disposition != "scheduled":
            continue
        by_gate.setdefault(requirement.gate_id, []).append(
            ScheduledRequirement(
                requirement_id=str(requirement.requirement_id),
                section_id=requirement.section_id,
                gate_id=requirement.gate_id,
                required_volume_m3=requirement.required_volume_m3,
                approved_excess_m3=requirement.approved_excess_m3,
                path_reach_ids=tuple(
                    json.loads(requirement.path_reach_ids_document_text)
                ),
                window_start=requirement.window_start,
                window_end=requirement.window_end,
            )
        )
    for gate_id in sorted(by_gate):
        gate_requirements = by_gate[gate_id]
        verdict = evaluate_safe_handover(
            gate_requirements,
            record.ledger_entries,
            gate_events,
            all_members_completed=all_completed,
        )
        yield (
            gate_id,
            [r.requirement_id for r in gate_requirements],
            verdict,
        )


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
        ),
    ):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    # Corruption of stored evidence (bad hash, malformed history/document) is a
    # fail-closed 503, matching the draft GET path — never an opaque 500.
    if isinstance(
        error,
        (LifecycleHistoryCorruptError, DraftStoreCorruptError, StoredDocumentError),
    ):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        )
    if isinstance(error, SQLAlchemyError):
        logger.error("lifecycle store failed", error=str(error))
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
