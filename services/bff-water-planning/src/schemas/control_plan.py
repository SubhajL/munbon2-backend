"""Strict read-only mirrors of the scheduler control-plan projections (PR 4.4).

These are *validated pass-through* models: every field name/type mirrors the
scheduler's `DraftControlPlanResponse` / `ControlPlanLedgerResponse` exactly
(snake_case), so the BFF never invents vocabulary and never fabricates delivery
numbers. `extra="forbid"` catches added/renamed fields, and the strict scalar
aliases below catch *retyped* ones — a JSON string or boolean where the
scheduler emits an integer/float would otherwise be silently coerced (`"3"`->3,
`true`->1), turning contract drift into apparently-valid lineage. Both surface
as a ValidationError, which the routes translate to a 502: the BFF fails closed
on drift rather than projecting a corrupted plan. Nullable-but-required fields
stay required so a dropped field still 502s; only fields the scheduler itself
defaults (`transition_document`) are optional.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Annotated, Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict


def _strict_int(value: Any) -> Any:
    # JSON integers arrive as `int`; reject bool/str/float so a retyped upstream
    # field fails closed (502) instead of being coerced into valid-looking lineage.
    if value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected a JSON integer")
    return value


def _strict_number(value: Any) -> Any:
    # Accept JSON numbers (int or float); reject bool/str/non-finite.
    if value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a JSON number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("number must be finite")
    return value


def _strict_bool(value: Any) -> Any:
    if value is None:
        return value
    if not isinstance(value, bool):
        raise ValueError("expected a JSON boolean")
    return value


StrictInt = Annotated[int, BeforeValidator(_strict_int)]
StrictNumber = Annotated[float, BeforeValidator(_strict_number)]
StrictBool = Annotated[bool, BeforeValidator(_strict_bool)]


class StrictControlPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


# --- detail sub-models (mirror scheduler control_plan OUT schemas) ----------
class PlanRequirementProjection(StrictControlPlanModel):
    requirement_id: str
    run_id: str
    source_version: StrictInt
    service_date: date
    section_id: str
    zone: StrictInt
    required_volume_m3: StrictNumber
    window_start: datetime
    window_end: datetime
    quality: str
    published_at: datetime
    as_of_date: date
    source_data_status: str
    planning_disposition: Literal["scheduled", "no_delivery_required"]
    delivery_node_id: Optional[str]
    gate_id: Optional[str]
    maximum_delivery_m3s: Optional[StrictNumber]
    approved_excess_m3: Optional[StrictNumber]
    travel_delay_seconds: Optional[StrictInt]
    minimum_delivery_fraction: Optional[StrictNumber]
    maximum_delivery_fraction: Optional[StrictNumber]
    path_reach_ids: Optional[list[str]]
    rotation_windows: Optional[list[dict[str, str]]]


class GatePlanEventProjection(StrictControlPlanModel):
    event_sequence: StrictInt
    gate_id: str
    event_kind: Literal["open", "trim", "close"]
    planned_at: datetime
    target_position_m: StrictNumber
    source_flow_m3s: StrictNumber
    gate_event_sequence: StrictInt
    trim_ordinal: Optional[StrictInt]


class PlanTransitionProjection(StrictControlPlanModel):
    transition_sequence: StrictInt
    transition_type: str
    from_state: Optional[str]
    to_state: str
    actor_subject: str
    reason: Optional[str]
    transition_document: Optional[dict[str, Any]] = None
    occurred_at: datetime


class PredictionMemberStatusProjection(StrictControlPlanModel):
    member: Literal["lower", "nominal", "upper"]
    status: Literal["completed", "infeasible"]


LifecycleState = Literal[
    "draft",
    "under_review",
    "approved_for_shadow",
    "cancelled",
    "superseded",
    "invalidated",
]


class ControlPlanProjection(StrictControlPlanModel):
    """Full mirror of the scheduler plan detail (GET /versions/{v})."""

    plan_id: UUID
    plan_version: StrictInt
    lifecycle_state: LifecycleState
    input_content_hash: str
    draft_content_hash: str
    requirement_run_id: UUID
    requirement_version: StrictInt
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    optimizer_status: Literal["feasible", "infeasible"]
    prediction_status: Literal["not_requested", "completed", "infeasible"]
    prediction_run_id: Optional[str]
    prediction_member_statuses: list[PredictionMemberStatusProjection]
    horizon_start: datetime
    horizon_end: datetime
    model_step_seconds: StrictInt
    max_intermediate_trims: StrictInt
    optimizer_result: dict[str, Any]
    requirements: list[PlanRequirementProjection]
    events: list[GatePlanEventProjection]
    transitions: list[PlanTransitionProjection]
    created_by_subject: str
    created_at: datetime


# --- ledger sub-models (mirror scheduler ledger OUT schemas) ----------------
class MemberBoundsProjection(StrictControlPlanModel):
    lower_bound: Optional[StrictNumber]
    nominal: Optional[StrictNumber]
    upper_bound: Optional[StrictNumber]


class LedgerEntryProjection(StrictControlPlanModel):
    requirement_id: str
    section_id: str
    checkpoint_index: StrictInt
    checkpoint_at: datetime
    status: str
    required_volume_m3: StrictNumber
    approved_excess_m3: StrictNumber
    delivered_m3: MemberBoundsProjection
    path_in_transit_m3: MemberBoundsProjection
    remaining_m3: MemberBoundsProjection
    checkpoint_reasons: list[str]


class HandoverVerdictProjection(StrictControlPlanModel):
    gate_id: str
    requirement_ids: list[str]
    is_safe: StrictBool
    reasons: list[str]


class ControlPlanLedgerProjection(StrictControlPlanModel):
    """Full mirror of the scheduler ledger (GET /versions/{v}/ledger)."""

    plan_id: UUID
    plan_version: StrictInt
    prediction_run_id: Optional[str]
    prediction_status: str
    ledger_sha256: str
    entries: list[LedgerEntryProjection]
    handover: list[HandoverVerdictProjection]


# --- derived read-only subsets (built from a validated detail projection) ---
class ControlPlanPredictionCoverage(StrictControlPlanModel):
    """Prediction lineage + exact per-member statuses — NO success/percentage/
    zero-count vocabulary. `infeasible`/`not_requested` are preserved verbatim."""

    plan_id: UUID
    plan_version: StrictInt
    requirement_run_id: UUID
    requirement_version: StrictInt
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    input_content_hash: str
    draft_content_hash: str
    optimizer_status: Literal["feasible", "infeasible"]
    prediction_status: Literal["not_requested", "completed", "infeasible"]
    prediction_run_id: Optional[str]
    prediction_member_statuses: list[PredictionMemberStatusProjection]


class ControlPlanLifecycleHistory(StrictControlPlanModel):
    """Plan identity + derived lifecycle state + the complete ordered transition
    history, each `transition_document` preserved verbatim."""

    plan_id: UUID
    plan_version: StrictInt
    lifecycle_state: LifecycleState
    created_by_subject: str
    created_at: datetime
    transitions: list[PlanTransitionProjection]
