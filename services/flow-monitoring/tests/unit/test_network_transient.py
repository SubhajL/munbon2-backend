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
    SectionRequirement,
    route_gate_events,
    simulate_network_timeline,
)
from core.reach_response import ReachResponse, ReachState, ResponseMember

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
DT_S = 60.0
CANONICAL_NETWORK = (
    Path(__file__).resolve().parents[2] / "src" / "config" / "network.json"
)


def _reach_id(upstream: str, downstream: str) -> str:
    return f"C_{upstream}_{downstream}"


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
    edges: tuple[tuple[str, str], ...],
    responses: tuple[ReachResponse, ...],
    *,
    events: tuple[GateFlowEvent, ...],
    requirements: tuple[SectionRequirement, ...] = (),
    allocations: tuple[BranchAllocation, ...] = (),
    steps: int = 3,
):
    return simulate_network_timeline(
        edges,
        responses,
        _states(responses),
        events,
        requirements,
        allocations,
        START,
        START + timedelta(seconds=steps * DT_S),
        DT_S,
    )


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
            0.0, 240.0, 0.0, 0.0, 240.0, 0.0, 0.0
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

    def test_canonical_timeline_has_complete_58_reach_coverage(self):
        network = json.loads(CANONICAL_NETWORK.read_text(encoding="utf-8"))
        edges = tuple(tuple(edge) for edge in network["edges"])
        responses = tuple(
            _response(*edge, delay_seconds=0.0, capacity_m3s=100.0) for edge in edges
        )
        child_counts = {
            node: sum(1 for upstream, _ in edges if upstream == node)
            for node in {upstream for upstream, _ in edges}
        }
        allocations = tuple(
            BranchAllocation(upstream, downstream, 1.0 / child_counts[upstream])
            for upstream, downstream in edges
            if child_counts[upstream] > 1
        )
        timeline = _simulate(
            edges,
            responses,
            events=(GateFlowEvent("S", START, 1.0),),
            allocations=allocations,
            steps=1,
        )

        assert (
            len(timeline.final_reach_states),
            {state.reach_id for state in timeline.final_reach_states},
            timeline.mass_balance.balance_error_m3,
        ) == (58, {response.reach_id for response in responses}, pytest.approx(0.0))

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
