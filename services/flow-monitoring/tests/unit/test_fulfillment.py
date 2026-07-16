from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings, strategies as st

from core.fulfillment import (
    ClosureProjection,
    ClosureRequirement,
    FulfillmentError,
    PredictedDeliveryState,
    PredictedFulfillmentStatus,
    TransitCommitment,
    VolumeBounds,
    advance_predicted_delivery,
    earliest_safe_closure,
    usable_in_transit_volume,
)

START = datetime(2026, 7, 16, tzinfo=timezone.utc)
NETWORK_EDGES = (("S", "A"), ("A", "B"), ("A", "C"))
REQUIREMENT = ClosureRequirement(
    requirement_id="requirement-1",
    delivery_node_id="B",
    required_volume_m3=100.0,
    approved_excess_m3=10.0,
    required_by=START + timedelta(hours=3),
)
STATE = PredictedDeliveryState(
    requirement_id=REQUIREMENT.requirement_id,
    section_id="section-1",
    required_volume_m3=REQUIREMENT.required_volume_m3,
    approved_excess_m3=REQUIREMENT.approved_excess_m3,
)


def _bounds(value: float) -> VolumeBounds:
    return VolumeBounds(value, value, value)


def _earliest_safe_closure(
    requirements: tuple[ClosureRequirement, ...],
    projections: tuple[ClosureProjection, ...],
    closing_gate_id: str = "A",
):
    return earliest_safe_closure(
        closing_gate_id, NETWORK_EDGES, requirements, projections
    )


def _commitment(
    volume: VolumeBounds,
    *,
    commitment_id: str = "commitment-1",
    requirement_id: str = REQUIREMENT.requirement_id,
    committed_at: datetime = START - timedelta(minutes=5),
    arrives_at: datetime = START + timedelta(hours=1),
) -> TransitCommitment:
    return TransitCommitment(
        commitment_id, requirement_id, committed_at, arrives_at, volume
    )


class TestAdvancePredictedDelivery:
    def test_delivery_and_tail_progress_through_predicted_only_statuses(self):
        arrival = advance_predicted_delivery(STATE, 0.0, 40.0)
        active = advance_predicted_delivery(arrival, 30.0, 35.0)
        fulfilled = advance_predicted_delivery(active, 70.0, 0.0)

        assert tuple(
            (
                state.predicted_delivered_m3,
                state.usable_in_transit_m3,
                state.status,
            )
            for state in (arrival, active, fulfilled)
        ) == (
            (0.0, 40.0, PredictedFulfillmentStatus.ARRIVAL_PREDICTED),
            (30.0, 35.0, PredictedFulfillmentStatus.DELIVERY_PREDICTED_ACTIVE),
            (100.0, 0.0, PredictedFulfillmentStatus.PREDICTED_FULFILLED),
        )

    def test_predicted_excess_is_visible_instead_of_claiming_fulfillment(self):
        result = advance_predicted_delivery(STATE, 80.0, 31.0)

        assert result.status is PredictedFulfillmentStatus.PREDICTED_EXCESS

    @pytest.mark.parametrize(
        "state,delivered_delta_m3,in_transit_m3",
        [
            (replace(STATE, requirement_id=" "), 0.0, 0.0),
            (replace(STATE, required_volume_m3=0.0), 0.0, 0.0),
            (replace(STATE, approved_excess_m3=-1.0), 0.0, 0.0),
            (STATE, -1.0, 0.0),
            (STATE, 0.0, -1.0),
            (STATE, float("nan"), 0.0),
        ],
    )
    def test_invalid_delivery_state_or_delta_fails_closed(
        self, state, delivered_delta_m3, in_transit_m3
    ):
        with pytest.raises(FulfillmentError):
            advance_predicted_delivery(state, delivered_delta_m3, in_transit_m3)

    @settings(max_examples=100)
    @given(
        delivered_deltas=st.lists(
            st.floats(min_value=0.0, max_value=10.0), min_size=1, max_size=20
        ),
        in_transit=st.floats(min_value=0.0, max_value=100.0),
    )
    def test_predicted_delivery_is_monotone_and_never_claims_observation(
        self, delivered_deltas, in_transit
    ):
        state = replace(STATE, required_volume_m3=1000.0)
        delivered = []
        for delta in delivered_deltas:
            state = advance_predicted_delivery(state, delta, in_transit)
            delivered.append(state.predicted_delivered_m3)

        assert delivered == sorted(delivered)
        assert (
            "confirmed" not in state.status.value and "actual" not in state.status.value
        )


class TestUsableInTransitVolume:
    def test_counts_only_committed_tail_arriving_after_close_and_by_deadline(self):
        commitments = (
            _commitment(VolumeBounds(50.0, 55.0, 60.0)),
            _commitment(_bounds(20.0), arrives_at=START),
            _commitment(_bounds(30.0), committed_at=START + timedelta(minutes=1)),
            _commitment(
                _bounds(40.0), arrives_at=REQUIREMENT.required_by + timedelta(seconds=1)
            ),
            _commitment(_bounds(70.0), requirement_id="requirement-2"),
        )

        assert usable_in_transit_volume(
            commitments,
            REQUIREMENT.requirement_id,
            START,
            REQUIREMENT.required_by,
        ) == VolumeBounds(50.0, 55.0, 60.0)

    def test_invalid_uncertainty_bounds_fail_closed(self):
        with pytest.raises(FulfillmentError, match="ordered"):
            usable_in_transit_volume(
                (_commitment(VolumeBounds(10.0, 9.0, 11.0)),),
                REQUIREMENT.requirement_id,
                START,
                REQUIREMENT.required_by,
            )


class TestEarliestSafeClosure:
    def test_earliest_safe_closure_counts_usable_in_transit_water(self):
        earlier = ClosureProjection(
            closes_at=START - timedelta(minutes=10),
            requirement_id=REQUIREMENT.requirement_id,
            delivered_volume_m3=_bounds(40.0),
        )
        safe_before_arrival = ClosureProjection(
            closes_at=START,
            requirement_id=REQUIREMENT.requirement_id,
            delivered_volume_m3=VolumeBounds(40.0, 45.0, 50.0),
            transit_commitments=(_commitment(VolumeBounds(60.0, 60.0, 60.0)),),
        )

        assert (
            _earliest_safe_closure((REQUIREMENT,), (safe_before_arrival, earlier))
            == START
        )

    def test_descendant_requirement_blocks_upstream_closure_until_all_are_safe(self):
        second = replace(REQUIREMENT, requirement_id="requirement-2")
        first_time = START
        second_time = START + timedelta(hours=1)
        projections = (
            ClosureProjection(first_time, REQUIREMENT.requirement_id, _bounds(100.0)),
            ClosureProjection(first_time, second.requirement_id, _bounds(90.0)),
            ClosureProjection(second_time, REQUIREMENT.requirement_id, _bounds(100.0)),
            ClosureProjection(second_time, second.requirement_id, _bounds(100.0)),
        )

        assert _earliest_safe_closure((REQUIREMENT, second), projections) == second_time

    @pytest.mark.parametrize(
        "delivered,tail",
        [
            (VolumeBounds(39.0, 45.0, 50.0), VolumeBounds(60.0, 60.0, 60.0)),
            (VolumeBounds(40.0, 45.0, 51.0), VolumeBounds(60.0, 60.0, 60.0)),
        ],
    )
    def test_uncertainty_or_overdelivery_bound_blocks_closure(self, delivered, tail):
        projection = ClosureProjection(
            START,
            REQUIREMENT.requirement_id,
            delivered,
            (_commitment(tail),),
        )

        assert _earliest_safe_closure((REQUIREMENT,), (projection,)) is None

    def test_missing_descendant_projection_fails_closed(self):
        second = replace(REQUIREMENT, requirement_id="requirement-2")
        projections = (
            ClosureProjection(START, REQUIREMENT.requirement_id, _bounds(100.0)),
        )

        with pytest.raises(FulfillmentError, match="coverage"):
            _earliest_safe_closure((REQUIREMENT, second), projections)

    def test_projection_rejects_commitment_for_another_requirement(self):
        projection = ClosureProjection(
            START,
            REQUIREMENT.requirement_id,
            _bounds(40.0),
            (_commitment(_bounds(60.0), requirement_id="requirement-2"),),
        )

        with pytest.raises(FulfillmentError, match="commitment"):
            _earliest_safe_closure((REQUIREMENT,), (projection,))

    def test_descendants_cannot_double_count_one_in_transit_commitment(self):
        second = replace(REQUIREMENT, requirement_id="requirement-2")
        projections = (
            ClosureProjection(
                START,
                REQUIREMENT.requirement_id,
                _bounds(40.0),
                (_commitment(_bounds(60.0)),),
            ),
            ClosureProjection(
                START,
                second.requirement_id,
                _bounds(40.0),
                (
                    _commitment(
                        _bounds(60.0),
                        requirement_id=second.requirement_id,
                    ),
                ),
            ),
        )

        with pytest.raises(FulfillmentError, match="duplicate commitment"):
            _earliest_safe_closure((REQUIREMENT, second), projections)

    def test_gate_closure_derives_every_descendant_requirement_from_topology(self):
        second = replace(
            REQUIREMENT,
            requirement_id="requirement-2",
            delivery_node_id="C",
        )
        projections = (
            ClosureProjection(START, REQUIREMENT.requirement_id, _bounds(100.0)),
        )

        with pytest.raises(FulfillmentError, match="coverage"):
            _earliest_safe_closure((REQUIREMENT, second), projections)

    def test_gate_closure_ignores_requirements_on_a_sibling_branch(self):
        sibling = replace(
            REQUIREMENT,
            requirement_id="requirement-2",
            delivery_node_id="C",
        )
        projection = ClosureProjection(
            START, REQUIREMENT.requirement_id, _bounds(100.0)
        )

        assert (
            _earliest_safe_closure(
                (REQUIREMENT, sibling), (projection,), closing_gate_id="B"
            )
            == START
        )

    def test_unknown_closing_gate_fails_closed(self):
        projection = ClosureProjection(
            START, REQUIREMENT.requirement_id, _bounds(100.0)
        )

        with pytest.raises(FulfillmentError, match="closing_gate_id"):
            _earliest_safe_closure(
                (REQUIREMENT,), (projection,), closing_gate_id="UNKNOWN"
            )
