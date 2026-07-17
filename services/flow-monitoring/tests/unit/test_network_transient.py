import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from core.fulfillment import PredictedFulfillmentStatus
from core.network_transient import (
    BranchAllocation,
    GateFlowEvent,
    NetworkMassBalanceAudit,
    NetworkTransientError,
    OperatorWithdrawalEvent,
    SectionRequirement,
    WithdrawalCapacityCheckStatus,
    route_gate_events,
    simulate_network_timeline,
)
from core.reach_response import (
    ReachResponse,
    ReachState,
    ResponseMember,
    TransitVolume,
)
from core.routing_topology import (
    RoutingElement,
    RoutingGeometryStatus,
    RoutingRole,
    build_routing_topology,
    derive_routing_topology,
)

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
DT_S = 60.0
CONFIG_DIR = Path(__file__).resolve().parents[2] / "src" / "config"
CANONICAL_NETWORK = CONFIG_DIR / "network.json"

_ROLE_PREFIX = {
    RoutingRole.BOUNDARY: "B",
    RoutingRole.TRANSPORT: "C",
    RoutingRole.BRANCH_STRUCTURE: "BR",
    RoutingRole.WITHDRAWAL_STRUCTURE: "WD",
}


def _reach_id(upstream: str, downstream: str) -> str:
    return f"C_{upstream}_{downstream}"


def _routing_element(
    upstream: str,
    downstream: str,
    role: RoutingRole = RoutingRole.TRANSPORT,
) -> RoutingElement:
    return RoutingElement(
        element_id=f"{_ROLE_PREFIX[role]}_{upstream}_{downstream}",
        upstream_node_id=upstream,
        downstream_node_id=downstream,
        role=role,
        canonical_edges=((upstream, downstream),),
        canal=None,
        span_m=100.0 if role is RoutingRole.TRANSPORT else None,
        geometry_status=(
            RoutingGeometryStatus.SURVEYED
            if role is RoutingRole.TRANSPORT
            else RoutingGeometryStatus.NOT_APPLICABLE
        ),
        located_at_km=None,
    )


def _topology(edges, roles=None):
    roles = roles or {}
    return build_routing_topology(
        tuple(
            _routing_element(*edge, role=roles.get(edge, RoutingRole.TRANSPORT))
            for edge in edges
        )
    )


def _response(
    upstream: str,
    downstream: str,
    *,
    member: ResponseMember = ResponseMember.NOMINAL,
    delay_seconds: float = DT_S,
    capacity_m3s: float = 20.0,
    loss_fraction: float = 0.0,
) -> ReachResponse:
    return ReachResponse(
        model_release_id="engineering-prior-2569-v1",
        reach_id=_reach_id(upstream, downstream),
        member=member,
        delay_seconds=delay_seconds,
        loss_fraction=loss_fraction,
        dispersion_seconds=0.0,
        capacity_m3s=capacity_m3s,
        minimum_timestep_seconds=DT_S,
        maximum_timestep_seconds=DT_S,
    )


def _states(responses: tuple[ReachResponse, ...]) -> tuple[ReachState, ...]:
    return tuple(
        ReachState(response.model_release_id, response.reach_id, response.member)
        for response in responses
    )


def _simulate(
    edges,
    responses: tuple[ReachResponse, ...],
    *,
    roles=None,
    events: tuple[GateFlowEvent, ...],
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...] = (),
    withdrawal_capacity=None,
    requirements: tuple[SectionRequirement, ...] = (),
    allocations: tuple[BranchAllocation, ...] = (),
    steps: int = 3,
):
    topology = edges if hasattr(edges, "elements") else _topology(edges, roles)
    if withdrawal_capacity is None:
        withdrawal_capacity = {
            element.downstream_node_id: None
            for element in topology.elements
            if element.role is RoutingRole.WITHDRAWAL_STRUCTURE
        }
    return simulate_network_timeline(
        topology,
        responses,
        _states(responses),
        events,
        withdrawal_events,
        withdrawal_capacity,
        requirements,
        allocations,
        START,
        START + timedelta(seconds=steps * DT_S),
        DT_S,
    )


def _withdrawal_event(
    structure_id: str,
    effective_at,
    planned_flow_m3s: float,
    purpose: str = "ecological_release",
) -> OperatorWithdrawalEvent:
    return OperatorWithdrawalEvent(
        structure_id=structure_id,
        effective_at=effective_at,
        planned_flow_m3s=planned_flow_m3s,
        purpose=purpose,
    )


WASTE_WAY_LIKE_EDGES = (
    ("S", "G1"),
    ("G1", "J(TEST,0+100)"),
    ("J(TEST,0+100)", "W"),
    ("J(TEST,0+100)", "G2"),
)
WASTE_WAY_LIKE_ROLES = {
    ("S", "G1"): RoutingRole.BOUNDARY,
    ("J(TEST,0+100)", "W"): RoutingRole.WITHDRAWAL_STRUCTURE,
}


class TestRouteGateEvents:
    def test_routes_piecewise_constant_events_across_multiple_days(self):
        day = timedelta(days=1)
        steps = route_gate_events(
            (
                GateFlowEvent("S", START, 2.0),
                GateFlowEvent("S", START + day, 1.0),
                GateFlowEvent("S", START + 2 * day, 0.0),
            ),
            START,
            START + 3 * day,
            day.total_seconds(),
        )

        assert tuple(step.node_flows_m3s for step in steps) == (
            (("S", 2.0),),
            (("S", 1.0),),
            (("S", 0.0),),
        )

    def test_duplicate_node_event_at_one_instant_fails_closed(self):
        event = GateFlowEvent("S", START, 2.0)
        with pytest.raises(NetworkTransientError, match="duplicate"):
            route_gate_events((event, event), START, START + timedelta(minutes=1), DT_S)


class TestSimulateNetworkTimeline:
    def test_simulation_routes_branch_arrivals_causally(self):
        edges = (("S", "A"), ("A", "B"), ("A", "C"))
        responses = tuple(_response(*edge) for edge in edges)
        timeline = _simulate(
            edges,
            responses,
            events=(
                GateFlowEvent("S", START, 4.0),
                GateFlowEvent("S", START + timedelta(seconds=DT_S), 0.0),
            ),
            allocations=(
                BranchAllocation("A", "B", 0.5),
                BranchAllocation("A", "C", 0.5),
            ),
        )

        branch_outflows = tuple(
            tuple(point.outflow_m3s for point in step.reaches[1:])
            for step in timeline.steps
        )
        assert branch_outflows == ((0.0, 0.0), (0.0, 0.0), (2.0, 2.0))
        assert timeline.mass_balance == NetworkMassBalanceAudit(
            initial_in_transit_m3=0.0,
            boundary_inflow_m3=240.0,
            delivered_m3=0.0,
            withdrawn_m3=0.0,
            declared_loss_m3=0.0,
            terminal_outflow_m3=240.0,
            final_in_transit_m3=0.0,
            balance_error_m3=0.0,
        )

    def test_network_audit_preserves_declared_loss_without_hidden_volume(self):
        edges = (("S", "A"),)
        responses = (_response("S", "A", delay_seconds=0.0, loss_fraction=0.25),)
        timeline = _simulate(
            edges,
            responses,
            events=(GateFlowEvent("S", START, 2.0),),
            steps=1,
        )

        assert timeline.mass_balance == NetworkMassBalanceAudit(
            initial_in_transit_m3=0.0,
            boundary_inflow_m3=120.0,
            delivered_m3=0.0,
            withdrawn_m3=0.0,
            declared_loss_m3=30.0,
            terminal_outflow_m3=90.0,
            final_in_transit_m3=0.0,
            balance_error_m3=0.0,
        )

    def test_overlapping_section_obligations_are_allocated_without_double_counting(
        self,
    ):
        edges = (("S", "A"), ("A", "B"))
        responses = tuple(_response(*edge, delay_seconds=0.0) for edge in edges)
        requirements = tuple(
            SectionRequirement(
                requirement_id=f"requirement-{index}",
                section_id=f"section-{index}",
                delivery_node_id="A",
                window_start=START,
                window_end=START + timedelta(hours=1),
                required_volume_m3=60.0,
                maximum_delivery_m3s=1.0,
            )
            for index in (1, 2)
        )
        timeline = _simulate(
            edges,
            responses,
            events=(GateFlowEvent("S", START, 3.0),),
            requirements=requirements,
            steps=1,
        )

        assert tuple(
            (state.requirement_id, state.predicted_delivered_m3, state.status)
            for state in timeline.final_fulfillment
        ) == (
            (
                "requirement-1",
                60.0,
                PredictedFulfillmentStatus.PREDICTED_FULFILLED,
            ),
            (
                "requirement-2",
                60.0,
                PredictedFulfillmentStatus.PREDICTED_FULFILLED,
            ),
        )
        assert timeline.mass_balance.delivered_m3 == 120.0
        assert timeline.mass_balance.terminal_outflow_m3 == 60.0

    def test_missing_explicit_branch_allocation_fails_closed(self):
        edges = (("S", "A"), ("A", "B"), ("A", "C"))
        responses = tuple(_response(*edge) for edge in edges)

        with pytest.raises(NetworkTransientError, match="branch allocation"):
            _simulate(
                edges,
                responses,
                events=(GateFlowEvent("S", START, 1.0),),
            )

    def test_branch_allocation_must_conserve_the_entire_available_flow(self):
        edges = (("S", "A"), ("A", "B"), ("A", "C"))
        responses = tuple(_response(*edge) for edge in edges)

        with pytest.raises(NetworkTransientError, match="sum to 1"):
            _simulate(
                edges,
                responses,
                events=(GateFlowEvent("S", START, 1.0),),
                allocations=(
                    BranchAllocation("A", "B", 0.4),
                    BranchAllocation("A", "C", 0.5),
                ),
            )

    def test_response_coverage_must_match_every_network_reach(self):
        edges = (("S", "A"), ("A", "B"))
        responses = (_response("S", "A"),)

        with pytest.raises(NetworkTransientError, match="coverage"):
            _simulate(
                edges,
                responses,
                events=(GateFlowEvent("S", START, 1.0),),
            )

    def test_canonical_timeline_has_complete_42_transport_coverage(self):
        network = json.loads(CANONICAL_NETWORK.read_text(encoding="utf-8"))
        coverage = json.loads(
            (CONFIG_DIR / "geometry_coverage.json").read_text(encoding="utf-8")
        )
        canal_geometry = json.loads(
            (CONFIG_DIR / "canal_geometry.json").read_text(encoding="utf-8")
        )
        topology = derive_routing_topology(network, coverage, canal_geometry)
        transport_edges = tuple(
            (element.upstream_node_id, element.downstream_node_id)
            for element in topology.elements
            if element.role is RoutingRole.TRANSPORT
        )
        responses = tuple(
            _response(*edge, delay_seconds=0.0, capacity_m3s=100.0)
            for edge in transport_edges
        )
        allocation_edges = tuple(
            (element.upstream_node_id, element.downstream_node_id)
            for element in topology.elements
            if element.role is not RoutingRole.WITHDRAWAL_STRUCTURE
        )
        child_counts = {
            node: sum(1 for upstream, _ in allocation_edges if upstream == node)
            for node in {upstream for upstream, _ in allocation_edges}
        }
        allocations = tuple(
            BranchAllocation(upstream, downstream, 1.0 / child_counts[upstream])
            for upstream, downstream in allocation_edges
            if child_counts[upstream] > 1
        )
        timeline = _simulate(
            topology,
            responses,
            events=(GateFlowEvent("S", START, 1.0),),
            allocations=allocations,
            steps=1,
        )

        assert (
            len(timeline.final_reach_states),
            {state.reach_id for state in timeline.final_reach_states},
            timeline.mass_balance.balance_error_m3,
        ) == (42, set(topology.transport_reach_ids()), pytest.approx(0.0))

    def test_requirement_at_the_virtual_junction_fails_closed(self):
        edges = (("S", "A"), ("A", "B"))
        roles = {("S", "A"): RoutingRole.BOUNDARY}
        elements = tuple(
            _routing_element(*edge, role=roles.get(edge, RoutingRole.TRANSPORT))
            for edge in edges
        )
        junction_element = RoutingElement(
            element_id="C_B_J(TEST,0+100)",
            upstream_node_id="B",
            downstream_node_id="J(TEST,0+100)",
            role=RoutingRole.TRANSPORT,
            canonical_edges=(("B", "C"),),
            canal=None,
            span_m=100.0,
            geometry_status=RoutingGeometryStatus.SURVEYED,
            located_at_km=None,
        )
        tail_element = RoutingElement(
            element_id="C_J(TEST,0+100)_C",
            upstream_node_id="J(TEST,0+100)",
            downstream_node_id="C",
            role=RoutingRole.TRANSPORT,
            canonical_edges=(("B", "C"),),
            canal=None,
            span_m=100.0,
            geometry_status=RoutingGeometryStatus.SURVEYED,
            located_at_km=None,
        )
        topology = build_routing_topology(elements + (junction_element, tail_element))
        responses = tuple(
            _response(element.upstream_node_id, element.downstream_node_id)
            for element in topology.elements
            if element.role is RoutingRole.TRANSPORT
        )
        requirement = SectionRequirement(
            requirement_id="requirement-1",
            section_id="section-1",
            delivery_node_id="J(TEST,0+100)",
            window_start=START,
            window_end=START + timedelta(hours=1),
            required_volume_m3=60.0,
            maximum_delivery_m3s=1.0,
        )

        with pytest.raises(NetworkTransientError, match="canal gate"):
            _simulate(
                topology,
                responses,
                events=(GateFlowEvent("S", START, 1.0),),
                requirements=(requirement,),
            )

    def test_nontransport_elements_pass_through_without_reach_responses(self):
        edges = (("S", "A"), ("A", "B"))
        roles = {("S", "A"): RoutingRole.BOUNDARY}
        responses = (_response("A", "B", delay_seconds=0.0),)

        timeline = _simulate(
            edges,
            responses,
            roles=roles,
            events=(GateFlowEvent("S", START, 2.0),),
            steps=1,
        )

        assert tuple(
            point.reach_id for point in timeline.steps[0].reaches
        ) == ("C_A_B",)
        assert timeline.steps[0].reaches[0].inflow_m3s == 2.0
        assert timeline.steps[0].terminal_outflow_m3 == 120.0
        assert timeline.mass_balance.balance_error_m3 == pytest.approx(0.0)

    def test_instantaneous_elements_preserve_exact_network_mass_balance(self):
        edges = (("S", "A"), ("A", "W"), ("A", "B"), ("B", "C"))
        roles = {
            ("S", "A"): RoutingRole.BOUNDARY,
            ("A", "W"): RoutingRole.WITHDRAWAL_STRUCTURE,
            ("A", "B"): RoutingRole.BRANCH_STRUCTURE,
        }
        responses = (_response("B", "C", delay_seconds=0.0, loss_fraction=0.25),)

        timeline = _simulate(
            edges,
            responses,
            roles=roles,
            events=(GateFlowEvent("S", START, 4.0),),
            withdrawal_events=(_withdrawal_event("W", START, 1.0),),
            steps=1,
        )

        assert timeline.mass_balance == NetworkMassBalanceAudit(
            initial_in_transit_m3=0.0,
            boundary_inflow_m3=240.0,
            delivered_m3=0.0,
            withdrawn_m3=60.0,
            declared_loss_m3=45.0,
            terminal_outflow_m3=135.0,
            final_in_transit_m3=0.0,
            balance_error_m3=0.0,
        )

    def test_no_event_means_zero_withdrawal(self):
        edges = (("S", "A"), ("A", "W"), ("A", "B"), ("B", "C"))
        roles = {
            ("S", "A"): RoutingRole.BOUNDARY,
            ("A", "W"): RoutingRole.WITHDRAWAL_STRUCTURE,
            ("A", "B"): RoutingRole.BRANCH_STRUCTURE,
        }
        responses = (_response("B", "C", delay_seconds=0.0),)

        timeline = _simulate(
            edges,
            responses,
            roles=roles,
            events=(GateFlowEvent("S", START, 2.0),),
            steps=1,
        )

        step = timeline.steps[0]
        assert tuple(
            (point.structure_id, point.planned_flow_m3s, point.predicted_withdrawal_m3s)
            for point in step.withdrawals
        ) == (("W", 0.0, 0.0),)
        assert timeline.mass_balance.withdrawn_m3 == 0.0
        assert timeline.mass_balance.terminal_outflow_m3 == 120.0

    def test_waste_way_event_withdraws_only_after_flume_arrival(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=DT_S),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        timeline = _simulate(
            WASTE_WAY_LIKE_EDGES,
            responses,
            roles=WASTE_WAY_LIKE_ROLES,
            events=(GateFlowEvent("S", START, 2.0),),
            withdrawal_events=(_withdrawal_event("W", START, 1.0),),
            steps=2,
        )

        first, second = timeline.steps
        assert tuple(
            (point.predicted_withdrawal_m3s, point.shortfall_m3s)
            for point in first.withdrawals
        ) == ((0.0, 1.0),)
        assert tuple(
            (point.predicted_withdrawal_m3s, point.shortfall_m3s)
            for point in second.withdrawals
        ) == ((1.0, 0.0),)
        assert timeline.mass_balance.withdrawn_m3 == 60.0
        assert timeline.mass_balance.balance_error_m3 == pytest.approx(0.0)

    def test_waste_way_event_does_not_change_rmc_source_split_before_lmc_junction(
        self,
    ):
        edges = (
            ("S", "G1"),
            ("G1", "R"),
            ("G1", "J(TEST,0+100)"),
            ("J(TEST,0+100)", "W"),
            ("J(TEST,0+100)", "G2"),
        )
        roles = {
            ("S", "G1"): RoutingRole.BOUNDARY,
            ("G1", "R"): RoutingRole.BRANCH_STRUCTURE,
            ("J(TEST,0+100)", "W"): RoutingRole.WITHDRAWAL_STRUCTURE,
        }
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )
        arguments = {
            "roles": roles,
            "events": (GateFlowEvent("S", START, 4.0),),
            "allocations": (
                BranchAllocation("G1", "R", 0.5),
                BranchAllocation("G1", "J(TEST,0+100)", 0.5),
            ),
            "steps": 1,
        }

        without_event = _simulate(edges, responses, **arguments)
        with_event = _simulate(
            edges,
            responses,
            withdrawal_events=(_withdrawal_event("W", START, 1.0),),
            **arguments,
        )

        def flume_inflow(timeline):
            return timeline.steps[0].reaches[0].inflow_m3s

        assert flume_inflow(with_event) == flume_inflow(without_event) == 2.0
        assert with_event.mass_balance.withdrawn_m3 == 60.0
        assert without_event.mass_balance.withdrawn_m3 == 0.0

    def test_withdrawal_shortfall_is_explicit_and_mass_is_conserved(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        timeline = _simulate(
            WASTE_WAY_LIKE_EDGES,
            responses,
            roles=WASTE_WAY_LIKE_ROLES,
            events=(GateFlowEvent("S", START, 0.5),),
            withdrawal_events=(_withdrawal_event("W", START, 2.0),),
            steps=1,
        )

        point = timeline.steps[0].withdrawals[0]
        assert (
            point.planned_flow_m3s,
            point.hydraulically_available_flow_m3s,
            point.predicted_withdrawal_m3s,
            point.shortfall_m3s,
        ) == (2.0, 0.5, 0.5, 1.5)
        assert timeline.mass_balance.withdrawn_m3 == 30.0
        assert timeline.mass_balance.terminal_outflow_m3 == 0.0
        assert timeline.mass_balance.balance_error_m3 == pytest.approx(0.0)

    def test_withdrawal_shortfall_survives_irrational_flow_volume_round_trip(self):
        """The reviewer's live repro: a shortfall clamp at an irrational
        availability must not leave a negative float residue that crashes
        the downstream reach validator."""
        requirement = SectionRequirement(
            requirement_id="requirement-1",
            section_id="section-1",
            delivery_node_id="G1",
            window_start=START,
            window_end=START + timedelta(hours=1),
            required_volume_m3=1e9,
            maximum_delivery_m3s=1.5840213564352403,
        )

        topology = _topology(
            (("S", "G1"), ("G1", "W"), ("G1", "J(TEST,0+100)")),
            {
                ("S", "G1"): RoutingRole.BOUNDARY,
                ("G1", "W"): RoutingRole.WITHDRAWAL_STRUCTURE,
            },
        )
        timestep_seconds = 1800.0
        responses = (
            ReachResponse(
                model_release_id="engineering-prior-2569-v1",
                reach_id="C_G1_J(TEST,0+100)",
                member=ResponseMember.NOMINAL,
                delay_seconds=0.0,
                loss_fraction=0.0,
                dispersion_seconds=0.0,
                capacity_m3s=100.0,
                minimum_timestep_seconds=timestep_seconds,
                maximum_timestep_seconds=timestep_seconds,
            ),
        )
        timeline = simulate_network_timeline(
            topology,
            responses,
            _states(responses),
            (GateFlowEvent("S", START, 2.1283507538211444),),
            (_withdrawal_event("W", START, 5.0),),
            {"W": None},
            (requirement,),
            (),
            START,
            START + timedelta(seconds=timestep_seconds),
            timestep_seconds,
        )

        point = timeline.steps[0].withdrawals[0]
        assert point.predicted_withdrawal_m3s >= 0.0
        assert point.shortfall_m3s >= 0.0
        assert timeline.steps[0].terminal_outflow_m3 >= 0.0
        assert timeline.mass_balance.balance_error_m3 == pytest.approx(
            0.0, abs=1e-8
        )

    def test_requirement_at_a_withdrawal_structure_fails_closed(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )
        requirement = SectionRequirement(
            requirement_id="requirement-1",
            section_id="section-1",
            delivery_node_id="W",
            window_start=START,
            window_end=START + timedelta(hours=1),
            required_volume_m3=10.0,
            maximum_delivery_m3s=1.0,
        )

        with pytest.raises(NetworkTransientError, match="withdrawal structure"):
            _simulate(
                WASTE_WAY_LIKE_EDGES,
                responses,
                roles=WASTE_WAY_LIKE_ROLES,
                events=(GateFlowEvent("S", START, 2.0),),
                requirements=(requirement,),
                steps=1,
            )

    def test_missing_structure_qmax_reports_unavailable_capacity_check(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        timeline = _simulate(
            WASTE_WAY_LIKE_EDGES,
            responses,
            roles=WASTE_WAY_LIKE_ROLES,
            events=(GateFlowEvent("S", START, 2.0),),
            withdrawal_events=(_withdrawal_event("W", START, 1.0),),
            steps=1,
        )

        assert (
            timeline.steps[0].withdrawals[0].capacity_check_status
            is WithdrawalCapacityCheckStatus.UNAVAILABLE
        )

    def test_authoritative_qmax_limits_predicted_withdrawal(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        timeline = _simulate(
            WASTE_WAY_LIKE_EDGES,
            responses,
            roles=WASTE_WAY_LIKE_ROLES,
            events=(GateFlowEvent("S", START, 2.0),),
            withdrawal_events=(_withdrawal_event("W", START, 1.5),),
            withdrawal_capacity={"W": 1.0},
            steps=1,
        )

        point = timeline.steps[0].withdrawals[0]
        assert (
            point.predicted_withdrawal_m3s,
            point.shortfall_m3s,
            point.capacity_check_status,
        ) == (1.0, 0.5, WithdrawalCapacityCheckStatus.EXCEEDS_CAPACITY)

    def test_withdrawal_is_not_declared_loss_or_section_delivery(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )
        requirement = SectionRequirement(
            requirement_id="requirement-1",
            section_id="section-1",
            delivery_node_id="G1",
            window_start=START,
            window_end=START + timedelta(hours=1),
            required_volume_m3=30.0,
            maximum_delivery_m3s=0.5,
        )

        timeline = _simulate(
            WASTE_WAY_LIKE_EDGES,
            responses,
            roles=WASTE_WAY_LIKE_ROLES,
            events=(GateFlowEvent("S", START, 2.0),),
            withdrawal_events=(_withdrawal_event("W", START, 1.0),),
            requirements=(requirement,),
            steps=1,
        )

        assert timeline.mass_balance.withdrawn_m3 == 60.0
        assert timeline.mass_balance.delivered_m3 == 30.0
        assert timeline.mass_balance.declared_loss_m3 == 0.0
        assert timeline.final_fulfillment[0].predicted_delivered_m3 == 30.0
        assert timeline.mass_balance.balance_error_m3 == pytest.approx(0.0)

    def test_unknown_or_nonwithdrawal_structure_event_fails_closed(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        for structure_id in ("G2", "NOWHERE"):
            with pytest.raises(NetworkTransientError, match="withdrawal structure"):
                _simulate(
                    WASTE_WAY_LIKE_EDGES,
                    responses,
                    roles=WASTE_WAY_LIKE_ROLES,
                    events=(GateFlowEvent("S", START, 2.0),),
                    withdrawal_events=(
                        _withdrawal_event(structure_id, START, 1.0),
                    ),
                    steps=1,
                )

    def test_overlapping_event_for_same_structure_and_instant_is_rejected(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        with pytest.raises(NetworkTransientError, match="duplicate"):
            _simulate(
                WASTE_WAY_LIKE_EDGES,
                responses,
                roles=WASTE_WAY_LIKE_ROLES,
                events=(GateFlowEvent("S", START, 2.0),),
                withdrawal_events=(
                    _withdrawal_event("W", START, 1.0),
                    _withdrawal_event("W", START, 0.5),
                ),
                steps=1,
            )

    def test_withdrawal_event_flow_is_held_until_replaced(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        timeline = _simulate(
            WASTE_WAY_LIKE_EDGES,
            responses,
            roles=WASTE_WAY_LIKE_ROLES,
            events=(GateFlowEvent("S", START, 2.0),),
            withdrawal_events=(
                _withdrawal_event("W", START, 1.0),
                _withdrawal_event(
                    "W", START + timedelta(seconds=2 * DT_S), 0.0
                ),
            ),
            steps=3,
        )

        assert tuple(
            step.withdrawals[0].predicted_withdrawal_m3s
            for step in timeline.steps
        ) == (1.0, 1.0, 0.0)
        assert timeline.mass_balance.withdrawn_m3 == 120.0

    def test_branch_allocations_exclude_withdrawal_structure_edges(self):
        responses = (
            _response("G1", "J(TEST,0+100)", delay_seconds=0.0),
            _response("J(TEST,0+100)", "G2", delay_seconds=0.0),
        )

        with pytest.raises(NetworkTransientError, match="unknown branch edge"):
            _simulate(
                WASTE_WAY_LIKE_EDGES,
                responses,
                roles=WASTE_WAY_LIKE_ROLES,
                events=(GateFlowEvent("S", START, 2.0),),
                allocations=(
                    BranchAllocation("J(TEST,0+100)", "W", 0.5),
                    BranchAllocation("J(TEST,0+100)", "G2", 0.5),
                ),
                steps=1,
            )

    def test_transport_states_cover_only_transport_elements(self):
        edges = (("S", "A"), ("A", "B"))
        roles = {("S", "A"): RoutingRole.BOUNDARY}
        responses = (_response("A", "B"),)

        timeline = _simulate(
            edges,
            responses,
            roles=roles,
            events=(GateFlowEvent("S", START, 1.0),),
            steps=1,
        )

        assert tuple(
            state.reach_id for state in timeline.final_reach_states
        ) == ("C_A_B",)

    def test_unknown_nontransport_response_fails_closed(self):
        edges = (("S", "A"), ("A", "B"))
        roles = {("S", "A"): RoutingRole.BOUNDARY}
        responses = (
            _response("A", "B"),
            _response("S", "A"),
        )

        with pytest.raises(NetworkTransientError, match="coverage"):
            _simulate(
                edges,
                responses,
                roles=roles,
                events=(GateFlowEvent("S", START, 1.0),),
            )

    def test_deterministic_replay_returns_the_same_immutable_timeline(self):
        edges = (("S", "A"),)
        responses = (_response("S", "A"),)
        arguments = {
            "events": (GateFlowEvent("S", START, 1.0),),
            "steps": 2,
        }

        assert _simulate(edges, responses, **arguments) == _simulate(
            edges, responses, **arguments
        )

    def test_response_members_remain_distinct_prediction_scenarios(self):
        edges = (("S", "A"),)
        nominal = _response("S", "A", delay_seconds=0.0)
        lower = replace(nominal, member=ResponseMember.LOWER, delay_seconds=DT_S)

        nominal_timeline = _simulate(
            edges,
            (nominal,),
            events=(GateFlowEvent("S", START, 1.0),),
            steps=1,
        )
        lower_timeline = _simulate(
            edges,
            (lower,),
            events=(GateFlowEvent("S", START, 1.0),),
            steps=1,
        )

        assert (
            nominal_timeline.member,
            nominal_timeline.steps[0].terminal_outflow_m3,
            lower_timeline.member,
            lower_timeline.steps[0].terminal_outflow_m3,
        ) == (ResponseMember.NOMINAL, 60.0, ResponseMember.LOWER, 0.0)

    def test_internal_gate_event_cannot_create_unmodelled_water(self):
        edges = (("S", "A"), ("A", "B"))
        responses = tuple(_response(*edge) for edge in edges)

        with pytest.raises(NetworkTransientError, match="root"):
            _simulate(
                edges,
                responses,
                events=(GateFlowEvent("A", START, 1.0),),
            )

    @settings(max_examples=60)
    @given(
        source_flow_m3s=st.floats(min_value=0.0, max_value=10.0),
        first_branch_fraction=st.floats(min_value=0.0, max_value=1.0),
        delay_steps=st.integers(min_value=0, max_value=3),
        loss_fraction=st.floats(min_value=0.0, max_value=0.5),
    )
    def test_random_branch_timeline_preserves_nonnegative_network_mass(
        self, source_flow_m3s, first_branch_fraction, delay_steps, loss_fraction
    ):
        edges = (("S", "A"), ("A", "B"), ("A", "C"))
        responses = tuple(
            _response(
                *edge,
                delay_seconds=delay_steps * DT_S,
                loss_fraction=loss_fraction,
            )
            for edge in edges
        )
        timeline = _simulate(
            edges,
            responses,
            events=(
                GateFlowEvent("S", START, source_flow_m3s),
                GateFlowEvent("S", START + timedelta(seconds=DT_S), 0.0),
            ),
            allocations=(
                BranchAllocation("A", "B", first_branch_fraction),
                BranchAllocation("A", "C", 1.0 - first_branch_fraction),
            ),
            steps=max(2, 2 * delay_steps + 1),
        )

        assert timeline.mass_balance.balance_error_m3 == pytest.approx(0.0, abs=1e-8)
        assert all(
            point.in_transit_volume_m3 >= 0.0 and point.outflow_m3s >= 0.0
            for step in timeline.steps
            for point in step.reaches
        )


EXCLUSION_EDGES = (
    ("S", "G1"),
    ("G1", "J(TEST,0+100)"),
    ("J(TEST,0+100)", "W"),
    ("J(TEST,0+100)", "G2"),
    ("G1", "R1"),
    ("R1", "R2"),
)
EXCLUSION_ROLES = {
    ("S", "G1"): RoutingRole.BOUNDARY,
    ("J(TEST,0+100)", "W"): RoutingRole.WITHDRAWAL_STRUCTURE,
    ("G1", "R1"): RoutingRole.BRANCH_STRUCTURE,
}
FLUME_LIKE_REACH = "C_G1_J(TEST,0+100)"


def _exclusion_case(
    *,
    flume_fraction: float = 0.0,
    requirements: tuple[SectionRequirement, ...] = (),
    withdrawal_events: tuple[OperatorWithdrawalEvent, ...] = (),
    extra_states: tuple[ReachState, ...] = (),
    unavailable: frozenset[str] = frozenset({FLUME_LIKE_REACH}),
    flow_m3s: float = 1.0,
):
    topology = _topology(EXCLUSION_EDGES, EXCLUSION_ROLES)
    responses = (
        _response("J(TEST,0+100)", "G2"),
        _response("R1", "R2"),
    )
    return simulate_network_timeline(
        topology,
        responses,
        _states(responses) + extra_states,
        (GateFlowEvent("S", START, flow_m3s),),
        withdrawal_events,
        {"W": None},
        requirements,
        (
            BranchAllocation("G1", "J(TEST,0+100)", flume_fraction),
            BranchAllocation("G1", "R1", 1.0 - flume_fraction),
        ),
        START,
        START + timedelta(seconds=3 * DT_S),
        DT_S,
        unavailable_transport_reach_ids=unavailable,
    )


class TestUnavailableTransportCoverage:
    def test_provably_dry_unavailable_transport_needs_no_synthetic_response(self):
        timeline = _exclusion_case()

        assert timeline.excluded_transport_reach_ids == (FLUME_LIKE_REACH,)
        stepped_reaches = {
            point.reach_id
            for step in timeline.steps
            for point in step.reaches
        }
        assert stepped_reaches == {"C_J(TEST,0+100)_G2", "C_R1_R2"}
        assert {state.reach_id for state in timeline.final_reach_states} == (
            stepped_reaches
        )
        # All water goes down the covered branch; the sweep stays conservative.
        assert timeline.mass_balance.boundary_inflow_m3 == pytest.approx(
            3 * DT_S * 1.0
        )

    def test_active_unavailable_transport_fails_closed(self):
        with pytest.raises(NetworkTransientError, match=r"C_G1_J\(TEST,0\+100\)"):
            _exclusion_case(flume_fraction=0.5)

    def test_unavailable_subtree_rejects_requirement_dependency(self):
        requirement = SectionRequirement(
            requirement_id="REQ-BELOW-FLUME",
            section_id="SEC-1",
            delivery_node_id="G2",
            window_start=START,
            window_end=START + timedelta(seconds=3 * DT_S),
            required_volume_m3=10.0,
            maximum_delivery_m3s=1.0,
        )
        with pytest.raises(NetworkTransientError, match=r"REQ-BELOW-FLUME"):
            _exclusion_case(requirements=(requirement,))

    def test_unavailable_subtree_rejects_withdrawal_event_dependency(self):
        with pytest.raises(
            NetworkTransientError, match=r"C_G1_J\(TEST,0\+100\)"
        ):
            _exclusion_case(
                withdrawal_events=(_withdrawal_event("W", START, 0.2),)
            )

    def test_unavailable_reach_must_not_carry_initial_state(self):
        stray = ReachState(
            "engineering-prior-2569-v1", FLUME_LIKE_REACH, ResponseMember.NOMINAL
        )
        with pytest.raises(
            NetworkTransientError, match="initial state coverage"
        ):
            _exclusion_case(extra_states=(stray,))

    def test_unknown_unavailable_reach_id_rejected(self):
        with pytest.raises(
            NetworkTransientError, match="not transport reaches"
        ):
            _exclusion_case(
                unavailable=frozenset({FLUME_LIKE_REACH, "C_X_Y"})
            )

    def test_dry_requirement_on_covered_path_is_allowed(self):
        # R-side gets zero water yet its path crosses only COVERED reaches:
        # the prediction must run and honestly report nothing delivered.
        topology = _topology(EXCLUSION_EDGES, EXCLUSION_ROLES)
        responses = (
            _response("G1", "J(TEST,0+100)"),
            _response("J(TEST,0+100)", "G2"),
            _response("R1", "R2"),
        )
        requirement = SectionRequirement(
            requirement_id="REQ-DRY-COVERED",
            section_id="SEC-1",
            delivery_node_id="R2",
            window_start=START,
            window_end=START + timedelta(seconds=3 * DT_S),
            required_volume_m3=10.0,
            maximum_delivery_m3s=1.0,
        )
        timeline = simulate_network_timeline(
            topology,
            responses,
            _states(responses),
            (GateFlowEvent("S", START, 1.0),),
            (),
            {"W": None},
            (requirement,),
            (
                BranchAllocation("G1", "J(TEST,0+100)", 1.0),
                BranchAllocation("G1", "R1", 0.0),
            ),
            START,
            START + timedelta(seconds=3 * DT_S),
            DT_S,
        )
        state = timeline.final_fulfillment[0]
        assert (state.predicted_delivered_m3, state.status) == (
            0.0,
            PredictedFulfillmentStatus.PENDING,
        )

    def test_capacity_exceedance_raises_structured_network_error(self):
        from core.network_transient import NetworkReachCapacityExceededError

        responses = (_response("S", "A", capacity_m3s=0.5),)
        with pytest.raises(NetworkReachCapacityExceededError) as excinfo:
            simulate_network_timeline(
                _topology((("S", "A"),)),
                responses,
                _states(responses),
                (GateFlowEvent("S", START, 1.0),),
                (),
                {},
                (),
                (),
                START,
                START + timedelta(seconds=DT_S),
                DT_S,
            )
        error = excinfo.value
        assert (
            error.reach_id,
            error.kind,
            error.interval_start,
            error.interval_end,
        ) == ("C_S_A", "inflow", START, START + timedelta(seconds=DT_S))
        assert (error.attempted_flow_m3s, error.capacity_m3s) == (1.0, 0.5)

    def test_wet_initial_state_below_excluded_reach_fails_closed(self):
        # A mass-balanced wet state downstream of the excluded flume would
        # fabricate water the unmodeled reach can never have delivered.
        wet_below = ReachState(
            "engineering-prior-2569-v1",
            "C_J(TEST,0+100)_G2",
            ResponseMember.NOMINAL,
            transit_volumes=(TransitVolume(10.0, 0.0, 60.0),),
            cumulative_inflow_m3=10.0,
        )
        topology = _topology(EXCLUSION_EDGES, EXCLUSION_ROLES)
        responses = (
            _response("J(TEST,0+100)", "G2"),
            _response("R1", "R2"),
        )
        states = tuple(
            wet_below if state.reach_id == "C_J(TEST,0+100)_G2" else state
            for state in _states(responses)
        )
        with pytest.raises(NetworkTransientError, match="must be dry"):
            simulate_network_timeline(
                topology,
                responses,
                states,
                (GateFlowEvent("S", START, 1.0),),
                (),
                {"W": None},
                (),
                (
                    BranchAllocation("G1", "J(TEST,0+100)", 0.0),
                    BranchAllocation("G1", "R1", 1.0),
                ),
                START,
                START + timedelta(seconds=3 * DT_S),
                DT_S,
                unavailable_transport_reach_ids=frozenset({FLUME_LIKE_REACH}),
            )

    def test_warm_upstream_state_defeating_zero_allocation_fails_at_validation(self):
        # Water already in transit inside a covered reach drains regardless of
        # the branch fractions below the root — the static proof must treat it
        # as a source, not discover the leak mid-simulation.
        edges = (
            ("S", "G1"),
            ("G1", "A"),
            ("A", "B"),
            ("G1", "R1"),
            ("R1", "R2"),
        )
        roles = {
            ("S", "G1"): RoutingRole.BOUNDARY,
            ("G1", "R1"): RoutingRole.BRANCH_STRUCTURE,
        }
        topology = _topology(edges, roles)
        responses = (
            _response("G1", "A"),
            _response("R1", "R2"),
        )
        warm = ReachState(
            "engineering-prior-2569-v1",
            "C_G1_A",
            ResponseMember.NOMINAL,
            transit_volumes=(TransitVolume(10.0, 0.0, 60.0),),
            cumulative_inflow_m3=10.0,
        )
        states = tuple(
            warm if state.reach_id == "C_G1_A" else state
            for state in _states(responses)
        )
        with pytest.raises(
            NetworkTransientError, match=r"C_A_B.*would receive water"
        ):
            simulate_network_timeline(
                topology,
                responses,
                states,
                (GateFlowEvent("S", START, 0.0),),
                (),
                {},
                (),
                (
                    BranchAllocation("G1", "A", 0.0),
                    BranchAllocation("G1", "R1", 1.0),
                ),
                START,
                START + timedelta(seconds=3 * DT_S),
                DT_S,
                unavailable_transport_reach_ids=frozenset({"C_A_B"}),
            )
