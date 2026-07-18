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
from core.deps import get_current_user, get_db
from core.logger import get_logger
from repositories.control_plan_repository import (
    DraftPlanRecord,
    DraftStoreCorruptError,
    PlanContentConflictError,
    PostgresControlPlanRepository,
)
from schemas.control_plan import (
    DraftControlPlanRequest,
    DraftControlPlanResponse,
    GatePlanEventOut,
    PlanRequirementOut,
    PlanTransitionOut,
    PredictionMemberStatusOut,
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
        lifecycle_state=record.lifecycle_state,
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
        optimizer_result=json.loads(record.optimizer_result_document_text),
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
                    else json.loads(entry.path_reach_ids_document_text)
                ),
                rotation_windows=(
                    None
                    if entry.rotation_windows_document_text is None
                    else json.loads(entry.rotation_windows_document_text)
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
                occurred_at=entry.occurred_at,
            )
            for entry in record.transitions
        ],
        created_by_subject=record.created_by_subject,
        created_at=record.created_at,
    )


@router.post("/drafts", response_model=DraftControlPlanResponse)
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
    except (UpstreamContractViolation, UpstreamContractError) as error:
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
    return _response_from_record(record)


@router.get(
    "/{plan_id}/versions/{plan_version}",
    response_model=DraftControlPlanResponse,
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
    return _response_from_record(record)
