"""Pydantic schemas for the C9 control API (demand -> required per-reach flow)."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    field_validator,
)

from schemas.demand import AwareUtc


def _reject_bool(value, field_name: str):
    """A JSON boolean coerces to 1.0/0.0 under a float field, silently defeating the
    core's finite-number guards. Reject it at the schema boundary (a bool serialises
    cleanly in a 422, unlike a raw NaN)."""
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number, not a boolean")
    return value


def _reject_bool_demand_values(demands):
    """Same guard for the per-node demand map: `{"M(0,2)": true}` would otherwise coerce
    to 1.0 m3/s of phantom demand before the engine's bool check ever runs."""
    if isinstance(demands, dict):
        for node_id, value in demands.items():
            if isinstance(value, bool):
                raise ValueError(
                    f"demand for {node_id} must be a number, not a boolean"
                )
    return demands


class PlanRequest(BaseModel):
    """A per-node water demand to turn into a per-reach flow plan.

    Non-finite values (NaN/Inf, e.g. a `1e400` overflow) are rejected in the handler by the
    engine's `_validate` (400 with a string message) rather than by a schema `allow_inf_nan`
    constraint: pydantic's 422 error echoes the raw inf float, which then fails JSON
    serialization ("Out of range float values are not JSON compliant") and returns 500.
    """

    demands: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-node water demand keyed by network node id, m3/s. Ids are accepted "
            "in any spacing (compact 'M(0,3;1,0)' or survey 'M (0,3; 1,0)'); two keys "
            "naming the same node are rejected. Responses always use the compact form."
        ),
    )
    apply_losses: bool = Field(
        default=False,
        description="Add B5 conveyance (seepage + operational) loss to each reach.",
    )
    charge_dry_reaches: bool = Field(
        default=False,
        description=(
            "Charge fixed-depth seepage on ALL surveyed reaches regardless of planned "
            "flow (legacy steady whole-network mode). Default (D1): only reaches that "
            "carry flow for this plan are charged. Requires apply_losses=true."
        ),
    )
    always_wet: list[tuple[str, str]] = Field(
        default_factory=list,
        description=(
            "Reaches [upstream, downstream] kept charged with seepage even when this "
            "plan sends them no flow (trunk canals that never drain). Ids accept any "
            "spacing; unknown reaches are rejected. Requires apply_losses=true."
        ),
    )

    @field_validator("demands", mode="before")
    @classmethod
    def _demands_not_bool(cls, v):
        return _reject_bool_demand_values(v)


class ReachFlow(BaseModel):
    """Required flow on one reach (the gate terminating it must pass this).

    The `calibration_method`/`confidence`/`has_geometry` fields are Wave 2.8a
    observability: how trustworthy this reach's model is (measured vs inferred gate
    rating; surveyed vs missing geometry), so a consumer never reads a low-confidence
    number as authoritative.
    """

    upstream: str
    downstream: str
    required_flow_m3s: float
    calibration_method: str
    confidence: float
    has_geometry: bool


class ReachChainageGap(BaseModel):
    """A partially surveyed reach: `gap_m` of its chainage carries NO surveyed
    geometry, so its conveyance loss and capacity bound understate there (2.1b)."""

    upstream: str
    downstream: str
    gap_m: float


class PlanCoverage(BaseModel):
    """Network-level Wave 2.8a roll-up: how much of the plan rests on surveyed geometry
    and measured (vs inferred) gate calibration. Request-independent — a snapshot an
    operator reads before trusting any plan."""

    total_reaches: int
    geometry_surveyed: int
    geometry_missing: int
    chainage_gaps: int
    calibration_method_counts: dict[str, int]


class PlanResponse(BaseModel):
    reaches: list[ReachFlow]
    head_flow_m3s: float
    apply_losses: bool
    charge_dry_reaches: bool = False
    reaches_missing_geometry: list[list[str]] = Field(default_factory=list)
    reaches_with_chainage_gaps: list[ReachChainageGap] = Field(default_factory=list)
    coverage: PlanCoverage


Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
LogicalKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DemandVersionRef(BaseModel):
    logical_key: LogicalKey
    version: StrictInt = Field(ge=1)
    content_hash: Sha256Hex


class StoredDemandPlanRequest(BaseModel):
    effective_at: AwareUtc
    demand_refs: list[DemandVersionRef] = Field(min_length=1)
    apply_losses: bool = False
    charge_dry_reaches: bool = False
    always_wet: list[tuple[str, str]] = Field(default_factory=list)


class DemandPlanInput(BaseModel):
    logical_key: str
    version: int
    content_hash: Sha256Hex
    node_id: str
    active: bool
    required_flow_m3s: float


class ControlConfigSha256(BaseModel):
    network: Sha256Hex
    canal_geometry: Sha256Hex
    gate_calibrations: Sha256Hex


class StoredDemandPlanResponse(BaseModel):
    effective_at: AwareUtc
    inputs: list[DemandPlanInput]
    config_sha256: ControlConfigSha256
    plan: PlanResponse


class DesignProfileRequest(BaseModel):
    zones: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6])
    flow_fraction: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)

    @field_validator("zones", mode="before")
    @classmethod
    def _validate_zones(cls, value):
        if not isinstance(value, list):
            raise ValueError("zones must be an array")
        if not value:
            raise ValueError("zones must not be empty")
        if any(isinstance(zone, bool) for zone in value):
            raise ValueError("zones must contain integers, not booleans")
        if any(not isinstance(zone, int) or zone not in range(1, 7) for zone in value):
            raise ValueError("zones must contain only zone numbers 1 through 6")
        if len(set(value)) != len(value):
            raise ValueError("zones must not contain duplicates")
        return value

    @field_validator("flow_fraction", mode="before")
    @classmethod
    def _flow_fraction_not_bool(cls, value):
        return _reject_bool(value, "flow_fraction")


class ZoneDesignProfileOut(BaseModel):
    zone: int
    canal: str
    entrance_gate_id: str
    branches_from_zone: int | None
    status: Literal["available", "unavailable", "over_capacity", "incompatible"]
    reason: str | None
    detail: str | None
    structure_data_status: Literal["complete", "incomplete", "unavailable"]
    calibration_method: str
    confidence: float
    design_fsl_reference_side: str | None
    design_fsl_msl_m: float | None
    sill_msl_m: float | None
    design_flow_m3s: float | None
    binding_capacity_m3s: float | None
    flow_m3s: float | None
    reference_upstream: str | None
    reference_downstream: str | None
    effective_bed_msl_m: float | None
    normal_depth_m: float | None
    forecast_level_msl_m: float | None


class DesignProfileResponse(BaseModel):
    mode: Literal["design_profile"]
    flow_fraction: float
    open_loop: Literal[True]
    actual_state_known: Literal[False]
    commandable: Literal[False]
    outlet_gate_id: str
    canals: dict[str, list[int]]
    source_workbook: str
    source_sha256: str
    config_sha256: dict[str, str]
    zones: list[ZoneDesignProfileOut]


class _StrictModelSnapshotSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelSnapshotScadaEdge(_StrictModelSnapshotSchema):
    upstream_node_id: str
    downstream_node_id: str


class ModelSnapshotScadaGraph(_StrictModelSnapshotSchema):
    config_sha256: Sha256Hex
    source_workbook_sha256: Sha256Hex
    root_node_id: Literal["S"]
    gate_count: int
    edge_count: int
    edges: list[ModelSnapshotScadaEdge]


class ModelSnapshotRoutingElement(_StrictModelSnapshotSchema):
    element_id: str
    upstream_node_id: str
    downstream_node_id: str
    role: Literal[
        "boundary", "transport", "branch_structure", "withdrawal_structure"
    ]
    canonical_edges: list[list[str]]
    canal: str | None
    span_m: float | None
    geometry_status: Literal["surveyed", "unavailable", "not_applicable"]
    located_at_km: str | None


class ModelSnapshotRoutingTopology(_StrictModelSnapshotSchema):
    schema_version: Literal[1]
    config_sha256: Sha256Hex
    content_hash: Sha256Hex
    root_node_id: Literal["S"]
    node_count: int
    element_count: int
    role_counts: dict[str, int]
    elements: list[ModelSnapshotRoutingElement]


class ModelSnapshotActionConfigSha256(_StrictModelSnapshotSchema):
    canal_geometry: Sha256Hex
    gate_calibrations: Sha256Hex
    geometry_coverage: Sha256Hex


class ModelSnapshotOperatingEnvelope(_StrictModelSnapshotSchema):
    minimum_flow_m3s: float
    maximum_flow_m3s: float
    minimum_timestep_seconds: float
    maximum_timestep_seconds: float
    maximum_horizon_seconds: float


class ModelSnapshotActionModel(_StrictModelSnapshotSchema):
    kind: Literal["gate_flow_event"]
    flow_unit: Literal["m3/s"]
    allowed_node_ids: list[Literal["S"]]
    requires_explicit_branch_allocations: Literal[True]
    commandable: Literal[False]
    actuation_approved: bool
    config_sha256: ModelSnapshotActionConfigSha256
    operating_envelope: ModelSnapshotOperatingEnvelope | None


class ModelSnapshotSource(_StrictModelSnapshotSchema):
    source_id: str
    version: str
    sha256: Sha256Hex


class ModelSnapshotLineage(_StrictModelSnapshotSchema):
    generator: str
    generator_version: str
    sources: list[ModelSnapshotSource]


class ModelSnapshotParameterDistribution(_StrictModelSnapshotSchema):
    lower: float
    nominal: float
    upper: float


class ModelSnapshotReachParameters(_StrictModelSnapshotSchema):
    reach_id: str
    delay_seconds: ModelSnapshotParameterDistribution
    loss_fraction: ModelSnapshotParameterDistribution
    dispersion_seconds: ModelSnapshotParameterDistribution
    capacity_m3s: ModelSnapshotParameterDistribution
    evidence_refs: list[str]


class ModelSnapshotResponseMember(_StrictModelSnapshotSchema):
    reach_id: str
    member: Literal["lower", "nominal", "upper"]
    delay_seconds: float
    loss_fraction: float
    dispersion_seconds: float
    capacity_m3s: float
    minimum_timestep_seconds: float
    maximum_timestep_seconds: float


class ModelSnapshotResponseModel(_StrictModelSnapshotSchema):
    schema_version: Literal[1]
    release_id: str
    generated_at: AwareUtc
    evidence_class: Literal["engineering_prior"]
    commandable: Literal[False]
    content_hash: Sha256Hex
    lineage: ModelSnapshotLineage
    reach_parameters: list[ModelSnapshotReachParameters]
    response_members: list[ModelSnapshotResponseMember]


class ModelSnapshotCoverage(_StrictModelSnapshotSchema):
    total_transport_reaches: int
    available_transport_reaches: int
    unavailable_transport_reaches: int


class ModelSnapshotUnavailableReach(_StrictModelSnapshotSchema):
    reach_id: str
    reason: str


class ModelSnapshotResponse(_StrictModelSnapshotSchema):
    schema_version: Literal[2]
    snapshot_id: Sha256Hex
    data_status: Literal["complete", "partial", "unavailable"]
    mode: Literal["open_loop_prediction"]
    open_loop: Literal[True]
    actual_state_known: Literal[False]
    commandable: Literal[False]
    scada_graph: ModelSnapshotScadaGraph
    routing_topology: ModelSnapshotRoutingTopology
    action_model: ModelSnapshotActionModel
    response_model: ModelSnapshotResponseModel | None
    transport_response_coverage: ModelSnapshotCoverage
    unavailable_transport_reaches: list[ModelSnapshotUnavailableReach]


class LevelValue(BaseModel):
    """A freshness-stamped real water-surface elevation (m MSL) at one node. `observed_at`
    is when it was measured — the wiring only commands a gate whose boundary levels are
    recent enough, so the timestamp is part of the datum (Wave 2.7, plan HIGH #11)."""

    water_level_m: float
    observed_at: datetime

    @field_validator("water_level_m", mode="before")
    @classmethod
    def _level_not_bool(cls, v):
        return _reject_bool(v, "water_level_m")


class OpeningsRequest(BaseModel):
    """Turn a per-node demand into per-gate openings, using the supplied real levels.

    `levels` is keyed by node id (any spacing). A reach whose upstream/downstream level is
    absent from `levels` or older than `max_level_age_seconds` is NOT commanded — it is
    returned opening-unavailable, never an assumed head.
    """

    demands: dict[str, float] = Field(default_factory=dict)
    levels: dict[str, LevelValue] = Field(default_factory=dict)
    max_level_age_seconds: float = Field(
        ...,
        description="Freshness SLA (seconds): a boundary level older than this is stale, "
        "so its reach is opening-unavailable rather than commanded on a stale head. Must "
        "be finite and > 0 (validated in the handler so a non-finite value returns a clean "
        "400, not a NaN-echoing 422).",
    )
    apply_losses: bool = False
    charge_dry_reaches: bool = False
    always_wet: list[tuple[str, str]] = Field(default_factory=list)

    @field_validator("max_level_age_seconds", mode="before")
    @classmethod
    def _sla_not_bool(cls, v):
        return _reject_bool(v, "max_level_age_seconds")

    @field_validator("demands", mode="before")
    @classmethod
    def _demands_not_bool(cls, v):
        return _reject_bool_demand_values(v)


class ReachOpeningOut(BaseModel):
    """One commanded reach with the honest branch-split infeasibility surface: the flow
    the commanded opening actually passes is forward-recomputed, so `feasible`/`deficit`/
    `reason` never assume the target was met."""

    upstream: str
    downstream: str
    requested_m3s: float
    capacity_m3s: float
    opening_m: float
    commanded_opening_m: float
    commanded_gate_flow_m3s: float
    achievable_m3s: float
    deficit_m3s: float
    feasible: bool
    needs_pulsing: bool
    reason: str
    confidence: float


class UnavailableReachOut(BaseModel):
    """A reach carrying demand that could NOT be commanded because its boundary levels
    were not a fresh real measurement (missing / stale / future) — surfaced, never a
    fabricated opening."""

    upstream: str
    downstream: str
    requested_m3s: float
    reason: str
    unavailable_nodes: list[str]
    detail: str


class OpeningsSummary(BaseModel):
    """Network roll-up. `feasible` is True only when every demand-carrying reach was both
    commandable AND delivered within tolerance. Per-reach flows are deliberately NOT summed
    into a network total: the same demand flows through every serial reach on its path, so a
    sum double-counts it — the true requested/achievable/deficit live on each reach record.
    """

    feasible: bool
    commanded_reaches: int
    unavailable_reaches: int
    idle_reaches: int
    infeasible_reaches: list[list[str]] = Field(default_factory=list)
    reaches_needing_pulsing: list[list[str]] = Field(default_factory=list)


class OpeningsResponse(BaseModel):
    openings: list[ReachOpeningOut]
    unavailable: list[UnavailableReachOut]
    summary: OpeningsSummary
