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
from datetime import datetime, timezone
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException

from core.demand_contract import (
    MAX_CLOCK_SKEW,
    DemandContractError,
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
    VersionConflict,
)
from core.branch_split import branch_split_summary
from core.network_flow_controller import (
    LevelReading,
    NetworkFlowController,
)
from core.network_topology import NetworkTopologyError
from core.node_id import NodeIdError, normalize_gate_id, normalize_node_id
from schemas.control import (
    OpeningsRequest,
    OpeningsResponse,
    OpeningsSummary,
    PlanCoverage,
    PlanRequest,
    PlanResponse,
    ReachChainageGap,
    ReachFlow,
    ReachOpeningOut,
    UnavailableReachOut,
)
from schemas.demand import (
    CurrentRecordsResponse,
    DemandSubmissionRequest,
    DemandSubmissionResponse,
    RecordResult,
    StoredRecordEnvelope,
)

logger = structlog.get_logger()
router = APIRouter()

# Initialized in main.py lifespan; None until then.
flow_controller: Optional[NetworkFlowController] = None
demand_store = None  # PostgresDemandStore at runtime; any core.demand_store twin in tests


def get_flow_controller() -> NetworkFlowController:
    """Dependency: the loaded controller, or 503 if the service has not initialized it."""
    if flow_controller is None:
        raise HTTPException(status_code=503, detail="Flow controller not initialized")
    return flow_controller


def get_demand_store():
    """Dependency: the versioned contract store, or 503 until lifespan wires it."""
    if demand_store is None:
        raise HTTPException(status_code=503, detail="Demand store not initialized")
    return demand_store


@router.post("/plan", response_model=PlanResponse)
async def plan(
    request: PlanRequest,
    controller: NetworkFlowController = Depends(get_flow_controller),
) -> PlanResponse:
    """Required flow on every reach to serve `request.demands` (fail-closed on bad demand)."""
    try:
        reach_flow = controller.required_flow_per_reach(
            request.demands,
            apply_losses=request.apply_losses,
            charge_dry_reaches=request.charge_dry_reaches,
            always_wet=request.always_wet,
        )
    except NetworkTopologyError as exc:  # server/config error (subclass of ValueError) -> 503
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:  # unknown / negative / non-finite / source demand -> client error
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    head_flow = sum(flow for (upstream, _), flow in reach_flow.items() if upstream == "S")
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
    required_flow = flow_rate_m3s(record.volume_m3, scheduled_delivery_seconds(intervals))
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
