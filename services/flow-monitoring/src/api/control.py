"""
api.control — C9 control endpoints exposing the NetworkFlowController aggregation engine.

`POST /plan` turns a per-node water demand into the required flow on every network reach
(A1-A3 graph-descendants aggregation, optional B5 conveyance loss). It fails closed on bad
demand (unknown / negative / source-node) with HTTP 400, and never fabricates demand — this
retires the old hardcoded 25.0 m3/s stub (F-03/C9).

`POST /demands` + `GET /demands` are the Wave 2.4 demand/allocation/actual contract
surface: three separate append-only versioned stores (HIGH #8), the ratified
m³/s = m³ ÷ scheduled-delivery-seconds conversion, idempotent replay, and
synthetic-lineage rejection by policy.

`flow_controller` / `demand_store` are module-level singletons set once at app startup
(main.py lifespan), mirroring the api.gates pattern. This module imports only schemas +
core + fastapi (no db / settings) so it stays unit-testable in isolation.
"""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi import Path as FastApiPath
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from core.demand_contract import (
    MAX_CLOCK_SKEW,
    DemandContractError,
    demand_flow_at,
    flow_rate_m3s,
    scheduled_delivery_seconds,
    validate_computed_at,
    validate_intervals_within_period,
    validate_lineage,
    validate_period_bounds,
    validate_timezone_name,
)
from core.demand_store import (
    DemandStoreError,
    DemandStoreUnavailable,
    DuplicateIdempotencyKey,
    ImmutabilityViolation,
    semantic_content_hash,
    VersionConflict,
)
from core.design_profile import DesignProfileError
from core.model_release import HydraulicModelRelease
from core.model_snapshot import ModelSnapshotError
from core.network_transient import (
    BranchAllocation,
    GateFlowEvent,
    OperatorWithdrawalEvent,
    SectionRequirement,
)
from core.branch_split import branch_split_summary
from core.network_flow_controller import (
    LevelReading,
    NetworkFlowController,
)
from core.network_topology import NetworkTopologyError
from core.node_id import NodeIdError, normalize_gate_id, normalize_node_id
from core.prediction_engine import engine_identity_fields
from core.prediction_repository import (
    PREDICTION_RUN_IDENTITY_VERSION,
    PREDICTION_RUN_IDENTITY_VERSION_V2,
    PredictionArtifactCorrupt,
    PredictionRunConflict,
    PredictionRunRecord,
    PredictionStoreUnavailable,
    canonical_json_bytes,
    prediction_run_id_for,
)
from schemas.control import (
    ControlConfigSha256,
    ControlPredictionRequest,
    ControlPredictionResponse,
    DesignProfileRequest,
    DesignProfileResponse,
    DemandPlanInput,
    DemandVersionRef,
    ExcludedTransportReachOut,
    OpeningsRequest,
    OpeningsResponse,
    OpeningsSummary,
    ModelSnapshotResponse,
    PlanCoverage,
    PlanRequest,
    PlanResponse,
    PredictionCoverageOut,
    PredictionFinalFulfillmentOut,
    PredictionInfeasibilityOut,
    PredictionMassBalanceOut,
    PredictionMemberOut,
    PredictionReachSeriesOut,
    PredictionRequirementSeriesOut,
    PredictionTimelineOut,
    PredictionWithdrawalSeriesOut,
    ReachChainageGap,
    ReachFlow,
    ReachOpeningOut,
    RequirementShortfallViolationOut,
    StoredDemandPlanRequest,
    StoredDemandPlanResponse,
    UnavailableReachOut,
    WithdrawalCapacityExceededViolationOut,
    WithdrawalCapacityUnavailableViolationOut,
    WithdrawalShortfallViolationOut,
)
from schemas.demand import (
    CurrentRecordsResponse,
    DemandRecord,
    DemandSubmissionRequest,
    DemandSubmissionResponse,
    RecordResult,
    StoredRecordEnvelope,
)
from services.design_profile_service import DesignProfileService
from services.control_prediction_service import (
    ControlPredictionService,
    PredictionEngineIdentityError,
    PredictionLineageConflictError,
    PredictionModelUnavailableError,
    normalize_prediction_request_identity_v2,
)
from services.prediction_artifact_service import (
    decode_prediction_artifact,
    encode_prediction_artifact,
    summarize_prediction_members,
)

logger = structlog.get_logger()
router = APIRouter()

# Initialized in main.py lifespan; None until then.
flow_controller: Optional[NetworkFlowController] = None
design_profile_service: Optional[DesignProfileService] = None
demand_store = (
    None  # PostgresDemandStore at runtime; any core.demand_store twin in tests
)


def get_flow_controller() -> NetworkFlowController:
    """Dependency: the loaded controller, or 503 if the service has not initialized it."""
    if flow_controller is None:
        raise HTTPException(status_code=503, detail="Flow controller not initialized")
    return flow_controller


def get_design_profile_service() -> DesignProfileService:
    if design_profile_service is None:
        raise HTTPException(
            status_code=503, detail="Design profile service not initialized"
        )
    return design_profile_service


def get_demand_store():
    """Dependency: the versioned contract store, or 503 until lifespan wires it."""
    if demand_store is None:
        raise HTTPException(status_code=503, detail="Demand store not initialized")
    return demand_store


def get_control_prediction_service(
    request: Request,
) -> ControlPredictionService:
    service = getattr(request.app.state, "control_prediction_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Control prediction service not initialized",
        )
    if not isinstance(service, ControlPredictionService):
        raise HTTPException(
            status_code=503,
            detail="Control prediction service state is invalid",
        )
    return service


def get_model_config_sha256(request: Request) -> dict:
    config_sha256 = getattr(request.app.state, "model_config_sha256", None)
    if not isinstance(config_sha256, dict):
        raise HTTPException(
            status_code=503,
            detail="Model config lineage not initialized",
        )
    return config_sha256


def get_hydraulic_model_release(
    request: Request,
) -> HydraulicModelRelease | None:
    if not hasattr(request.app.state, "hydraulic_model_release"):
        raise HTTPException(
            status_code=503,
            detail="Hydraulic model release state not initialized",
        )
    release = request.app.state.hydraulic_model_release
    if release is not None and not isinstance(release, HydraulicModelRelease):
        raise HTTPException(
            status_code=503,
            detail="Hydraulic model release state is invalid",
        )
    return release


def _build_plan_response(
    request: PlanRequest, controller: NetworkFlowController
) -> PlanResponse:
    reach_flow = controller.required_flow_per_reach(
        request.demands,
        apply_losses=request.apply_losses,
        charge_dry_reaches=request.charge_dry_reaches,
        always_wet=request.always_wet,
    )
    head_flow = sum(
        flow for (upstream, _), flow in reach_flow.items() if upstream == "S"
    )
    # Geometry coverage is a STATIC network property, not a loss artifact, so it is
    # reported unconditionally (Wave 2.8a): the itemized lists must agree with the
    # `coverage` roll-up in the SAME payload — gating them on apply_losses made the
    # default response claim "17 missing / 5 gaps" in the summary while the lists read
    # empty. Response ids are CANONICAL COMPACT (Wave 1.2), independent of the survey's
    # irregular spacing. Under apply_losses these are also the reaches that take zero loss
    # on their unsurveyed chainage (the head-gate figure is not full loss coverage, 2.1b).
    missing = [
        [normalize_node_id(u), normalize_node_id(v)]
        for u, v in sorted(controller.reaches_missing_geometry)
    ]
    gaps = [
        ReachChainageGap(upstream=u, downstream=v, gap_m=gap)
        for (u, v), gap in sorted(controller.reaches_with_chainage_gaps.items())
    ]
    # Wave 2.8a: carry each reach's coverage/confidence (terminating-gate calibration +
    # geometry survey) through, plus a network roll-up, so consumers can weigh the plan.
    coverage = controller.reach_coverage
    return PlanResponse(
        reaches=[
            ReachFlow(
                upstream=normalize_node_id(u),
                downstream=normalize_node_id(v),
                required_flow_m3s=q,
                calibration_method=coverage[(u, v)].calibration_method,
                confidence=coverage[(u, v)].confidence,
                has_geometry=coverage[(u, v)].has_geometry,
            )
            for (u, v), q in reach_flow.items()
        ],
        head_flow_m3s=head_flow,
        apply_losses=request.apply_losses,
        charge_dry_reaches=request.charge_dry_reaches,
        reaches_missing_geometry=missing,
        reaches_with_chainage_gaps=gaps,
        coverage=PlanCoverage(**controller.coverage_summary()),
    )


@router.post("/plan", response_model=PlanResponse)
async def plan(
    request: PlanRequest,
    controller: NetworkFlowController = Depends(get_flow_controller),
) -> PlanResponse:
    """Required flow on every reach to serve `request.demands` (fail-closed on bad demand)."""
    try:
        return _build_plan_response(request, controller)
    except (
        NetworkTopologyError
    ) as exc:  # server/config error (subclass of ValueError) -> 503
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (
        ValueError
    ) as exc:  # unknown / negative / non-finite / source demand -> client error
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validated_stored_demand(
    ref: DemandVersionRef, stored: dict, now: datetime
) -> tuple[StoredRecordEnvelope, DemandRecord]:
    try:
        envelope = StoredRecordEnvelope.model_validate(stored)
    except ValidationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"stored demand {ref.logical_key!r} version {ref.version} is invalid",
        ) from exc
    if (envelope.logical_key, envelope.version) != (ref.logical_key, ref.version):
        raise HTTPException(
            status_code=503,
            detail=(
                f"stored demand {ref.logical_key!r} version {ref.version} "
                "identity does not match the requested version"
            ),
        )
    if envelope.content_hash != ref.content_hash:
        raise HTTPException(
            status_code=409,
            detail=(
                f"demand {ref.logical_key!r} version {ref.version} "
                "content hash does not match"
            ),
        )
    try:
        record = DemandRecord.model_validate(envelope.record)
        stored_logical_key, payload, _ = _prepare_demand(record, now)
        recomputed_hash = semantic_content_hash(payload)
    except (ValidationError, DemandContractError, NodeIdError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"stored demand {ref.logical_key!r} version {ref.version} is invalid",
        ) from exc
    if stored_logical_key != envelope.logical_key:
        raise HTTPException(
            status_code=503,
            detail=(
                f"stored demand {ref.logical_key!r} version {ref.version} "
                "logical key does not match its payload"
            ),
        )
    if recomputed_hash != envelope.content_hash:
        raise HTTPException(
            status_code=503,
            detail=(
                f"stored demand {ref.logical_key!r} version {ref.version} "
                "content hash does not match its payload"
            ),
        )
    if record.area_type != "node":
        raise HTTPException(
            status_code=400,
            detail="stored demand must use area_type 'node' until mapping is versioned",
        )
    return envelope, record


@router.post("/plan/from-demands", response_model=StoredDemandPlanResponse)
async def plan_from_stored_demands(
    request: StoredDemandPlanRequest,
    controller: NetworkFlowController = Depends(get_flow_controller),
    store=Depends(get_demand_store),
) -> StoredDemandPlanResponse:
    identities = [(ref.logical_key, ref.version) for ref in request.demand_refs]
    if len(set(identities)) != len(identities):
        raise HTTPException(status_code=400, detail="duplicate demand reference")

    now = datetime.now(timezone.utc)
    demands: dict[str, float] = {}
    inputs: list[DemandPlanInput] = []
    for ref in request.demand_refs:
        try:
            stored = await store.get_version("demand", ref.logical_key, ref.version)
        except DemandStoreUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if stored is None:
            raise HTTPException(
                status_code=404,
                detail=f"demand {ref.logical_key!r} version {ref.version} not found",
            )
        envelope, record = _validated_stored_demand(ref, stored, now)
        active, required_flow = demand_flow_at(record, request.effective_at)
        node_id = normalize_gate_id(record.area_id)
        demands[node_id] = demands.get(node_id, 0.0) + required_flow
        inputs.append(
            DemandPlanInput(
                logical_key=envelope.logical_key,
                version=envelope.version,
                content_hash=envelope.content_hash,
                node_id=node_id,
                active=active,
                required_flow_m3s=required_flow,
            )
        )

    plan_request = PlanRequest(
        demands=demands,
        apply_losses=request.apply_losses,
        charge_dry_reaches=request.charge_dry_reaches,
        always_wet=request.always_wet,
    )
    try:
        result = _build_plan_response(plan_request, controller)
    except NetworkTopologyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info(
        "planned from exact demand versions",
        effective_at=request.effective_at.isoformat(),
        input_count=len(inputs),
        active_count=sum(item.active for item in inputs),
        input_flow_m3s=sum(item.required_flow_m3s for item in inputs),
        head_flow_m3s=result.head_flow_m3s,
        config_sha256=controller.config_sha256,
    )
    return StoredDemandPlanResponse(
        effective_at=request.effective_at,
        inputs=inputs,
        config_sha256=ControlConfigSha256(**controller.config_sha256),
        plan=result,
    )


@router.post("/hydraulic-forecast/design", response_model=DesignProfileResponse)
async def design_profile(
    request: DesignProfileRequest,
    service: DesignProfileService = Depends(get_design_profile_service),
) -> DesignProfileResponse:
    """Static design levels under explicit workbook assumptions; never observed or commandable."""
    try:
        result = service.calculate(sorted(request.zones), request.flow_fraction)
    except DesignProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DesignProfileResponse(**result)


@router.post("/model-snapshots", response_model=ModelSnapshotResponse)
async def model_snapshot(
    controller: NetworkFlowController = Depends(get_flow_controller),
    service: ControlPredictionService = Depends(get_control_prediction_service),
    release: HydraulicModelRelease | None = Depends(get_hydraulic_model_release),
    config_sha256: dict = Depends(get_model_config_sha256),
) -> ModelSnapshotResponse:
    try:
        result = service.model_snapshot(
            release,
            config_sha256,
            controller.actuation_approved,
        )
    except ModelSnapshotError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ModelSnapshotResponse(**result)


@router.post("/openings", response_model=OpeningsResponse)
async def openings(
    request: OpeningsRequest,
    controller: NetworkFlowController = Depends(get_flow_controller),
) -> OpeningsResponse:
    """Per-gate openings for `request.demands`, using the supplied freshness-stamped real
    levels (Wave 2.7 wiring). A reach is returned opening-unavailable — never commanded on
    an assumed input (plan HIGH #11) — when its level is missing/stale/future, its canal
    capacity is not fully surveyed, or the calibration bundle is not approved for actuation
    (every current bundle is planning-only, so nothing is commanded until real field
    calibrations + approved sills exist)."""
    node_levels = {
        node_id: LevelReading(value.water_level_m, value.observed_at)
        for node_id, value in request.levels.items()
    }
    now = datetime.now(timezone.utc)
    try:
        result = controller.openings_for_demand(
            request.demands,
            node_levels,
            now=now,
            max_level_age_seconds=request.max_level_age_seconds,
            apply_losses=request.apply_losses,
            charge_dry_reaches=request.charge_dry_reaches,
            always_wet=request.always_wet,
        )
    except NetworkTopologyError as exc:  # server/config topology error -> 503
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:  # bad demand / level / freshness input -> client error
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rollup = branch_split_summary(result.openings)
    return OpeningsResponse(
        openings=[
            ReachOpeningOut(
                upstream=normalize_node_id(o.reach[0]),
                downstream=normalize_node_id(o.reach[1]),
                requested_m3s=o.requested_m3s,
                capacity_m3s=o.capacity_m3s,
                opening_m=o.opening_m,
                commanded_opening_m=o.commanded_opening_m,
                commanded_gate_flow_m3s=o.commanded_gate_flow_m3s,
                achievable_m3s=o.achievable_m3s,
                deficit_m3s=o.deficit_m3s,
                feasible=o.feasible,
                needs_pulsing=o.needs_pulsing,
                reason=o.reason,
                confidence=o.confidence,
            )
            for o in result.openings
        ],
        unavailable=[
            UnavailableReachOut(
                upstream=normalize_node_id(u.reach[0]),
                downstream=normalize_node_id(u.reach[1]),
                requested_m3s=u.requested_m3s,
                reason=u.reason,
                unavailable_nodes=[normalize_node_id(n) for n in u.unavailable_nodes],
                detail=u.detail,
            )
            for u in result.unavailable
        ],
        summary=OpeningsSummary(
            # An uncommandable reach (no fresh level / unknown capacity / not actuation-
            # approved) makes the whole plan infeasible. Per-reach flows are NOT summed into
            # a network total here: the same demand flows through every serial reach on its
            # path, so a sum double-counts it (and would diverge from /plan's head_flow) —
            # the true per-reach requested/achievable/deficit are on each reach record.
            feasible=rollup["feasible"] and not result.unavailable,
            commanded_reaches=len(result.openings),
            unavailable_reaches=len(result.unavailable),
            idle_reaches=result.idle_reaches,
            infeasible_reaches=[
                [normalize_node_id(u), normalize_node_id(v)]
                for u, v in rollup["infeasible_reaches"]
            ],
            reaches_needing_pulsing=[
                [normalize_node_id(u), normalize_node_id(v)]
                for u, v in rollup["reaches_needing_pulsing"]
            ],
        ),
    )


def _canonical_area_id(area_type: str, area_id: str) -> str:
    """Trimmed area id; node ids must be real gates, canonicalized to compact form.

    `normalize_node_id` alone would pass arbitrary strings through (it only
    reformats gate-shaped ids), so nodes go through the strict gate parser. The
    source 'S' is deliberately not a valid demand subject — demand at the source
    is what /plan computes, not an input.
    """
    text = area_id.strip()
    if not text:
        raise DemandContractError("area_id must be non-empty")
    return normalize_gate_id(text) if area_type == "node" else text


def _logical_key(record, area_id: str, start: datetime, end: datetime) -> str:
    """One versioned series per (where, when, how, who) — uniform across kinds.

    Canonical JSON tuple, NOT a delimiter join: producer-controlled fields may
    contain any text, and a non-injective key silently merges distinct series
    (QCHECK: 'a|b'+'c' vs 'a'+'b|c' collided under a raw '|' join).
    """
    return json.dumps(
        [
            record.area_type,
            area_id,
            start.isoformat(),
            end.isoformat(),
            record.method,
            record.source_service,
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _validate_envelope(record, now: datetime) -> None:
    validate_timezone_name(record.timezone)
    validate_lineage(
        record.source_service, record.source_version, record.method, record.synthetic
    )
    validate_computed_at(record.computed_at, now=now)


def _prepare_demand(record, now: datetime) -> tuple[str, dict, float]:
    _validate_envelope(record, now)
    area_id = _canonical_area_id(record.area_type, record.area_id)
    start, end = validate_period_bounds(record.period_start, record.period_end)
    intervals = [(i.start, i.end) for i in record.scheduled_delivery_intervals]
    validate_intervals_within_period(start, end, intervals)
    required_flow = flow_rate_m3s(
        record.volume_m3, scheduled_delivery_seconds(intervals)
    )
    payload = record.model_dump(mode="json")
    payload["area_id"] = area_id
    return _logical_key(record, area_id, start, end), payload, required_flow


def _prepare_allocation(record, now: datetime) -> tuple[str, dict, None]:
    _validate_envelope(record, now)
    area_id = _canonical_area_id(record.area_type, record.area_id)
    start, end = validate_period_bounds(record.period_start, record.period_end)
    intervals = [(i.start, i.end) for i in record.intervals]
    validate_intervals_within_period(start, end, intervals)
    scheduled_delivery_seconds(intervals)  # enforces non-empty + non-overlapping
    for interval in record.intervals:
        # Reuse the contract's finite/non-negative rule; the divisor 1.0 is inert.
        try:
            flow_rate_m3s(interval.flow_m3s, 1.0)
        except DemandContractError as exc:
            raise DemandContractError(f"allocation flow_m3s invalid: {exc}") from exc
    payload = record.model_dump(mode="json")
    payload["area_id"] = area_id
    return _logical_key(record, area_id, start, end), payload, None


def _prepare_delivery(record, now: datetime) -> tuple[str, dict, None]:
    _validate_envelope(record, now)
    area_id = _canonical_area_id(record.area_type, record.area_id)
    start, end = validate_period_bounds(record.start, record.end)
    if end > now + MAX_CLOCK_SKEW:
        # An "actual" delivery for a window that has not elapsed is a typo or a
        # forecast in disguise; append-only means it could only ever be
        # superseded, never removed — reject it at the door.
        raise DemandContractError("delivery observation window must lie in the past")
    # Validates delivered volume is finite/non-negative against the observed window.
    flow_rate_m3s(record.volume_m3, (end - start).total_seconds())
    payload = record.model_dump(mode="json")
    payload["area_id"] = area_id
    return _logical_key(record, area_id, start, end), payload, None


@router.post("/demands", response_model=DemandSubmissionResponse)
async def submit_demand_records(
    request: DemandSubmissionRequest,
    store=Depends(get_demand_store),
) -> DemandSubmissionResponse:
    """Append demand/allocation/delivery records to their versioned stores.

    Records are processed in order with per-record atomicity: on a mid-batch
    rejection the earlier accepted records stay stored, and resubmitting the same
    batch replays them idempotently. Nothing is ever overwritten — a correction is
    the next version of its logical key (409 otherwise).
    """
    total = len(request.demands) + len(request.allocations) + len(request.deliveries)
    if total == 0:
        raise HTTPException(
            status_code=400, detail="submission must contain at least one record"
        )
    now = datetime.now(timezone.utc)
    results: list[RecordResult] = []
    batches = (
        ("demand", request.demands, _prepare_demand),
        ("allocation", request.allocations, _prepare_allocation),
        ("delivery", request.deliveries, _prepare_delivery),
    )
    try:
        for kind, records, prepare in batches:
            for record in records:
                key, payload, required_flow = prepare(record, now)
                put = await store.put(
                    kind, key, record.version, record.idempotency_key, payload
                )
                results.append(
                    RecordResult(
                        kind=kind,
                        logical_key=key,
                        version=put.version,
                        replayed=put.replayed,
                        content_hash=put.content_hash,
                        required_flow_m3s=required_flow,
                    )
                )
    except (ImmutabilityViolation, VersionConflict, DuplicateIdempotencyKey) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DemandContractError, NodeIdError, DemandStoreError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DemandStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return DemandSubmissionResponse(results=results)


@router.get("/demands", response_model=CurrentRecordsResponse)
async def current_demand_records(
    kind: Literal["demand", "allocation", "delivery"] = "demand",
    store=Depends(get_demand_store),
) -> CurrentRecordsResponse:
    """Latest version per logical key from one of the three contract stores."""
    try:
        records = await store.current(kind)
    except DemandStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CurrentRecordsResponse(
        kind=kind,
        records=[StoredRecordEnvelope(**record) for record in records],
    )


_PREDICTION_VIOLATION_OUT = {
    "requirement_shortfall": RequirementShortfallViolationOut,
    "withdrawal_shortfall": WithdrawalShortfallViolationOut,
    "withdrawal_capacity_exceeded": WithdrawalCapacityExceededViolationOut,
    "withdrawal_capacity_unavailable": WithdrawalCapacityUnavailableViolationOut,
}


def map_prediction_violation(violation):
    """Exact discriminated variant for one service-domain violation."""
    return _PREDICTION_VIOLATION_OUT[violation.kind](**asdict(violation))


def map_prediction_timeline(timeline, covered_order) -> PredictionTimelineOut:
    """Columnar transpose of a completed NetworkTimeline; every series is
    built over the same step sequence so lengths agree by construction, and
    the per-index reach identity is asserted rather than assumed."""
    steps = timeline.steps
    reaches = []
    for index, reach_id in enumerate(covered_order):
        if any(step.reaches[index].reach_id != reach_id for step in steps):
            raise ValueError(
                f"timeline reach order drifted at index {index} "
                f"({reach_id!r})"
            )
        reaches.append(
            PredictionReachSeriesOut(
                reach_id=reach_id,
                inflow_m3s=[step.reaches[index].inflow_m3s for step in steps],
                outflow_m3s=[
                    step.reaches[index].outflow_m3s for step in steps
                ],
                in_transit_volume_m3=[
                    step.reaches[index].in_transit_volume_m3 for step in steps
                ],
                cumulative_declared_loss_m3=[
                    step.reaches[index].cumulative_declared_loss_m3
                    for step in steps
                ],
            )
        )
    withdrawals = []
    for index, point in enumerate(steps[0].withdrawals if steps else ()):
        if any(
            step.withdrawals[index].structure_id != point.structure_id
            for step in steps
        ):
            raise ValueError(
                f"timeline withdrawal order drifted at index {index} "
                f"({point.structure_id!r})"
            )
        withdrawals.append(
            PredictionWithdrawalSeriesOut(
                structure_id=point.structure_id,
                planned_flow_m3s=[
                    step.withdrawals[index].planned_flow_m3s for step in steps
                ],
                hydraulically_available_flow_m3s=[
                    step.withdrawals[index].hydraulically_available_flow_m3s
                    for step in steps
                ],
                predicted_withdrawal_m3s=[
                    step.withdrawals[index].predicted_withdrawal_m3s
                    for step in steps
                ],
                shortfall_m3s=[
                    step.withdrawals[index].shortfall_m3s for step in steps
                ],
                capacity_check_status=[
                    step.withdrawals[index].capacity_check_status.value
                    for step in steps
                ],
            )
        )
    requirement_series = []
    for index, state in enumerate(steps[0].fulfillment if steps else ()):
        if any(
            step.fulfillment[index].requirement_id != state.requirement_id
            for step in steps
        ):
            raise ValueError(
                f"timeline requirement order drifted at index {index} "
                f"({state.requirement_id!r})"
            )
        requirement_series.append(
            PredictionRequirementSeriesOut(
                requirement_id=state.requirement_id,
                predicted_delivered_m3=[
                    step.fulfillment[index].predicted_delivered_m3
                    for step in steps
                ],
                status=[
                    step.fulfillment[index].status.value for step in steps
                ],
            )
        )
    return PredictionTimelineOut(
        sampled_at=[step.ends_at for step in steps],
        reaches=reaches,
        withdrawals=withdrawals,
        requirements=requirement_series,
        terminal_outflow_m3=[step.terminal_outflow_m3 for step in steps],
        mass_balance=PredictionMassBalanceOut(
            **asdict(timeline.mass_balance)
        ),
        final_fulfillment=[
            PredictionFinalFulfillmentOut(
                requirement_id=state.requirement_id,
                section_id=state.section_id,
                required_volume_m3=state.required_volume_m3,
                approved_excess_m3=state.approved_excess_m3,
                predicted_delivered_m3=state.predicted_delivered_m3,
                status=state.status.value,
            )
            for state in timeline.final_fulfillment
        ],
    )


def _map_prediction_member(entry, covered_order) -> PredictionMemberOut:
    if entry.timeline is None:
        infeasibility = entry.infeasibility
        return PredictionMemberOut(
            member=entry.member.value,
            status="infeasible",
            infeasibility=PredictionInfeasibilityOut(
                kind="reach_capacity_exceeded",
                reach_id=infeasibility.reach_id,
                capacity_kind=infeasibility.kind,
                attempted_flow_m3s=infeasibility.attempted_flow_m3s,
                capacity_m3s=infeasibility.capacity_m3s,
                interval_start=infeasibility.interval_start,
                interval_end=infeasibility.interval_end,
            ),
            violations=[],
            predicted_delivered_total_m3=None,
            timeline=None,
        )
    return PredictionMemberOut(
        member=entry.member.value,
        status="completed",
        infeasibility=None,
        violations=[
            map_prediction_violation(violation)
            for violation in entry.violations
        ],
        predicted_delivered_total_m3=entry.predicted_delivered_total_m3,
        timeline=map_prediction_timeline(entry.timeline, covered_order),
    )


async def get_prediction_repository(request: Request):
    """Dependency: the migration-backed run store, or 503 — persistence is
    part of the success contract. When lifespan left it unwired (transient DB
    blip at boot, or migration applied later) the probe re-runs lazily so one
    healthy request restores availability without a restart."""
    repository = getattr(request.app.state, "prediction_repository", None)
    if repository is None:
        probe = getattr(
            request.app.state, "prediction_repository_probe", None
        )
        if probe is not None:
            repository = await probe()
            if repository is not None:
                request.app.state.prediction_repository = repository
    if repository is None:
        raise HTTPException(
            status_code=503,
            detail="Prediction persistence is not available (migration not "
            "applied or repository not initialized)",
        )
    return repository


PREDICTION_IDENTITY_ROLLOUT_MODES = ("accept-v1-write-v2", "require-v2")

# The client's explicit engine pin. In require-v2 the caller MUST send this
# header equal to the current descriptor's content_hash, acknowledging the exact
# engine it is asking to run against. It is a HEADER (not a body field) so it
# never enters the frozen v1/v2 canonical identity payload.
PREDICTION_ENGINE_CONTENT_HASH_HEADER = "X-Prediction-Engine-Content-Hash"


def get_prediction_identity_rollout_mode(request: Request) -> str:
    """The identity rollout mode from app state (default accept-v1-write-v2).

    An unrecognized configured value fails closed (503) rather than silently
    picking a mode — the choice governs whether legacy v1 requests are still
    accepted."""
    mode = getattr(
        request.app.state,
        "prediction_identity_rollout_mode",
        "accept-v1-write-v2",
    )
    if mode not in PREDICTION_IDENTITY_ROLLOUT_MODES:
        raise HTTPException(
            status_code=503,
            detail="prediction identity rollout mode is not configured",
        )
    return mode


def _require_explicit_engine_pin(http_request: Request, descriptor: dict | None) -> None:
    """require-v2 gate: the caller MUST explicitly pin the current engine.

    Without the descriptor loaded, the mode cannot run at all (503). Otherwise
    the request must carry X-Prediction-Engine-Content-Hash equal to the current
    descriptor's content_hash: absent → 400 (the caller never acknowledged an
    engine), mismatched → 409 (the caller pinned a different engine than the
    server runs). Never a silent accept and never a v1 fallback."""
    if descriptor is None:
        raise HTTPException(
            status_code=503,
            detail="prediction engine descriptor is not loaded; require-v2 "
            "predictions are unavailable",
        )
    pin = http_request.headers.get(PREDICTION_ENGINE_CONTENT_HASH_HEADER)
    if pin is None:
        raise HTTPException(
            status_code=400,
            detail=f"require-v2 mode requires the "
            f"{PREDICTION_ENGINE_CONTENT_HASH_HEADER} header pinning the "
            "current engine descriptor content hash",
        )
    if pin != descriptor["content_hash"]:
        raise HTTPException(
            status_code=409,
            detail="client engine pin "
            f"{PREDICTION_ENGINE_CONTENT_HASH_HEADER} does not match the "
            "current prediction engine descriptor",
        )


def _prediction_response_headers(record: PredictionRunRecord) -> dict:
    """Artifact + identity metadata headers for a served prediction. The bytes
    stay the exact stored artifact; these headers describe the stored row."""
    headers = {
        "X-Prediction-Artifact-SHA256": record.artifact.artifact_sha256,
        "X-Prediction-Artifact-Media-Type": record.artifact.media_type,
        "X-Prediction-Artifact-Encoding": record.artifact.encoding,
        "X-Prediction-Artifact-Encoding-Version": str(
            record.artifact.encoding_version
        ),
        "X-Prediction-Artifact-Uncompressed-Size": str(
            record.artifact.uncompressed_size_bytes
        ),
        "X-Prediction-Identity-Version": str(record.identity_version),
    }
    if record.identity_version == PREDICTION_RUN_IDENTITY_VERSION_V2:
        headers.update(
            {
                "X-Prediction-Engine-Id": record.engine_id,
                "X-Prediction-Semantic-Contract-Version": str(
                    record.semantic_contract_version
                ),
                "X-Prediction-Build-Digest": record.build_digest,
                "X-Prediction-Engine-Content-Hash": (
                    record.engine_descriptor_content_hash
                ),
            }
        )
    return headers


def _validated_stored_bytes(stored, expected_run_id: str) -> bytes:
    """Decode + validate a stored artifact before serving it: it must parse
    as a ControlPredictionResponse whose embedded run id matches the header —
    stored bytes are never trusted blind (CPU-bound; call via threadpool)."""
    response_bytes = decode_prediction_artifact(stored.artifact)
    payload = json.loads(response_bytes.decode("utf-8"))
    try:
        parsed = ControlPredictionResponse.model_validate(payload)
    except ValidationError as exc:
        raise PredictionArtifactCorrupt(
            f"stored artifact is not a valid prediction response: {exc}"
        ) from exc
    if parsed.prediction_run_id != expected_run_id:
        raise PredictionArtifactCorrupt(
            "stored artifact's embedded run id does not match its header"
        )
    return response_bytes


def _compute_control_prediction_response(
    request: ControlPredictionRequest,
    controller: NetworkFlowController,
    service: ControlPredictionService,
    release: HydraulicModelRelease | None,
    config_sha256: dict,
    run_id: str,
) -> ControlPredictionResponse:
    """Three-member dynamic prediction on the EXACT pinned model snapshot.

    CPU-bound; the route runs this in a threadpool. An infeasible member is an
    explicit result, not an error. Missing model/coverage/lineage fails closed
    (503/409/400) — never a default."""
    gate_events = tuple(
        GateFlowEvent(event.node_id, event.effective_at, event.flow_m3s)
        for event in request.source_flow_events
    )
    withdrawal_events = tuple(
        OperatorWithdrawalEvent(
            structure_id=event.structure_id,
            effective_at=event.effective_at,
            planned_flow_m3s=event.planned_flow_m3s,
            purpose=event.purpose,
            operator_reference=event.operator_reference,
        )
        for event in request.operator_withdrawal_events
    )
    requirements = tuple(
        SectionRequirement(
            requirement_id=item.requirement_id,
            section_id=item.section_id,
            delivery_node_id=item.delivery_node_id,
            window_start=item.window_start,
            window_end=item.window_end,
            required_volume_m3=item.required_volume_m3,
            maximum_delivery_m3s=item.maximum_delivery_m3s,
            approved_excess_m3=item.approved_excess_m3,
        )
        for item in request.section_requirements
    )
    allocations = tuple(
        BranchAllocation(
            upstream_node_id=item.upstream_node_id,
            downstream_node_id=item.downstream_node_id,
            fraction=item.fraction,
        )
        for item in request.branch_allocations
    )
    try:
        outcome = service.predict_control_timeline(
            release,
            config_sha256,
            controller.actuation_approved,
            request.model_snapshot_id,
            request.model_release_id,
            request.model_release_content_hash,
            gate_events,
            withdrawal_events,
            requirements,
            allocations,
            request.starts_at,
            request.ends_at,
            request.timestep_seconds,
        )
    except PredictionModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PredictionLineageConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ModelSnapshotError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ControlPredictionResponse(
        schema_version=2,
        mode="open_loop_prediction",
        open_loop=True,
        actual_state_known=False,
        commandable=False,
        persistence="stored",
        prediction_run_id=run_id,
        model_snapshot_id=request.model_snapshot_id,
        model_release_id=request.model_release_id,
        model_release_content_hash=request.model_release_content_hash,
        config_sha256=dict(config_sha256),
        starts_at=request.starts_at,
        ends_at=request.ends_at,
        timestep_seconds=request.timestep_seconds,
        coverage=PredictionCoverageOut(
            modeled_transport_reach_ids=list(
                outcome.covered_transport_reach_ids
            ),
            excluded_transport_reaches=[
                ExcludedTransportReachOut(reach_id=reach_id, reason=reason)
                for reach_id, reason in outcome.excluded_transport_reaches
            ],
        ),
        members=[
            _map_prediction_member(entry, outcome.covered_transport_reach_ids)
            for entry in outcome.members
        ],
    )


def _build_prediction_record(
    request: ControlPredictionRequest,
    v2_request_payload: dict,
    response_model: ControlPredictionResponse,
    run_id: str,
    engine_descriptor: dict,
) -> PredictionRunRecord:
    """Canonicalize, summarize, and compress the fresh result (CPU-bound).

    A fresh write is ALWAYS identity_version 2: the request payload embeds the
    current engine descriptor and the run carries its engine pins. There is no
    new-v1 write path."""
    response_payload = response_model.model_dump(mode="json")
    response_bytes = canonical_json_bytes(response_payload)
    engine_fields = engine_identity_fields(engine_descriptor)
    return PredictionRunRecord(
        prediction_run_id=run_id,
        identity_version=PREDICTION_RUN_IDENTITY_VERSION_V2,
        response_schema_version=2,
        request_payload=v2_request_payload,
        model_snapshot_id=request.model_snapshot_id,
        model_release_id=request.model_release_id,
        model_release_content_hash=request.model_release_content_hash,
        starts_at=request.starts_at,
        ends_at=request.ends_at,
        timestep_seconds=request.timestep_seconds,
        member_summaries=summarize_prediction_members(response_payload),
        artifact=encode_prediction_artifact(response_bytes),
        engine_id=engine_fields["engine_id"],
        semantic_contract_version=engine_fields["semantic_contract_version"],
        build_digest=engine_fields["build_digest"],
        engine_descriptor_content_hash=engine_fields[
            "engine_descriptor_content_hash"
        ],
    )


async def _serve_stored_prediction(stored, run_id: str) -> Response:
    """Validate the stored artifact and return it with metadata headers."""
    content = await run_in_threadpool(_validated_stored_bytes, stored, run_id)
    return Response(
        content=content,
        media_type="application/json",
        headers=_prediction_response_headers(stored),
    )


@router.post("/predictions", response_model=ControlPredictionResponse)
async def control_predictions(
    request: ControlPredictionRequest,
    http_request: Request,
    controller: NetworkFlowController = Depends(get_flow_controller),
    service: ControlPredictionService = Depends(
        get_control_prediction_service
    ),
    release: HydraulicModelRelease | None = Depends(
        get_hydraulic_model_release
    ),
    config_sha256: dict = Depends(get_model_config_sha256),
    repository=Depends(get_prediction_repository),
    rollout_mode: str = Depends(get_prediction_identity_rollout_mode),
) -> Response:
    """Replay-first persisted prediction under the identity-v2 rollout.

    A fresh result is ALWAYS persisted as identity_version 2 (the request
    payload embeds the current engine descriptor) atomically BEFORE it is
    returned. An existing identity-v2 run replays its stored bytes. In
    `accept-v1-write-v2` a legacy identity-v1 run still replays by its v1 run
    id; in `require-v2` the caller MUST explicitly pin the current engine via
    the X-Prediction-Engine-Content-Hash header or it fails closed. There is no
    new-v1 write path."""
    descriptor = service.prediction_engine_descriptor

    # require-v2: the caller must explicitly acknowledge the exact engine
    # (header, kept OUT of the hashed identity payload) before anything runs.
    if rollout_mode == "require-v2":
        _require_explicit_engine_pin(http_request, descriptor)

    try:
        normalized_request = request.model_dump(mode="json")
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"request is not canonically serializable: {exc}",
        ) from exc

    v2_payload: dict | None = None
    v2_run_id: str | None = None
    try:
        # 1. Replay an existing identity-v2 run (requires the current engine).
        if descriptor is not None:
            v2_payload = normalize_prediction_request_identity_v2(
                normalized_request, descriptor
            )
            v2_run_id = prediction_run_id_for(
                v2_payload, PREDICTION_RUN_IDENTITY_VERSION_V2
            )
            stored = await repository.load_prediction_run(v2_run_id)
            if stored is not None:
                if canonical_json_bytes(stored.request_payload) != (
                    canonical_json_bytes(v2_payload)
                ):
                    raise PredictionRunConflict(
                        f"prediction run {v2_run_id!r} exists with different "
                        "request content"
                    )
                return await _serve_stored_prediction(stored, v2_run_id)

        # 2. Replay a legacy identity-v1 run (accept-v1-write-v2 only). The v1
        #    prefix/canonicalization are frozen, so old rows load byte-exactly.
        if rollout_mode == "accept-v1-write-v2":
            v1_run_id = prediction_run_id_for(
                normalized_request, PREDICTION_RUN_IDENTITY_VERSION
            )
            stored_v1 = await repository.load_prediction_run(v1_run_id)
            if stored_v1 is not None:
                if canonical_json_bytes(stored_v1.request_payload) != (
                    canonical_json_bytes(normalized_request)
                ):
                    raise PredictionRunConflict(
                        f"prediction run {v1_run_id!r} exists with different "
                        "request content"
                    )
                return await _serve_stored_prediction(stored_v1, v1_run_id)

        # 3. Fresh compute → persist as identity_version 2 (fail closed if the
        #    engine descriptor is unavailable — there is no new-v1 write path).
        if descriptor is None or v2_payload is None or v2_run_id is None:
            raise PredictionEngineIdentityError(
                "prediction engine descriptor is not loaded; identity-v2 "
                "predictions are unavailable"
            )
        response_model = await run_in_threadpool(
            _compute_control_prediction_response,
            request,
            controller,
            service,
            release,
            config_sha256,
            v2_run_id,
        )
        record = await run_in_threadpool(
            _build_prediction_record, request, v2_payload,
            response_model, v2_run_id, descriptor,
        )
        stored_record, _ = await repository.persist_prediction_run(record)
        return await _serve_stored_prediction(stored_record, v2_run_id)
    except PredictionRunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PredictionArtifactCorrupt as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PredictionStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PredictionEngineIdentityError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        # e.g. a non-finite float escaping the engine into canonical
        # serialization — a server-side fault, never a silent 500.
        raise HTTPException(
            status_code=503,
            detail=f"prediction result is not canonically serializable: {exc}",
        ) from exc


@router.get(
    "/predictions/{prediction_run_id}",
    response_model=ControlPredictionResponse,
)
async def get_control_prediction(
    prediction_run_id: str = FastApiPath(pattern=r"^[0-9a-f]{64}$"),
    repository=Depends(get_prediction_repository),
) -> Response:
    """Exact replay of one stored prediction run — the original bytes, for
    every stored outcome including explicitly infeasible members. Unknown id
    is 404; stored-state corruption fails closed as 503, never a partial."""
    try:
        stored = await repository.load_prediction_run(prediction_run_id)
        if stored is None:
            raise HTTPException(
                status_code=404,
                detail=f"prediction run {prediction_run_id!r} is not stored",
            )
        return await _serve_stored_prediction(stored, prediction_run_id)
    except (PredictionArtifactCorrupt, PredictionRunConflict) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PredictionStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
