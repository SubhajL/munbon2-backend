"""Strict request/response schemas for the control-plans draft API (PR 4.3a)."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal, Optional
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)


def _require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must carry an explicit timezone offset")
    return value.astimezone(timezone.utc)


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    return value


def _finite_number(value: Any) -> Any:
    value = _reject_bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("number must be finite")
    return value


def _no_boundary_whitespace(value: str) -> str:
    # The optimizer rejects boundary whitespace on identifiers (Munbon gate ids
    # legitimately carry interior spaces), so catch it here as a 422 rather than
    # letting it surface as an internal 500 from optimize.
    if not value or value != value.strip():
        raise ValueError(
            "identifier must be non-empty and free of leading/trailing whitespace"
        )
    return value


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


AwareUtc = Annotated[datetime, AfterValidator(_require_aware_utc)]
StrictNumber = Annotated[float, BeforeValidator(_finite_number)]
StrictInt = Annotated[int, BeforeValidator(_reject_bool)]
StrictId = Annotated[str, Field(min_length=1), AfterValidator(_no_boundary_whitespace)]
NonBlank = Annotated[str, Field(min_length=1), AfterValidator(_non_blank)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class RequirementScopeIn(_StrictModel):
    service_date: date
    zone: StrictInt = Field(ge=1, le=6)


class TimeWindowIn(_StrictModel):
    starts_at: AwareUtc
    ends_at: AwareUtc

    @model_validator(mode="after")
    def _ordered(self) -> "TimeWindowIn":
        if self.starts_at >= self.ends_at:
            raise ValueError("window must have positive duration")
        return self


class SectionBindingIn(_StrictModel):
    section_id: StrictId
    delivery_node_id: StrictId
    gate_id: StrictId
    maximum_delivery_m3s: StrictNumber = Field(gt=0)


class RequirementPolicyIn(_StrictModel):
    requirement_id: StrictId
    approved_excess_m3: StrictNumber = Field(ge=0)
    rotation_windows: list[TimeWindowIn] = Field(min_length=1)


class FlowCandidateIn(_StrictModel):
    gate_id: StrictId
    target_position_m: StrictNumber = Field(gt=0)
    source_flow_m3s: StrictNumber = Field(gt=0)


class PulseDutyIn(_StrictModel):
    gate_id: StrictId
    minimum_open_seconds: StrictInt = Field(gt=0)
    maximum_open_seconds: StrictInt = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> "PulseDutyIn":
        if self.minimum_open_seconds > self.maximum_open_seconds:
            raise ValueError("pulse duty bounds must be ordered")
        return self


class OperatorWithdrawalIn(_StrictModel):
    structure_id: StrictId
    effective_at: AwareUtc
    planned_flow_m3s: StrictNumber = Field(ge=0)
    purpose: NonBlank
    operator_reference: Optional[NonBlank] = None


class BranchAllocationIn(_StrictModel):
    upstream_node_id: StrictId
    downstream_node_id: StrictId
    fraction: StrictNumber = Field(ge=0, le=1)


class DraftControlPlanRequest(_StrictModel):
    requirement_run_id: UUID
    requirement_version: StrictInt = Field(gt=0)
    requirement_scopes: list[RequirementScopeIn] = Field(min_length=1)
    starts_at: AwareUtc
    ends_at: AwareUtc
    section_bindings: list[SectionBindingIn]
    requirement_policies: list[RequirementPolicyIn]
    flow_candidates: list[FlowCandidateIn] = Field(min_length=1)
    pulse_duties: list[PulseDutyIn]
    operator_withdrawals: list[OperatorWithdrawalIn]
    branch_allocations: list[BranchAllocationIn]

    @model_validator(mode="after")
    def _consistent(self) -> "DraftControlPlanRequest":
        if self.starts_at >= self.ends_at:
            raise ValueError("draft horizon must have positive duration")
        scopes = [(scope.service_date, scope.zone) for scope in self.requirement_scopes]
        if len(set(scopes)) != len(scopes):
            raise ValueError("requirement_scopes must be unique")
        sections = [binding.section_id for binding in self.section_bindings]
        if len(set(sections)) != len(sections):
            raise ValueError("section_bindings must be unique per section")
        policies = [policy.requirement_id for policy in self.requirement_policies]
        if len(set(policies)) != len(policies):
            raise ValueError("requirement_policies must be unique per requirement")
        candidates = [
            (candidate.gate_id, candidate.target_position_m)
            for candidate in self.flow_candidates
        ]
        if len(set(candidates)) != len(candidates):
            raise ValueError("flow_candidates must be unique per gate position")
        duties = [duty.gate_id for duty in self.pulse_duties]
        if len(set(duties)) != len(duties):
            raise ValueError("pulse_duties must be unique per gate")
        edges = [
            (allocation.upstream_node_id, allocation.downstream_node_id)
            for allocation in self.branch_allocations
        ]
        if len(set(edges)) != len(edges):
            raise ValueError("branch_allocations must be unique per edge")
        return self


class PlanRequirementOut(_StrictModel):
    requirement_id: str
    run_id: str
    source_version: int
    service_date: date
    section_id: str
    zone: int
    required_volume_m3: float
    window_start: datetime
    window_end: datetime
    quality: str
    published_at: datetime
    as_of_date: date
    source_data_status: str
    planning_disposition: Literal["scheduled", "no_delivery_required"]
    delivery_node_id: Optional[str]
    gate_id: Optional[str]
    maximum_delivery_m3s: Optional[float]
    approved_excess_m3: Optional[float]
    travel_delay_seconds: Optional[int]
    minimum_delivery_fraction: Optional[float]
    maximum_delivery_fraction: Optional[float]
    path_reach_ids: Optional[list[str]]
    rotation_windows: Optional[list[dict[str, str]]]


class GatePlanEventOut(_StrictModel):
    event_sequence: int
    gate_id: str
    event_kind: Literal["open", "trim", "close"]
    planned_at: datetime
    target_position_m: float
    source_flow_m3s: float
    gate_event_sequence: int
    trim_ordinal: Optional[int]


class PlanTransitionOut(_StrictModel):
    transition_sequence: int
    transition_type: str
    from_state: Optional[str]
    to_state: str
    actor_subject: str
    reason: Optional[str]
    transition_document: Optional[dict[str, Any]] = None
    occurred_at: datetime


class PredictionMemberStatusOut(_StrictModel):
    member: Literal["lower", "nominal", "upper"]
    status: Literal["completed", "infeasible"]


class MemberBoundsOut(_StrictModel):
    lower_bound: Optional[float]
    nominal: Optional[float]
    upper_bound: Optional[float]


class LedgerEntryOut(_StrictModel):
    requirement_id: str
    section_id: str
    checkpoint_index: int
    checkpoint_at: datetime
    status: str
    required_volume_m3: float
    approved_excess_m3: float
    delivered_m3: MemberBoundsOut
    path_in_transit_m3: MemberBoundsOut
    remaining_m3: MemberBoundsOut
    checkpoint_reasons: list[str]


class HandoverVerdictOut(_StrictModel):
    gate_id: str
    requirement_ids: list[str]
    is_safe: bool
    reasons: list[str]


class ControlPlanLedgerResponse(_StrictModel):
    plan_id: UUID
    plan_version: int
    prediction_run_id: Optional[str]
    prediction_status: str
    ledger_sha256: str
    entries: list[LedgerEntryOut]
    handover: list[HandoverVerdictOut]


class LifecycleActionRequest(_StrictModel):
    reason: Optional[NonBlank] = None


class ReasonedActionRequest(_StrictModel):
    reason: NonBlank


class SupersedeRequest(_StrictModel):
    successor_plan_id: UUID
    successor_plan_version: StrictInt = Field(gt=0)
    reason: NonBlank


_LIFECYCLE_STATE = Literal[
    "draft",
    "under_review",
    "approved_for_shadow",
    "cancelled",
    "superseded",
    "invalidated",
]


class DraftControlPlanResponse(_StrictModel):
    plan_id: UUID
    plan_version: int
    lifecycle_state: _LIFECYCLE_STATE
    input_content_hash: str
    draft_content_hash: str
    requirement_run_id: UUID
    requirement_version: int
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    optimizer_status: Literal["feasible", "infeasible"]
    prediction_status: Literal["not_requested", "completed", "infeasible"]
    prediction_run_id: Optional[str]
    prediction_member_statuses: list[PredictionMemberStatusOut]
    horizon_start: datetime
    horizon_end: datetime
    model_step_seconds: int
    max_intermediate_trims: int
    optimizer_result: dict[str, Any]
    requirements: list[PlanRequirementOut]
    events: list[GatePlanEventOut]
    transitions: list[PlanTransitionOut]
    created_by_subject: str
    created_at: datetime
