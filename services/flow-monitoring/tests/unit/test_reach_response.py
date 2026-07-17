import math
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, strategies as st

import core.reach_response as reach_response_module
from core.model_release import (
    EvidenceClass,
    HydraulicModelRelease,
    ModelLineage,
    OperatingEnvelope,
    ParameterDistribution,
    ReachResponseParameters,
    SourceArtifact,
)
from core.reach_response import (
    ReachCapacityExceededError,
    ReachResponse,
    ReachResponseError,
    ReachState,
    ResponseMember,
    TransitVolume,
    reach_responses_from_model_release,
    route_reach_step,
    validate_reach_response,
)

RESPONSE = ReachResponse(
    model_release_id="engineering-prior-2569-v1",
    reach_id="C_M(0,0)_M(0,1)",
    member=ResponseMember.NOMINAL,
    delay_seconds=120.0,
    loss_fraction=0.1,
    dispersion_seconds=120.0,
    capacity_m3s=5.0,
    minimum_timestep_seconds=30.0,
    maximum_timestep_seconds=300.0,
)


def _dry_state(response: ReachResponse = RESPONSE) -> ReachState:
    return ReachState(
        model_release_id=response.model_release_id,
        reach_id=response.reach_id,
        member=response.member,
    )


def _accounted_volume_m3(state: ReachState) -> float:
    return (
        state.cumulative_outflow_m3
        + state.cumulative_withdrawal_m3
        + state.cumulative_declared_loss_m3
        + state.cumulative_operational_loss_m3
        + state.in_transit_volume_m3
    )


def _model_release() -> HydraulicModelRelease:
    source = SourceArtifact("surveyed-geometry", "rid-2569-draft", "a" * 64)
    return HydraulicModelRelease(
        schema_version=1,
        release_id="engineering-prior-2569-v1",
        generated_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
        evidence_class=EvidenceClass.ENGINEERING_PRIOR,
        commandable=False,
        lineage=ModelLineage("model-generator", "1.0.0", (source,)),
        operating_envelope=OperatingEnvelope(0.0, 5.0, 60.0, 300.0, 604800.0),
        reach_parameters=(
            ReachResponseParameters(
                reach_id="C_M(0,0)_M(0,1)",
                delay_seconds=ParameterDistribution(30.0, 60.0, 90.0),
                loss_fraction=ParameterDistribution(0.1, 0.2, 0.3),
                dispersion_seconds=ParameterDistribution(0.0, 30.0, 60.0),
                capacity_m3s=ParameterDistribution(3.0, 4.0, 5.0),
                evidence_refs=(source.source_id,),
            ),
        ),
        unavailable_reaches=(),
        content_hash="b" * 64,
    )


class TestValidateReachResponse:
    def test_valid_response_passes(self):
        validate_reach_response(RESPONSE)

    @pytest.mark.parametrize(
        "changes",
        [
            {"model_release_id": ""},
            {"reach_id": " "},
            {"member": "nominal"},
            {"delay_seconds": -1.0},
            {"delay_seconds": math.nan},
            {"loss_fraction": -0.1},
            {"loss_fraction": 1.0},
            {"dispersion_seconds": -1.0},
            {"capacity_m3s": 0.0},
            {"minimum_timestep_seconds": 0.0},
            {"maximum_timestep_seconds": 10.0},
        ],
    )
    def test_invalid_response_fails_closed(self, changes):
        with pytest.raises(ReachResponseError):
            validate_reach_response(replace(RESPONSE, **changes))


class TestReachResponsesFromModelRelease:
    def test_materializes_each_parameter_member_with_release_envelope(self):
        responses = reach_responses_from_model_release(_model_release())

        assert tuple(
            (
                response.member,
                response.delay_seconds,
                response.loss_fraction,
                response.dispersion_seconds,
                response.capacity_m3s,
                response.minimum_timestep_seconds,
                response.maximum_timestep_seconds,
            )
            for response in responses
        ) == (
            (ResponseMember.LOWER, 30.0, 0.1, 0.0, 3.0, 60.0, 300.0),
            (ResponseMember.NOMINAL, 60.0, 0.2, 30.0, 4.0, 60.0, 300.0),
            (ResponseMember.UPPER, 90.0, 0.3, 60.0, 5.0, 60.0, 300.0),
        )

    def test_executes_dry_zero_flow_invariant_for_every_response(self, monkeypatch):
        calls = []
        real_route_reach_step = reach_response_module.route_reach_step

        def recording_route(response, state, inflow_m3s, dt_s):
            calls.append((response.member, inflow_m3s, dt_s))
            return real_route_reach_step(response, state, inflow_m3s, dt_s)

        monkeypatch.setattr(reach_response_module, "route_reach_step", recording_route)

        reach_responses_from_model_release(_model_release())

        assert calls == [
            (ResponseMember.LOWER, 0.0, 60.0),
            (ResponseMember.NOMINAL, 0.0, 60.0),
            (ResponseMember.UPPER, 0.0, 60.0),
        ]


class TestRouteReachStep:
    def test_no_outflow_arrives_before_pure_delay(self):
        response = replace(RESPONSE, loss_fraction=0.0, dispersion_seconds=0.0)
        first = route_reach_step(response, _dry_state(response), 2.0, 60.0)
        second = route_reach_step(response, first, 0.0, 60.0)
        third = route_reach_step(response, second, 0.0, 60.0)

        assert (
            first.outflow_m3s,
            second.outflow_m3s,
            third.outflow_m3s,
            third.in_transit_volume_m3,
        ) == (0.0, 0.0, 2.0, 0.0)

    def test_route_reach_step_preserves_delayed_mass_balance(self):
        response = replace(
            RESPONSE,
            loss_fraction=0.25,
            dispersion_seconds=0.0,
        )
        state = route_reach_step(response, _dry_state(response), 2.0, 60.0)
        state = route_reach_step(response, state, 0.0, 60.0)
        state = route_reach_step(response, state, 0.0, 60.0)

        assert (
            state.cumulative_inflow_m3,
            state.cumulative_declared_loss_m3,
            state.cumulative_outflow_m3,
            state.in_transit_volume_m3,
            _accounted_volume_m3(state),
        ) == pytest.approx((120.0, 30.0, 90.0, 0.0, 120.0))

    def test_dispersion_releases_volume_uniformly_without_creating_water(self):
        response = replace(RESPONSE, delay_seconds=0.0, loss_fraction=0.0)
        first = route_reach_step(response, _dry_state(response), 2.0, 60.0)
        second = route_reach_step(response, first, 0.0, 60.0)

        assert (
            first.outflow_m3s,
            first.in_transit_volume_m3,
            second.outflow_m3s,
            second.in_transit_volume_m3,
            second.cumulative_outflow_m3,
        ) == pytest.approx((1.0, 60.0, 1.0, 0.0, 120.0))

    def test_zero_input_decay_drains_existing_transit(self):
        response = replace(
            RESPONSE,
            delay_seconds=0.0,
            loss_fraction=0.0,
            dispersion_seconds=180.0,
        )
        states = [route_reach_step(response, _dry_state(response), 3.0, 60.0)]
        states.append(route_reach_step(response, states[-1], 0.0, 60.0))
        states.append(route_reach_step(response, states[-1], 0.0, 60.0))

        assert tuple(state.in_transit_volume_m3 for state in states) + tuple(
            state.outflow_m3s for state in states
        ) == pytest.approx((120.0, 60.0, 0.0, 1.0, 1.0, 1.0))

    def test_withdrawal_and_operational_loss_remain_explicit_in_continuity(self):
        response = replace(
            RESPONSE,
            delay_seconds=0.0,
            loss_fraction=0.1,
            dispersion_seconds=0.0,
        )
        state = route_reach_step(
            response,
            _dry_state(response),
            inflow_m3s=4.0,
            dt_s=60.0,
            withdrawal_m3s=1.0,
            operational_loss_m3s=0.5,
        )

        assert (
            state.cumulative_inflow_m3,
            state.cumulative_declared_loss_m3,
            state.cumulative_withdrawal_m3,
            state.cumulative_operational_loss_m3,
            state.cumulative_outflow_m3,
            state.outflow_m3s,
        ) == pytest.approx((240.0, 24.0, 60.0, 30.0, 126.0, 2.1))

    def test_withdrawal_and_operational_loss_cannot_overdraw_routed_volume(self):
        response = replace(
            RESPONSE,
            delay_seconds=0.0,
            loss_fraction=0.0,
            dispersion_seconds=0.0,
        )
        with pytest.raises(ReachResponseError, match="exceed routed volume"):
            route_reach_step(
                response,
                _dry_state(response),
                inflow_m3s=1.0,
                dt_s=60.0,
                withdrawal_m3s=0.75,
                operational_loss_m3s=0.5,
            )

    def test_inflow_above_response_capacity_is_rejected(self):
        with pytest.raises(ReachResponseError, match="capacity"):
            route_reach_step(
                RESPONSE,
                _dry_state(),
                inflow_m3s=math.nextafter(RESPONSE.capacity_m3s, math.inf),
                dt_s=60.0,
            )

    def test_initial_transit_cannot_release_above_reach_capacity(self):
        response = replace(RESPONSE, delay_seconds=0.0, dispersion_seconds=0.0)
        state = ReachState(
            model_release_id=response.model_release_id,
            reach_id=response.reach_id,
            member=response.member,
            transit_volumes=(
                TransitVolume(200.0, 0.0, 0.0),
                TransitVolume(200.0, 0.0, 0.0),
            ),
            initial_volume_m3=400.0,
        )
        with pytest.raises(ReachResponseError, match="capacity"):
            route_reach_step(response, state, 0.0, 60.0)

    @pytest.mark.parametrize("dt_s", [29.0, 301.0])
    def test_timestep_outside_response_envelope_is_rejected(self, dt_s):
        with pytest.raises(ReachResponseError, match="timestep"):
            route_reach_step(RESPONSE, _dry_state(), 0.0, dt_s)

    @pytest.mark.parametrize("dt_s", [30.0, 300.0])
    def test_timestep_envelope_boundaries_are_inclusive(self, dt_s):
        assert route_reach_step(RESPONSE, _dry_state(), 0.0, dt_s).outflow_m3s == 0.0

    @pytest.mark.parametrize(
        "field,value",
        [
            ("model_release_id", "other-release"),
            ("reach_id", "C_OTHER_REACH"),
            ("member", ResponseMember.LOWER),
        ],
    )
    def test_state_lineage_must_match_response(self, field, value):
        with pytest.raises(ReachResponseError, match=field):
            route_reach_step(
                RESPONSE,
                replace(_dry_state(), **{field: value}),
                inflow_m3s=0.0,
                dt_s=60.0,
            )

    def test_state_with_broken_mass_balance_is_rejected(self):
        state = replace(_dry_state(), cumulative_outflow_m3=1.0)
        with pytest.raises(ReachResponseError, match="mass balance"):
            route_reach_step(RESPONSE, state, 0.0, 60.0)

    def test_state_rejects_mutable_transit_collection(self):
        state = replace(_dry_state(), transit_volumes=[])
        with pytest.raises(ReachResponseError, match="tuple"):
            route_reach_step(RESPONSE, state, 0.0, 60.0)

    def test_valid_initial_transit_volume_routes_without_hidden_water(self):
        response = replace(RESPONSE, delay_seconds=0.0, dispersion_seconds=0.0)
        state = ReachState(
            model_release_id=response.model_release_id,
            reach_id=response.reach_id,
            member=response.member,
            transit_volumes=(TransitVolume(90.0, 0.0, 0.0),),
            initial_volume_m3=90.0,
        )

        routed = route_reach_step(response, state, 0.0, 60.0)

        assert (
            routed.initial_volume_m3,
            routed.cumulative_outflow_m3,
            routed.in_transit_volume_m3,
        ) == (90.0, 90.0, 0.0)


class TestRouteReachStepProperties:
    @settings(max_examples=100)
    @given(
        loss_fraction=st.floats(min_value=0.0, max_value=0.8),
        delay_steps=st.integers(min_value=0, max_value=4),
        dispersion_steps=st.integers(min_value=0, max_value=4),
        inflows=st.lists(
            st.floats(min_value=0.0, max_value=10.0),
            min_size=1,
            max_size=12,
        ),
    )
    def test_every_step_preserves_nonnegative_mass_balance(
        self, loss_fraction, delay_steps, dispersion_steps, inflows
    ):
        dt_s = 60.0
        response = replace(
            RESPONSE,
            delay_seconds=delay_steps * dt_s,
            loss_fraction=loss_fraction,
            dispersion_seconds=dispersion_steps * dt_s,
            capacity_m3s=10.0,
            minimum_timestep_seconds=dt_s,
            maximum_timestep_seconds=dt_s,
        )
        state = _dry_state(response)
        for inflow_m3s in inflows:
            state = route_reach_step(response, state, inflow_m3s, dt_s)
            assert (
                state.initial_volume_m3 + state.cumulative_inflow_m3
                == pytest.approx(_accounted_volume_m3(state), abs=1e-8)
            )
            assert state.in_transit_volume_m3 >= 0.0 and state.outflow_m3s >= 0.0

    @settings(max_examples=100)
    @given(
        inflow_m3s=st.floats(min_value=0.01, max_value=10.0),
        loss_fraction=st.floats(min_value=0.0, max_value=0.8),
        delay_steps=st.integers(min_value=0, max_value=5),
    )
    def test_delay_is_causal_at_every_timestep_boundary(
        self, inflow_m3s, loss_fraction, delay_steps
    ):
        dt_s = 60.0
        response = replace(
            RESPONSE,
            delay_seconds=delay_steps * dt_s,
            loss_fraction=loss_fraction,
            dispersion_seconds=0.0,
            capacity_m3s=10.0,
            minimum_timestep_seconds=dt_s,
            maximum_timestep_seconds=dt_s,
        )
        states = [route_reach_step(response, _dry_state(response), inflow_m3s, dt_s)]
        for _ in range(delay_steps):
            states.append(route_reach_step(response, states[-1], 0.0, dt_s))

        assert (
            tuple(state.outflow_m3s for state in states[:delay_steps])
            == (0.0,) * delay_steps
        )
        assert states[delay_steps].outflow_m3s == pytest.approx(
            inflow_m3s * (1.0 - loss_fraction)
        )


def test_routed_volume_capacity_error_reports_flow_domain_attributes():
    response = ReachResponse(
        model_release_id="engineering-prior-2569-v1",
        reach_id="C_S_A",
        member=ResponseMember.NOMINAL,
        delay_seconds=0.0,
        loss_fraction=0.0,
        dispersion_seconds=0.0,
        capacity_m3s=1.0,
        minimum_timestep_seconds=60.0,
        maximum_timestep_seconds=60.0,
    )
    # Two stalled packets releasing in the same step route 80 m3 against a
    # 60 m3 per-step capacity while the step's own inflow stays legal.
    state = ReachState(
        response.model_release_id,
        response.reach_id,
        response.member,
        transit_volumes=(
            TransitVolume(40.0, 0.0, 0.0),
            TransitVolume(40.0, 0.0, 0.0),
        ),
        cumulative_inflow_m3=80.0,
    )
    with pytest.raises(ReachCapacityExceededError) as excinfo:
        route_reach_step(response, state, 0.0, 60.0)
    error = excinfo.value
    assert (error.reach_id, error.kind) == ("C_S_A", "routed_volume")
    assert error.attempted_flow_m3s == pytest.approx(80.0 / 60.0)
    assert error.capacity_m3s == 1.0
    assert "routed volume" in str(error)
