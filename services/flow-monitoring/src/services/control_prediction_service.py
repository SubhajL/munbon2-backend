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
    OperatorWithdrawalEvent,
    SectionRequirement,
    simulate_network_timeline,
)
from core.model_release import HydraulicModelRelease
from core.model_snapshot import ModelSnapshotError, build_model_snapshot
from core.reach_response import ReachResponse, ReachState, ResponseMember
from core.routing_topology import RoutingRole, RoutingTopology


def build_withdrawal_structure_max_flow_map(
    routing_topology: RoutingTopology,
    gate_calibrations_config: Mapping[str, object],
) -> tuple[tuple[str, float | None], ...]:
    """Authoritative structure maxima for the withdrawal structures.

    The ONLY accepted source is gate_calibrations
    ``gates[structure_id].structure_max_flow_m3s`` — never rated q_max,
    dimensions, or donor inference. Absent metadata stays None so capacity
    checks report unavailable instead of fabricating a ceiling.
    """
    gates = gate_calibrations_config.get("gates")
    if not isinstance(gates, Mapping):
        raise NetworkTransientError(
            "gate calibrations config must carry a gates mapping"
        )
    capacity: dict[str, float | None] = {}
    for element in routing_topology.elements:
        if element.role is not RoutingRole.WITHDRAWAL_STRUCTURE:
            continue
        structure_id = element.downstream_node_id
        gate = gates.get(structure_id)
        if not isinstance(gate, Mapping):
            raise NetworkTransientError(
                f"withdrawal structure {structure_id!r} is absent from the "
                "gate calibrations artifact"
            )
        q_max = gate.get("structure_max_flow_m3s")
        if q_max is not None and (
            isinstance(q_max, bool)
            or not isinstance(q_max, (int, float))
            or not math.isfinite(q_max)
            or q_max <= 0.0
        ):
            raise NetworkTransientError(
                f"structure_max_flow_m3s for {structure_id!r} must be None "
                "or a positive finite flow"
            )
        capacity[structure_id] = q_max
    return tuple(sorted(capacity.items()))


@dataclass(frozen=True)
class ControlPredictionService:
    routing_topology: RoutingTopology
    reach_responses: tuple[ReachResponse, ...]
    maximum_horizon_seconds: float | None
    structure_max_flow_m3s_by_id: tuple[tuple[str, float | None], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.routing_topology, RoutingTopology):
            raise NetworkTransientError(
                "routing_topology must be a typed RoutingTopology"
            )
        if not isinstance(self.structure_max_flow_m3s_by_id, tuple):
            raise NetworkTransientError(
                "structure_max_flow_m3s_by_id must be an immutable tuple of "
                "(structure_id, q_max) pairs"
            )
        expected = {
            element.downstream_node_id
            for element in self.routing_topology.elements
            if element.role is RoutingRole.WITHDRAWAL_STRUCTURE
        }
        provided = [pair[0] for pair in self.structure_max_flow_m3s_by_id]
        if len(provided) != len(set(provided)) or set(provided) != expected:
            raise NetworkTransientError(
                "structure_max_flow_m3s_by_id must cover exactly the "
                f"withdrawal structures {sorted(expected)!r}"
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
        withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
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
            self.routing_topology,
            member_responses,
            initial_states,
            gate_events,
            withdrawal_events,
            dict(self.structure_max_flow_m3s_by_id),
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
        if closing_gate_id not in self.routing_topology.canonical_gate_node_ids():
            raise NetworkTransientError(
                f"closing_gate_id {closing_gate_id!r} must be a canal gate, "
                "not a virtual routing node"
            )
        routing_edges = self.routing_topology.routing_edges()
        return earliest_safe_closure(
            closing_gate_id,
            routing_edges,
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
            self.routing_topology,
            self.reach_responses,
            release,
            config_sha256,
            actuation_approved,
        )
