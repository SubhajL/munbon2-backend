"""Pydantic schemas for the C9 control API (demand -> required per-reach flow)."""
from pydantic import BaseModel, Field


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


class ReachFlow(BaseModel):
    """Required flow on one reach (the gate terminating it must pass this)."""

    upstream: str
    downstream: str
    required_flow_m3s: float


class ReachChainageGap(BaseModel):
    """A partially surveyed reach: `gap_m` of its chainage carries NO surveyed
    geometry, so its conveyance loss and capacity bound understate there (2.1b)."""

    upstream: str
    downstream: str
    gap_m: float


class PlanResponse(BaseModel):
    reaches: list[ReachFlow]
    head_flow_m3s: float
    apply_losses: bool
    charge_dry_reaches: bool = False
    reaches_missing_geometry: list[list[str]] = Field(default_factory=list)
    reaches_with_chainage_gaps: list[ReachChainageGap] = Field(default_factory=list)
