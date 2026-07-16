"""Runtime orchestration seam for pure sensorless control predictions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math

from core.fulfillment import (
    ClosureProjection,
    ClosureRequirement,
    earliest_safe_closure,
)
from core.network_transient import (
    BranchAllocation,
    GateFlowEvent,
    NetworkTimeline,
    NetworkTransientError,
    SectionRequirement,
    simulate_network_timeline,
)
from core.model_release import HydraulicModelRelease
from core.model_snapshot import ModelSnapshotError, build_model_snapshot
from core.reach_response import ReachResponse, ReachState, ResponseMember


@dataclass(frozen=True)
class ControlPredictionService:
    network_edges: tuple[tuple[str, str], ...]
    reach_responses: tuple[ReachResponse, ...]
    maximum_horizon_seconds: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.network_edges, tuple) or not self.network_edges:
            raise NetworkTransientError(
                "network_edges must be a non-empty immutable tuple"
            )
        if not isinstance(self.reach_responses, tuple):
            raise NetworkTransientError("reach_responses must be an immutable tuple")
        if self.reach_responses and self.maximum_horizon_seconds is None:
            raise NetworkTransientError(
                "maximum_horizon_seconds is required with a model release"
            )
        if self.maximum_horizon_seconds is not None and (
            isinstance(self.maximum_horizon_seconds, bool)
            or not isinstance(self.maximum_horizon_seconds, (int, float))
            or not math.isfinite(self.maximum_horizon_seconds)
            or self.maximum_horizon_seconds <= 0.0
        ):
            raise NetworkTransientError(
                "maximum_horizon_seconds must be a finite number > 0"
            )

    def predict_member(
        self,
        member: ResponseMember,
        initial_states: tuple[ReachState, ...],
        gate_events: tuple[GateFlowEvent, ...],
        requirements: tuple[SectionRequirement, ...],
        branch_allocations: tuple[BranchAllocation, ...],
        starts_at: datetime,
        ends_at: datetime,
        timestep_seconds: float,
    ) -> NetworkTimeline:
        if not isinstance(member, ResponseMember):
            raise NetworkTransientError("member must be a ResponseMember")
        horizon_seconds = (ends_at - starts_at).total_seconds()
        if (
            self.maximum_horizon_seconds is not None
            and horizon_seconds > self.maximum_horizon_seconds
        ):
            raise NetworkTransientError(
                f"prediction horizon {horizon_seconds} exceeds model release envelope "
                f"{self.maximum_horizon_seconds}"
            )
        member_responses = tuple(
            response for response in self.reach_responses if response.member is member
        )
        return simulate_network_timeline(
            self.network_edges,
            member_responses,
            initial_states,
            gate_events,
            requirements,
            branch_allocations,
            starts_at,
            ends_at,
            timestep_seconds,
        )

    def earliest_safe_closure(
        self,
        closing_gate_id: str,
        requirements: tuple[ClosureRequirement, ...],
        projections: tuple[ClosureProjection, ...],
    ) -> datetime | None:
        return earliest_safe_closure(
            closing_gate_id,
            self.network_edges,
            requirements,
            projections,
        )

    def model_snapshot(
        self,
        release: HydraulicModelRelease | None,
        config_sha256: Mapping[str, str],
        actuation_approved: bool,
    ) -> dict:
        expected_horizon = (
            None
            if release is None
            else release.operating_envelope.maximum_horizon_seconds
        )
        if self.maximum_horizon_seconds != expected_horizon:
            raise ModelSnapshotError(
                "runtime prediction horizon does not match the model release"
            )
        return build_model_snapshot(
            self.network_edges,
            self.reach_responses,
            release,
            config_sha256,
            actuation_approved,
        )
