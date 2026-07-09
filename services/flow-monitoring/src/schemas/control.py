"""Pydantic schemas for the C9 control API (demand -> required per-reach flow)."""
from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    """A per-node water demand to turn into a per-reach flow plan."""

    demands: dict[str, float] = Field(
        default_factory=dict,
        description="Per-node water demand keyed by network node id, m3/s.",
    )
    apply_losses: bool = Field(
        default=False,
        description="Add B5 conveyance (seepage + operational) loss to each reach.",
    )


class ReachFlow(BaseModel):
    """Required flow on one reach (the gate terminating it must pass this)."""

    upstream: str
    downstream: str
    required_flow_m3s: float


class PlanResponse(BaseModel):
    reaches: list[ReachFlow]
    head_flow_m3s: float
    apply_losses: bool
    reaches_missing_geometry: list[list[str]] = Field(default_factory=list)
