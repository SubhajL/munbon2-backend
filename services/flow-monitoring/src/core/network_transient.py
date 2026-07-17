"""Pure causal routing across a rooted canal network timeline."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import math

from .fulfillment import PredictedDeliveryState, advance_predicted_delivery
from .network_topology import ROOT, is_spanning_tree, nodes_of, topological_order
from .reach_response import (
    ReachCapacityExceededError,
    ReachResponse,
    ReachResponseError,
    ReachState,
    ResponseMember,
    route_reach_step,
    validate_reach_response,
)
from .routing_topology import RoutingRole, RoutingTopology

__all__ = [
    "BranchAllocation",
    "GateFlowEvent",
    "GateFlowStep",
    "NetworkMassBalanceAudit",
    "NetworkStep",
    "NetworkTimeline",
    "NetworkReachCapacityExceededError",
    "NetworkTransientError",
    "OperatorWithdrawalEvent",
    "ReachTimelinePoint",
    "SectionRequirement",
    "WithdrawalCapacityCheckStatus",
    "WithdrawalTimelinePoint",
    "simulate_network_timeline",
    "route_gate_events",
    "route_operator_withdrawal_events",
]


class NetworkTransientError(ValueError):
    """A network timeline is malformed or violates conservation."""


def _allocation_children(
    allocation_edges: tuple[tuple[str, str], ...],
) -> dict[str, list[str]]:
    children: dict[str, list[str]] = defaultdict(list)
    for upstream, downstream in allocation_edges:
        children[upstream].append(downstream)
    return children


def _allocated_fraction(
    downstream_nodes,
    allocations: dict[tuple[str, str], float],
    node_id: str,
    downstream_node_id: str,
) -> float:
    """THE single fraction rule shared by routing and the dry proof — the
    proof is only sound while both predict the same split."""
    if len(downstream_nodes) == 1:
        return 1.0
    return allocations[(node_id, downstream_node_id)]


class NetworkReachCapacityExceededError(NetworkTransientError):
    """One reach exceeded its authoritative capacity while routing a step.

    Distinct from plain NetworkTransientError so an orchestrator can treat
    capacity exceedance as an explicit infeasible RESULT while every other
    engine failure stays a request-rejecting error."""

    def __init__(
        self,
        reach_id: str,
        kind: str,
        attempted_flow_m3s: float,
        capacity_m3s: float,
        interval_start: datetime,
        interval_end: datetime,
        message: str,
    ) -> None:
        self.reach_id = reach_id
        self.kind = kind
        self.attempted_flow_m3s = attempted_flow_m3s
        self.capacity_m3s = capacity_m3s
        self.interval_start = interval_start
        self.interval_end = interval_end
        super().__init__(message)


@dataclass(frozen=True)
class GateFlowEvent:
    node_id: str
    effective_at: datetime
    flow_m3s: float


@dataclass(frozen=True)
class GateFlowStep:
    starts_at: datetime
    ends_at: datetime
    node_flows_m3s: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class BranchAllocation:
    upstream_node_id: str
    downstream_node_id: str
    fraction: float


@dataclass(frozen=True)
class SectionRequirement:
    requirement_id: str
    section_id: str
    delivery_node_id: str
    window_start: datetime
    window_end: datetime
    required_volume_m3: float
    maximum_delivery_m3s: float
    approved_excess_m3: float = 0.0


@dataclass(frozen=True)
class OperatorWithdrawalEvent:
    structure_id: str
    effective_at: datetime
    planned_flow_m3s: float
    purpose: str
    operator_reference: str | None = None


class WithdrawalCapacityCheckStatus(str, Enum):
    WITHIN_CAPACITY = "within_capacity"
    EXCEEDS_CAPACITY = "exceeds_capacity"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WithdrawalTimelinePoint:
    structure_id: str
    planned_flow_m3s: float
    hydraulically_available_flow_m3s: float
    predicted_withdrawal_m3s: float
    shortfall_m3s: float
    capacity_check_status: WithdrawalCapacityCheckStatus


@dataclass(frozen=True)
class ReachTimelinePoint:
    reach_id: str
    inflow_m3s: float
    outflow_m3s: float
    in_transit_volume_m3: float
    cumulative_declared_loss_m3: float


@dataclass(frozen=True)
class NetworkStep:
    starts_at: datetime
    ends_at: datetime
    reaches: tuple[ReachTimelinePoint, ...]
    withdrawals: tuple[WithdrawalTimelinePoint, ...]
    fulfillment: tuple[PredictedDeliveryState, ...]
    terminal_outflow_m3: float


@dataclass(frozen=True)
class NetworkMassBalanceAudit:
    initial_in_transit_m3: float
    boundary_inflow_m3: float
    delivered_m3: float
    withdrawn_m3: float
    declared_loss_m3: float
    terminal_outflow_m3: float
    final_in_transit_m3: float
    balance_error_m3: float


@dataclass(frozen=True)
class NetworkTimeline:
    model_release_id: str
    member: ResponseMember
    starts_at: datetime
    ends_at: datetime
    timestep_seconds: float
    steps: tuple[NetworkStep, ...]
    final_reach_states: tuple[ReachState, ...]
    final_fulfillment: tuple[PredictedDeliveryState, ...]
    mass_balance: NetworkMassBalanceAudit
    excluded_transport_reach_ids: tuple[str, ...] = ()


def route_gate_events(
    gate_events: tuple[GateFlowEvent, ...],
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
) -> tuple[GateFlowStep, ...]:
    if not isinstance(gate_events, tuple):
        raise NetworkTransientError("gate_events must be an immutable tuple")
    step_count = _validate_timeline(starts_at, ends_at, timestep_seconds)
    events_by_time: dict[datetime, list[GateFlowEvent]] = defaultdict(list)
    seen = set()
    node_ids = set()
    for event in gate_events:
        _validate_non_blank(event.node_id, "gate_event.node_id")
        _validate_aware(event.effective_at, "gate_event.effective_at")
        _validate_non_negative(event.flow_m3s, "gate_event.flow_m3s")
        if not starts_at <= event.effective_at < ends_at:
            raise NetworkTransientError(
                "gate event effective_at must be within the simulation horizon"
            )
        _validate_aligned(event.effective_at, starts_at, timestep_seconds, "gate event")
        key = (event.node_id, event.effective_at)
        if key in seen:
            raise NetworkTransientError("duplicate gate event for node and instant")
        seen.add(key)
        node_ids.add(event.node_id)
        events_by_time[event.effective_at].append(event)

    active_flows = {node_id: 0.0 for node_id in sorted(node_ids)}
    steps = []
    for index in range(step_count):
        step_start = starts_at + timedelta(seconds=index * timestep_seconds)
        for event in sorted(
            events_by_time.get(step_start, ()), key=lambda event: event.node_id
        ):
            active_flows[event.node_id] = event.flow_m3s
        steps.append(
            GateFlowStep(
                starts_at=step_start,
                ends_at=step_start + timedelta(seconds=timestep_seconds),
                node_flows_m3s=tuple(sorted(active_flows.items())),
            )
        )
    return tuple(steps)


def simulate_network_timeline(
    routing_topology: RoutingTopology,
    responses: tuple[ReachResponse, ...],
    initial_states: tuple[ReachState, ...],
    gate_events: tuple[GateFlowEvent, ...],
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
    withdrawal_capacity_m3s: Mapping[str, float | None],
    requirements: tuple[SectionRequirement, ...],
    branch_allocations: tuple[BranchAllocation, ...],
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
    unavailable_transport_reach_ids: frozenset[str] = frozenset(),
) -> NetworkTimeline:
    if not isinstance(routing_topology, RoutingTopology):
        raise NetworkTransientError(
            "simulate_network_timeline requires a typed RoutingTopology"
        )
    if not isinstance(unavailable_transport_reach_ids, frozenset):
        raise NetworkTransientError(
            "unavailable_transport_reach_ids must be a frozenset of reach ids"
        )
    network_edges = routing_topology.routing_edges()
    transport_edges = frozenset(
        (element.upstream_node_id, element.downstream_node_id)
        for element in routing_topology.elements
        if element.role is RoutingRole.TRANSPORT
    )
    transport_reach_ids = routing_topology.transport_reach_ids()
    withdrawal_elements = tuple(
        element
        for element in routing_topology.elements
        if element.role is RoutingRole.WITHDRAWAL_STRUCTURE
    )
    withdrawal_order = routing_topology.withdrawal_structure_node_ids()
    allocation_edges = routing_topology.allocation_edges()
    _validate_network_edges(network_edges)
    _validate_timeline(starts_at, ends_at, timestep_seconds)
    allocations = _validate_branch_allocations(allocation_edges, branch_allocations)
    covered_reach_ids, excluded_dependent_reach_ids = (
        _validate_unavailable_transport_coverage(
            transport_reach_ids,
            unavailable_transport_reach_ids,
            network_edges,
            allocation_edges,
            transport_edges,
            allocations,
            requirements,
            withdrawal_events,
            initial_states,
        )
    )
    response_by_reach, model_release_id, member = _validate_response_coverage(
        covered_reach_ids, responses, timestep_seconds
    )
    state_by_reach = _validate_initial_state_coverage(response_by_reach, initial_states)
    _validate_excluded_dependent_states_dry(
        excluded_dependent_reach_ids, state_by_reach
    )
    capacity_by_structure = _validate_withdrawal_capacity(
        withdrawal_order, withdrawal_capacity_m3s
    )
    withdrawal_plans = route_operator_withdrawal_events(
        withdrawal_events,
        frozenset(withdrawal_order),
        starts_at,
        ends_at,
        timestep_seconds,
    )
    requirements_by_node, fulfillment_by_id = _validate_requirements(
        routing_topology.canonical_gate_node_ids()
        - set(withdrawal_order),
        requirements,
        starts_at,
        ends_at,
        timestep_seconds,
    )
    gate_steps = route_gate_events(gate_events, starts_at, ends_at, timestep_seconds)
    non_root_event_nodes = {
        event.node_id for event in gate_events if event.node_id != ROOT
    }
    if non_root_event_nodes:
        raise NetworkTransientError(
            "gate flow events may inject water only at the network root; "
            f"got {sorted(non_root_event_nodes)!r}"
        )
    network_nodes = nodes_of(network_edges)
    unknown_event_nodes = {
        node_id
        for step in gate_steps
        for node_id, _ in step.node_flows_m3s
        if node_id not in network_nodes
    }
    if unknown_event_nodes:
        raise NetworkTransientError(
            f"gate events contain unknown nodes {sorted(unknown_event_nodes)!r}"
        )

    children = _allocation_children(allocation_edges)
    withdrawal_children_by_node: dict[str, list[str]] = defaultdict(list)
    for element in withdrawal_elements:
        withdrawal_children_by_node[element.upstream_node_id].append(
            element.downstream_node_id
        )
    ordered_nodes = topological_order(network_edges)
    initial_in_transit_m3 = sum(
        state.in_transit_volume_m3 for state in state_by_reach.values()
    )
    initial_declared_loss_m3 = sum(
        state.cumulative_declared_loss_m3 for state in state_by_reach.values()
    )
    boundary_inflow_m3 = 0.0
    terminal_outflow_m3 = 0.0
    withdrawn_m3 = 0.0
    timeline_steps = []
    for step_index, gate_step in enumerate(gate_steps):
        (
            network_step,
            state_by_reach,
            fulfillment_by_id,
            step_boundary_inflow_m3,
        ) = _route_network_step(
            gate_step,
            covered_reach_ids,
            unavailable_transport_reach_ids,
            transport_edges,
            ordered_nodes,
            children,
            withdrawal_children_by_node,
            withdrawal_order,
            withdrawal_plans[step_index],
            capacity_by_structure,
            response_by_reach,
            state_by_reach,
            allocations,
            requirements,
            requirements_by_node,
            fulfillment_by_id,
            timestep_seconds,
        )
        boundary_inflow_m3 += step_boundary_inflow_m3
        terminal_outflow_m3 += network_step.terminal_outflow_m3
        withdrawn_m3 += sum(
            point.predicted_withdrawal_m3s * timestep_seconds
            for point in network_step.withdrawals
        )
        timeline_steps.append(network_step)

    final_states = tuple(
        state_by_reach[reach_id] for reach_id in covered_reach_ids
    )
    final_fulfillment = tuple(
        fulfillment_by_id[requirement.requirement_id] for requirement in requirements
    )
    delivered_m3 = sum(state.predicted_delivered_m3 for state in final_fulfillment)
    declared_loss_m3 = (
        sum(state.cumulative_declared_loss_m3 for state in final_states)
        - initial_declared_loss_m3
    )
    final_in_transit_m3 = sum(state.in_transit_volume_m3 for state in final_states)
    supplied_m3 = initial_in_transit_m3 + boundary_inflow_m3
    accounted_m3 = (
        delivered_m3
        + withdrawn_m3
        + declared_loss_m3
        + terminal_outflow_m3
        + final_in_transit_m3
    )
    balance_error_m3 = supplied_m3 - accounted_m3
    tolerance_m3 = max(1e-8, abs(supplied_m3) * 1e-12)
    if abs(balance_error_m3) > tolerance_m3:
        raise NetworkTransientError(
            f"network mass balance is broken: supplied={supplied_m3}, "
            f"accounted={accounted_m3}"
        )
    return NetworkTimeline(
        model_release_id=model_release_id,
        member=member,
        starts_at=starts_at,
        ends_at=ends_at,
        timestep_seconds=timestep_seconds,
        steps=tuple(timeline_steps),
        final_reach_states=final_states,
        final_fulfillment=final_fulfillment,
        mass_balance=NetworkMassBalanceAudit(
            initial_in_transit_m3=initial_in_transit_m3,
            boundary_inflow_m3=boundary_inflow_m3,
            delivered_m3=delivered_m3,
            withdrawn_m3=withdrawn_m3,
            declared_loss_m3=declared_loss_m3,
            terminal_outflow_m3=terminal_outflow_m3,
            final_in_transit_m3=final_in_transit_m3,
            balance_error_m3=balance_error_m3,
        ),
        excluded_transport_reach_ids=tuple(
            sorted(unavailable_transport_reach_ids)
        ),
    )


def _route_network_step(
    gate_step: GateFlowStep,
    transport_reach_ids: tuple[str, ...],
    unavailable_transport_reach_ids: frozenset[str],
    transport_edges: frozenset[tuple[str, str]],
    ordered_nodes: list[str],
    children: dict[str, list[str]],
    withdrawal_children_by_node: dict[str, list[str]],
    withdrawal_order: tuple[str, ...],
    withdrawal_plan: dict[str, float],
    withdrawal_capacity: dict[str, float | None],
    responses: dict[str, ReachResponse],
    states: dict[str, ReachState],
    allocations: dict[tuple[str, str], float],
    requirements: tuple[SectionRequirement, ...],
    requirements_by_node: dict[str, tuple[SectionRequirement, ...]],
    fulfillment: dict[str, PredictedDeliveryState],
    timestep_seconds: float,
) -> tuple[
    NetworkStep,
    dict[str, ReachState],
    dict[str, PredictedDeliveryState],
    float,
]:
    next_states = dict(states)
    next_fulfillment = dict(fulfillment)
    available_by_node_m3: defaultdict[str, float] = defaultdict(float)
    boundary_inflow_m3 = 0.0
    for node_id, flow_m3s in gate_step.node_flows_m3s:
        volume_m3 = flow_m3s * timestep_seconds
        available_by_node_m3[node_id] += volume_m3
        boundary_inflow_m3 += volume_m3

    points_by_reach = {}
    withdrawal_points: dict[str, WithdrawalTimelinePoint] = {}
    terminal_outflow_m3 = 0.0
    for node_id in ordered_nodes:
        available_m3 = available_by_node_m3[node_id]
        for requirement in requirements_by_node.get(node_id, ()):
            if not (
                requirement.window_start <= gate_step.starts_at < requirement.window_end
            ):
                continue
            state = next_fulfillment[requirement.requirement_id]
            remaining_m3 = max(
                0.0,
                requirement.required_volume_m3 - state.predicted_delivered_m3,
            )
            delivered_m3 = min(
                available_m3,
                remaining_m3,
                requirement.maximum_delivery_m3s * timestep_seconds,
            )
            next_fulfillment[requirement.requirement_id] = advance_predicted_delivery(
                state, delivered_m3, 0.0
            )
            available_m3 -= delivered_m3

        # Planned operator withdrawals leave at the structure's upstream
        # junction, before any water is allocated downstream. Predicted
        # withdrawal is limited by what is physically present and, when an
        # authoritative structure maximum exists, by that ceiling.
        for structure_id in withdrawal_children_by_node.get(node_id, ()):
            planned_flow_m3s = withdrawal_plan.get(structure_id, 0.0)
            available_flow_m3s = available_m3 / timestep_seconds
            q_max = withdrawal_capacity[structure_id]
            if q_max is None:
                capacity_status = WithdrawalCapacityCheckStatus.UNAVAILABLE
                withdrawn_volume_m3 = min(
                    planned_flow_m3s * timestep_seconds, available_m3
                )
            else:
                capacity_status = (
                    WithdrawalCapacityCheckStatus.EXCEEDS_CAPACITY
                    if planned_flow_m3s > q_max
                    else WithdrawalCapacityCheckStatus.WITHIN_CAPACITY
                )
                withdrawn_volume_m3 = min(
                    planned_flow_m3s * timestep_seconds,
                    available_m3,
                    q_max * timestep_seconds,
                )
            # The clamp works in the volume domain so draining the junction
            # leaves exactly 0.0 — a flow/volume round-trip can leave a
            # negative float residue that crashes downstream validation.
            available_m3 -= withdrawn_volume_m3
            predicted_flow_m3s = withdrawn_volume_m3 / timestep_seconds
            withdrawal_points[structure_id] = WithdrawalTimelinePoint(
                structure_id=structure_id,
                planned_flow_m3s=planned_flow_m3s,
                hydraulically_available_flow_m3s=available_flow_m3s,
                predicted_withdrawal_m3s=predicted_flow_m3s,
                shortfall_m3s=planned_flow_m3s - predicted_flow_m3s,
                capacity_check_status=capacity_status,
            )

        downstream_nodes = children.get(node_id, ())
        if not downstream_nodes:
            terminal_outflow_m3 += available_m3
            continue
        for downstream_node_id in downstream_nodes:
            fraction = _allocated_fraction(
                downstream_nodes, allocations, node_id, downstream_node_id
            )
            allocated_m3 = available_m3 * fraction
            if (node_id, downstream_node_id) not in transport_edges:
                # Boundary/branch/withdrawal structures are instantaneous
                # non-transport transitions at V1 resolution: the allocated
                # volume arrives downstream within the same step, with no
                # storage, loss, capacity, or fabricated reach response.
                available_by_node_m3[downstream_node_id] += allocated_m3
                continue
            inflow_m3s = allocated_m3 / timestep_seconds
            reach_id = _reach_id(node_id, downstream_node_id)
            if reach_id in unavailable_transport_reach_ids:
                # Statically proven dry at validation time; a nonzero volume
                # here means that proof was wrong — never route through a
                # reach that has no authoritative response.
                if allocated_m3 != 0.0:
                    raise NetworkTransientError(
                        f"unavailable transport reach {reach_id!r} received "
                        f"{allocated_m3} m3 despite the static dry proof"
                    )
                continue
            response = responses[reach_id]
            try:
                next_state = route_reach_step(
                    response,
                    next_states[reach_id],
                    inflow_m3s,
                    timestep_seconds,
                )
            except ReachCapacityExceededError as exc:
                raise NetworkReachCapacityExceededError(
                    reach_id,
                    exc.kind,
                    exc.attempted_flow_m3s,
                    exc.capacity_m3s,
                    gate_step.starts_at,
                    gate_step.ends_at,
                    f"reach {reach_id!r} routing failed: {exc}",
                ) from exc
            except ReachResponseError as exc:
                raise NetworkTransientError(
                    f"reach {reach_id!r} routing failed: {exc}"
                ) from exc
            next_states[reach_id] = next_state
            available_by_node_m3[downstream_node_id] += (
                next_state.outflow_m3s * timestep_seconds
            )
            points_by_reach[reach_id] = ReachTimelinePoint(
                reach_id=reach_id,
                inflow_m3s=inflow_m3s,
                outflow_m3s=next_state.outflow_m3s,
                in_transit_volume_m3=next_state.in_transit_volume_m3,
                cumulative_declared_loss_m3=(next_state.cumulative_declared_loss_m3),
            )
    return (
        NetworkStep(
            starts_at=gate_step.starts_at,
            ends_at=gate_step.ends_at,
            reaches=tuple(
                points_by_reach[reach_id] for reach_id in transport_reach_ids
            ),
            withdrawals=tuple(
                withdrawal_points[structure_id]
                for structure_id in withdrawal_order
            ),
            fulfillment=tuple(
                next_fulfillment[requirement.requirement_id]
                for requirement in requirements
            ),
            terminal_outflow_m3=terminal_outflow_m3,
        ),
        next_states,
        next_fulfillment,
        boundary_inflow_m3,
    )


def _validate_network_edges(
    network_edges: tuple[tuple[str, str], ...],
) -> None:
    if not isinstance(network_edges, tuple) or not network_edges:
        raise NetworkTransientError("network_edges must be a non-empty immutable tuple")
    if not all(
        isinstance(edge, tuple)
        and len(edge) == 2
        and all(isinstance(node, str) and node.strip() for node in edge)
        for edge in network_edges
    ):
        raise NetworkTransientError("every network edge must be a pair of node ids")
    if len(set(network_edges)) != len(network_edges) or not is_spanning_tree(
        network_edges, ROOT
    ):
        raise NetworkTransientError("network_edges must form a rooted spanning tree")


def _validate_unavailable_transport_coverage(
    transport_reach_ids: tuple[str, ...],
    unavailable_transport_reach_ids: frozenset[str],
    network_edges: tuple[tuple[str, str], ...],
    allocation_edges: tuple[tuple[str, str], ...],
    transport_edges: frozenset[tuple[str, str]],
    allocations: dict[tuple[str, str], float],
    requirements: tuple[SectionRequirement, ...],
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
    initial_states: tuple[ReachState, ...],
) -> tuple[tuple[str, ...], frozenset[str]]:
    """Statically prove every unavailable transport reach stays dry and
    unrequested. Returns (covered reach ids, reaches whose supply path
    crosses an excluded reach). Water enters at the root AND from any warm
    initial in-transit volume, so a reach is provably dry only when no
    positive-allocation path from either source reaches it; a requirement or
    withdrawal whose supply path crosses an unavailable reach cannot be
    predicted at all — fail closed."""
    if not unavailable_transport_reach_ids:
        return tuple(transport_reach_ids), frozenset()
    unknown = unavailable_transport_reach_ids - set(transport_reach_ids)
    if unknown:
        raise NetworkTransientError(
            "unavailable transport reach ids are not transport reaches: "
            f"{sorted(unknown)!r}"
        )
    excluded_edges = {
        (upstream, downstream)
        for upstream, downstream in transport_edges
        if _reach_id(upstream, downstream) in unavailable_transport_reach_ids
    }
    children = _allocation_children(allocation_edges)
    downstream_by_reach = {
        _reach_id(upstream, downstream): downstream
        for upstream, downstream in transport_edges
    }
    wet = {ROOT}
    for state in initial_states:
        if state.in_transit_volume_m3 > 0.0 or state.outflow_m3s > 0.0:
            warm_node = downstream_by_reach.get(state.reach_id)
            if warm_node is not None:
                wet.add(warm_node)
    pending = list(wet)
    while pending:
        node_id = pending.pop()
        downstream_nodes = children.get(node_id, ())
        for downstream_node_id in downstream_nodes:
            fraction = _allocated_fraction(
                downstream_nodes, allocations, node_id, downstream_node_id
            )
            if fraction <= 0.0:
                continue
            if (node_id, downstream_node_id) in excluded_edges:
                raise NetworkTransientError(
                    "unavailable transport reach "
                    f"{_reach_id(node_id, downstream_node_id)!r} would "
                    "receive water; allocate exactly zero into it or use a "
                    "model release that covers it"
                )
            if downstream_node_id not in wet:
                wet.add(downstream_node_id)
                pending.append(downstream_node_id)
    parent_by_node = {
        downstream: upstream for upstream, downstream in network_edges
    }
    subjects = [
        ("requirement", requirement.requirement_id, requirement.delivery_node_id)
        for requirement in requirements
    ] + [
        ("operator withdrawal", event.structure_id, event.structure_id)
        for event in withdrawal_events
    ]
    for label, subject_id, node_id in subjects:
        child = node_id
        while child in parent_by_node:
            parent = parent_by_node[child]
            if (parent, child) in excluded_edges:
                raise NetworkTransientError(
                    f"{label} {subject_id!r} requires unavailable transport "
                    f"reach {_reach_id(parent, child)!r}"
                )
            child = parent
    excluded_dependent = []
    for upstream, downstream in sorted(transport_edges - excluded_edges):
        child = upstream
        while child in parent_by_node:
            parent = parent_by_node[child]
            if (parent, child) in excluded_edges:
                excluded_dependent.append(_reach_id(upstream, downstream))
                break
            child = parent
    return (
        tuple(
            reach_id
            for reach_id in transport_reach_ids
            if reach_id not in unavailable_transport_reach_ids
        ),
        frozenset(excluded_dependent),
    )


def _validate_excluded_dependent_states_dry(
    excluded_dependent_reach_ids: frozenset[str],
    state_by_reach: dict[str, ReachState],
) -> None:
    """A reach whose only supply path crosses an unavailable transport can
    hold no honestly-known water: with the flume unmodeled, any wet initial
    state below it fabricates lineage the model cannot account for."""
    for reach_id in sorted(excluded_dependent_reach_ids):
        state = state_by_reach[reach_id]
        if (
            state.transit_volumes
            or state.initial_volume_m3 != 0.0
            or state.cumulative_inflow_m3 != 0.0
            or state.cumulative_outflow_m3 != 0.0
            or state.cumulative_withdrawal_m3 != 0.0
            or state.cumulative_declared_loss_m3 != 0.0
            or state.cumulative_operational_loss_m3 != 0.0
            or state.outflow_m3s != 0.0
        ):
            raise NetworkTransientError(
                f"initial state for reach {reach_id!r} must be dry: its "
                "supply path crosses an unavailable transport reach"
            )


def _validate_response_coverage(
    transport_reach_ids: tuple[str, ...],
    responses: tuple[ReachResponse, ...],
    timestep_seconds: float,
) -> tuple[dict[str, ReachResponse], str, ResponseMember]:
    if not isinstance(responses, tuple) or not responses:
        raise NetworkTransientError("response coverage is empty")
    response_by_reach = {}
    for response in responses:
        try:
            validate_reach_response(response)
        except ReachResponseError as exc:
            raise NetworkTransientError(str(exc)) from exc
        if response.reach_id in response_by_reach:
            raise NetworkTransientError("response coverage contains duplicate reach_id")
        if not (
            response.minimum_timestep_seconds
            <= timestep_seconds
            <= response.maximum_timestep_seconds
        ):
            raise NetworkTransientError(
                f"timestep is outside response envelope for {response.reach_id!r}"
            )
        response_by_reach[response.reach_id] = response
    expected = set(transport_reach_ids)
    if set(response_by_reach) != expected:
        raise NetworkTransientError(
            f"response coverage must exactly equal transport reaches; "
            f"missing={sorted(expected - set(response_by_reach))!r}, "
            f"unknown={sorted(set(response_by_reach) - expected)!r}"
        )
    release_ids = {response.model_release_id for response in responses}
    members = {response.member for response in responses}
    if len(release_ids) != 1 or len(members) != 1:
        raise NetworkTransientError(
            "responses must have one model_release_id and one parameter member"
        )
    return response_by_reach, release_ids.pop(), members.pop()


def _validate_initial_state_coverage(
    responses: dict[str, ReachResponse], initial_states: tuple[ReachState, ...]
) -> dict[str, ReachState]:
    if not isinstance(initial_states, tuple):
        raise NetworkTransientError("initial_states must be an immutable tuple")
    states = {}
    for state in initial_states:
        if state.reach_id in states:
            raise NetworkTransientError(
                "initial state coverage contains duplicate reach_id"
            )
        states[state.reach_id] = state
    if set(states) != set(responses):
        raise NetworkTransientError(
            "initial state coverage must equal response coverage"
        )
    for reach_id, response in responses.items():
        state = states[reach_id]
        if (
            state.model_release_id,
            state.reach_id,
            state.member,
        ) != (
            response.model_release_id,
            response.reach_id,
            response.member,
        ):
            raise NetworkTransientError(
                f"initial state lineage does not match response for {reach_id!r}"
            )
    return states


def _validate_withdrawal_capacity(
    withdrawal_order: tuple[str, ...],
    withdrawal_capacity_m3s: Mapping[str, float | None],
) -> dict[str, float | None]:
    if not isinstance(withdrawal_capacity_m3s, Mapping):
        raise NetworkTransientError(
            "withdrawal_capacity_m3s must be a mapping of structure id to "
            "authoritative maximum flow or None"
        )
    expected = set(withdrawal_order)
    if set(withdrawal_capacity_m3s) != expected:
        raise NetworkTransientError(
            "withdrawal capacity coverage must exactly equal the withdrawal "
            f"structures; missing={sorted(expected - set(withdrawal_capacity_m3s))!r}, "
            f"unknown={sorted(set(withdrawal_capacity_m3s) - expected)!r}"
        )
    for structure_id, q_max in withdrawal_capacity_m3s.items():
        if q_max is None:
            continue
        if (
            isinstance(q_max, bool)
            or not isinstance(q_max, (int, float))
            or not math.isfinite(q_max)
            or q_max <= 0.0
        ):
            raise NetworkTransientError(
                f"withdrawal capacity for {structure_id!r} must be None or a "
                "positive finite flow"
            )
    return dict(withdrawal_capacity_m3s)


def route_operator_withdrawal_events(
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...],
    withdrawal_structures: frozenset[str],
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
) -> tuple[dict[str, float], ...]:
    if not isinstance(withdrawal_events, tuple):
        raise NetworkTransientError(
            "withdrawal_events must be an immutable tuple"
        )
    step_count = _validate_timeline(starts_at, ends_at, timestep_seconds)
    events_by_time: dict[datetime, list[OperatorWithdrawalEvent]] = defaultdict(list)
    seen = set()
    for event in withdrawal_events:
        if event.structure_id not in withdrawal_structures:
            raise NetworkTransientError(
                f"withdrawal event targets {event.structure_id!r}, which is "
                "not a withdrawal structure in the routing topology"
            )
        _validate_aware(event.effective_at, "withdrawal_event.effective_at")
        _validate_non_negative(
            event.planned_flow_m3s, "withdrawal_event.planned_flow_m3s"
        )
        _validate_non_blank(event.purpose, "withdrawal_event.purpose")
        if event.operator_reference is not None and (
            not isinstance(event.operator_reference, str)
            or not event.operator_reference.strip()
        ):
            raise NetworkTransientError(
                "withdrawal_event.operator_reference must be None or non-blank"
            )
        if not starts_at <= event.effective_at < ends_at:
            raise NetworkTransientError(
                "withdrawal event effective_at must be within the simulation "
                "horizon"
            )
        _validate_aligned(
            event.effective_at, starts_at, timestep_seconds, "withdrawal event"
        )
        key = (event.structure_id, event.effective_at)
        if key in seen:
            raise NetworkTransientError(
                "duplicate withdrawal event for structure and instant"
            )
        seen.add(key)
        events_by_time[event.effective_at].append(event)

    active: dict[str, float] = {}
    plans = []
    for index in range(step_count):
        step_start = starts_at + timedelta(seconds=index * timestep_seconds)
        for event in sorted(
            events_by_time.get(step_start, ()),
            key=lambda event: event.structure_id,
        ):
            active[event.structure_id] = event.planned_flow_m3s
        plans.append(dict(active))
    return tuple(plans)


def _validate_branch_allocations(
    network_edges: tuple[tuple[str, str], ...],
    branch_allocations: tuple[BranchAllocation, ...],
) -> dict[tuple[str, str], float]:
    if not isinstance(branch_allocations, tuple):
        raise NetworkTransientError("branch_allocations must be an immutable tuple")
    children = _allocation_children(network_edges)
    allocations = {}
    for allocation in branch_allocations:
        key = (allocation.upstream_node_id, allocation.downstream_node_id)
        if key in allocations:
            raise NetworkTransientError("branch allocation contains duplicate edge")
        if (
            allocation.upstream_node_id not in children
            or len(children[allocation.upstream_node_id]) <= 1
            or allocation.downstream_node_id
            not in children[allocation.upstream_node_id]
        ):
            raise NetworkTransientError(
                f"branch allocation has unknown branch edge {key!r}"
            )
        _validate_non_negative(allocation.fraction, "branch_allocation.fraction")
        allocations[key] = allocation.fraction
    for upstream, downstream_nodes in children.items():
        if len(downstream_nodes) <= 1:
            continue
        expected = {(upstream, downstream) for downstream in downstream_nodes}
        actual = {key for key in allocations if key[0] == upstream}
        if actual != expected or not math.isclose(
            sum(allocations[key] for key in expected),
            1.0,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise NetworkTransientError(
                f"branch allocation for {upstream!r} must cover every child and sum to 1"
            )
    return allocations


def _validate_requirements(
    gate_node_ids: frozenset[str] | set[str],
    requirements: tuple[SectionRequirement, ...],
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
) -> tuple[
    dict[str, tuple[SectionRequirement, ...]], dict[str, PredictedDeliveryState]
]:
    if not isinstance(requirements, tuple):
        raise NetworkTransientError("requirements must be an immutable tuple")
    nodes = gate_node_ids
    by_node: dict[str, list[SectionRequirement]] = defaultdict(list)
    states = {}
    for requirement in requirements:
        _validate_non_blank(requirement.requirement_id, "requirement.requirement_id")
        _validate_non_blank(requirement.section_id, "requirement.section_id")
        _validate_non_blank(
            requirement.delivery_node_id, "requirement.delivery_node_id"
        )
        if requirement.requirement_id in states:
            raise NetworkTransientError(
                "requirements contains duplicate requirement_id"
            )
        if (
            requirement.delivery_node_id not in nodes
            or requirement.delivery_node_id == ROOT
        ):
            raise NetworkTransientError(
                "requirement delivery_node_id must be a deliverable canal "
                "gate; withdrawal structure releases are operator withdrawal "
                "events, not section deliveries"
            )
        _validate_aware(requirement.window_start, "requirement.window_start")
        _validate_aware(requirement.window_end, "requirement.window_end")
        if requirement.window_end <= requirement.window_start:
            raise NetworkTransientError(
                "requirement window_end must follow window_start"
            )
        for boundary in (requirement.window_start, requirement.window_end):
            if starts_at < boundary < ends_at:
                _validate_aligned(
                    boundary, starts_at, timestep_seconds, "requirement window"
                )
        _validate_positive(requirement.required_volume_m3, "required_volume_m3")
        _validate_positive(requirement.maximum_delivery_m3s, "maximum_delivery_m3s")
        _validate_non_negative(requirement.approved_excess_m3, "approved_excess_m3")
        by_node[requirement.delivery_node_id].append(requirement)
        states[requirement.requirement_id] = PredictedDeliveryState(
            requirement_id=requirement.requirement_id,
            section_id=requirement.section_id,
            required_volume_m3=requirement.required_volume_m3,
            approved_excess_m3=requirement.approved_excess_m3,
        )
    ordered = {
        node_id: tuple(
            sorted(
                node_requirements,
                key=lambda item: (item.window_end, item.requirement_id),
            )
        )
        for node_id, node_requirements in by_node.items()
    }
    return ordered, states


def _validate_timeline(
    starts_at: datetime, ends_at: datetime, timestep_seconds: float
) -> int:
    _validate_aware(starts_at, "starts_at")
    _validate_aware(ends_at, "ends_at")
    _validate_positive(timestep_seconds, "timestep_seconds")
    horizon_seconds = (ends_at - starts_at).total_seconds()
    if horizon_seconds <= 0.0:
        raise NetworkTransientError("ends_at must follow starts_at")
    step_count = horizon_seconds / timestep_seconds
    if not step_count.is_integer():
        raise NetworkTransientError(
            "simulation horizon must be an exact timestep multiple"
        )
    return int(step_count)


def _validate_aligned(
    instant: datetime, starts_at: datetime, timestep_seconds: float, label: str
) -> None:
    offset_steps = (instant - starts_at).total_seconds() / timestep_seconds
    if not offset_steps.is_integer():
        raise NetworkTransientError(f"{label} must align to a timestep boundary")


def _reach_id(upstream_node_id: str, downstream_node_id: str) -> str:
    return f"C_{upstream_node_id}_{downstream_node_id}"


def _validate_non_blank(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise NetworkTransientError(f"{label} must be a non-empty string")


def _validate_aware(value: datetime, label: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise NetworkTransientError(f"{label} must be timezone-aware")


def _validate_number(value: float, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise NetworkTransientError(f"{label} must be a finite number")


def _validate_non_negative(value: float, label: str) -> None:
    _validate_number(value, label)
    if value < 0.0:
        raise NetworkTransientError(f"{label} must be >= 0")


def _validate_positive(value: float, label: str) -> None:
    _validate_number(value, label)
    if value <= 0.0:
        raise NetworkTransientError(f"{label} must be > 0")
