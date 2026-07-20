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

from schemas.machine_boundary import ValidationRejectionReason


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
# Bounded, non-blank text for the persisted shadow-approval document: the list
# projection loads this document per row, so its size is capped at the source to
# keep the bounded projection genuinely bounded.
BoundedReason = Annotated[
    str, Field(min_length=1, max_length=2000), AfterValidator(_non_blank)
]
BoundedEvidenceRef = Annotated[
    str, Field(min_length=1, max_length=200), AfterValidator(_non_blank)
]


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
    # Optional campaign identity (PR 4.4b-4): absent -> a NEW campaign at version
    # 1; present -> the next immutable version of that EXISTING campaign (a
    # present-but-unknown campaign_id fails closed, never auto-creates). It is part
    # of the canonical hashed input, so idempotency is per (campaign_id, input).
    campaign_id: Optional[UUID] = None
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


class ShadowApprovalRequest(_StrictModel):
    """Approve-for-shadow REQUIRES a reason and at least one non-blank evidence
    reference (the human authorization trail pinned into the freeze). Both the
    reason and each evidence ref are length-capped so the stored approval document
    the bounded list projection later reads per row can never grow unbounded."""

    reason: BoundedReason
    evidence_refs: list[BoundedEvidenceRef] = Field(min_length=1, max_length=20)


class SupersedeRequest(_StrictModel):
    successor_plan_id: UUID
    successor_plan_version: StrictInt = Field(gt=0)
    reason: NonBlank


class ActivateRequest(_StrictModel):
    """Activation REQUIRES a reason and at least one non-blank evidence reference —
    the human authorization trail pinned into the activation freeze (this transition
    grants machine authority). Mirrors ShadowApprovalRequest's bounds."""

    reason: BoundedReason
    evidence_refs: list[BoundedEvidenceRef] = Field(min_length=1, max_length=20)


_LIFECYCLE_STATE = Literal[
    "draft",
    "under_review",
    "approved_for_shadow",
    "shadow_active",
    "cancelled",
    "superseded",
    "invalidated",
]


class DraftControlPlanResponse(_StrictModel):
    plan_id: UUID
    plan_version: int
    # The stable campaign identity this version belongs to (PR 4.4b-4); a legacy
    # singleton campaign's id equals its plan_id.
    campaign_id: UUID
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


# --- Bounded read projections (PR 4.4b-3) -----------------------------------
# Dedicated, BOUNDED per-plan reads served by their own scheduler endpoints. Each
# carries EXACTLY the coverage / history data the BFF previously projected out of
# the full detail — reusing the OUT sub-models above, inventing no new vocabulary
# — so a bounded read returns the same data without loading the full aggregate.
class ControlPlanPredictionCoverageResponse(_StrictModel):
    """Prediction lineage + exact per-member statuses (NO optimizer_result, NO
    requirements/events/transitions/ledger, NO trajectory). Mirrors the subset the
    detail response already exposes; `infeasible`/`not_requested` are verbatim."""

    plan_id: UUID
    plan_version: int
    # The campaign this version belongs to, sourced from the mapping table via a
    # small indexed join (PR 4.4b-4).
    campaign_id: UUID
    requirement_run_id: UUID
    requirement_version: int
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    input_content_hash: str
    draft_content_hash: str
    optimizer_status: Literal["feasible", "infeasible"]
    prediction_status: Literal["not_requested", "completed", "infeasible"]
    prediction_run_id: Optional[str]
    prediction_member_statuses: list[PredictionMemberStatusOut]


class ControlPlanLifecycleHistoryResponse(_StrictModel):
    """Plan identity + derived lifecycle state + the COMPLETE ordered transition
    history, each `transition_document` preserved verbatim (history needs them)."""

    plan_id: UUID
    plan_version: int
    lifecycle_state: _LIFECYCLE_STATE
    created_by_subject: str
    created_at: datetime
    transitions: list[PlanTransitionOut]


# --- Bounded machine-boundary reads (PR 6.5a) -------------------------------
# Read-only projections of the shadow-dispatch durable evidence, for the operator
# dashboard (via the BFF). NO large documents; NO command affordance.
class IntentTimelineEntryOut(_StrictModel):
    """One command intent's claimed→dispatched→validated arc: the outbox intent
    (gate/kind/window, 0007), its per-intent execution state (0009), and its
    validation receipt (0010) if one has been persisted yet. Delivery is PREDICTED
    evidence — never an observed device state."""

    intent_id: UUID
    canonical_gate_id: str
    event_kind: Literal["open", "trim", "close"]
    event_sequence: int
    not_before: datetime
    deadline: datetime
    execution_state: Literal["pending", "claimed", "missed", "invalidated"]
    claimed_at: Optional[datetime]
    receipt_status: Optional[Literal["validation_accepted", "validation_rejected"]]
    # The frozen 6.0 rejection vocabulary — a stored out-of-vocab reason fails closed (503)
    # at the projection rather than passing an unknown value through to the dashboard.
    reason_code: Optional[ValidationRejectionReason]
    validated_at: Optional[datetime]
    dispatched_at: Optional[datetime]
    receipt_content_sha256: Optional[str]


class ControlPlanIntentTimelineResponse(_StrictModel):
    plan_id: UUID
    plan_version: int
    intents: list[IntentTimelineEntryOut]


class ReadbackObservationOut(_StrictModel):
    """One shadow readback reconciliation observation (0011). `unavailable` means the
    reading could not be trusted (never a hold); a null observed_level is explicit."""

    canonical_gate_id: str
    observed_level: Optional[int]
    expected_level: int
    quality: str
    verdict: Literal["ok", "mismatch", "unavailable"]
    reconciliation_mode: Literal["observe", "enforce"]
    observed_at: datetime


class ControlPlanReadbackObservationsResponse(_StrictModel):
    plan_id: UUID
    plan_version: int
    observations: list[ReadbackObservationOut]


class HoldEventOut(_StrictModel):
    event_type: Literal["held", "resumed"]
    worker_id: Optional[str]
    occurred_at: datetime


class ControlPlanExecutionStateResponse(_StrictModel):
    """Plan-level open-loop execution posture: the DERIVED current hold state plus the
    ordered held/resumed history (0009). A hold pauses claiming; it is NOT a lifecycle
    exit (the plan keeps its authority)."""

    plan_id: UUID
    plan_version: int
    is_held: bool
    hold_events: list[HoldEventOut]


# --- Bounded list projection (PR 4.4a-3) ------------------------------------
# The list page is a HEADER-ONLY projection: it MUST NOT carry any large
# document (optimizer_result, prediction response, requirements/events/
# transitions/ledger, trajectory). Bumping this version signals an incompatible
# change to the list-page shape to every consumer (scheduler + BFF + contracts).
PROJECTION_SCHEMA_VERSION = 1


class ControlPlanListFilters(_StrictModel):
    """The exact, optional filter set for the list route.

    Doubles as the cursor's filter identity: a cursor is bound to
    ``model_dump(mode="json", exclude_none=True)`` of these fields, so it cannot
    be replayed across a different filter set. ``lifecycle_state`` filters on the
    DERIVED current state (the terminal transition's ``to_state``), not the
    frozen creation-metadata column.
    """

    lifecycle_state: Optional[_LIFECYCLE_STATE] = None
    horizon_start_gte: Optional[AwareUtc] = None
    horizon_end_lte: Optional[AwareUtc] = None
    requirement_run_id: Optional[UUID] = None
    requirement_version: Optional[StrictInt] = Field(default=None, gt=0)
    input_content_hash: Optional[str] = None
    model_snapshot_id: Optional[str] = None
    model_release_content_hash: Optional[str] = None
    prediction_run_id: Optional[str] = None
    prediction_content_sha256: Optional[str] = None

    def cursor_identity(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class ControlPlanSummaryOut(_StrictModel):
    """One row of the bounded list projection — header columns + a derived
    lifecycle state and approval-trust flag. NO optimizer_result, NO
    requirements/events/transitions/ledger, NO trajectory."""

    plan_id: UUID
    plan_version: int
    # Stable campaign identity (PR 4.4b-4), joined from the mapping table.
    campaign_id: UUID
    lifecycle_state: _LIFECYCLE_STATE
    approval_trust: bool
    horizon_start: datetime
    horizon_end: datetime
    requirement_run_id: UUID
    requirement_version: int
    input_content_hash: str
    model_snapshot_id: str
    model_release_content_hash: str
    optimizer_status: Literal["feasible", "infeasible"]
    prediction_status: Literal["not_requested", "completed", "infeasible"]
    prediction_run_id: Optional[str]
    prediction_response_sha256: Optional[str]
    created_by_subject: str
    created_at: datetime


class ControlPlanListPage(_StrictModel):
    items: list[ControlPlanSummaryOut]
    next_cursor: Optional[str]
    # Pinned to the CURRENT projection shape (== PROJECTION_SCHEMA_VERSION). Typing
    # it as a Literal (not a bare int) means bumping the projection is a deliberate
    # code change on both the scheduler and the BFF mirror, and an unexpected
    # version can never round-trip silently.
    projection_schema_version: Literal[1]
