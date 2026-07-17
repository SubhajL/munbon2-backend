"""Muskingum-Cunge engineering-response primitives (PR 2.1c).

Pure hydraulic derivations under the approved V1 policy: Manning normal
depth on surveyed trapezoids, flood-wave celerity c = dQ/dA (never the
particle velocity Q/A), a causal mass-conserving step response, and the
deterministic t10/t90 surrogate fit. All expectations are independent:
analytical limits, direct Manning-equation residuals, or hand-computed
series — never the module's own output.
"""

import math

import pytest

from core.muskingum_cunge import (
    CascadeSection,
    MuskingumCungeError,
    TrapezoidSection,
    fit_t10_t90,
    flood_wave_celerity_m_s,
    normal_depth_m,
    route_cascade,
    route_step_response,
)

# A real LMC section shape (canal_geometry.json section 1).
SECTION = TrapezoidSection(
    bottom_width_m=3.5,
    depth_m=1.85,
    side_slope=1.5,
    manning_n=0.018,
    bed_slope=0.0002,
)


def _manning_flow(section: TrapezoidSection, depth: float) -> float:
    area = (section.bottom_width_m + section.side_slope * depth) * depth
    perimeter = section.bottom_width_m + 2.0 * depth * math.sqrt(
        1.0 + section.side_slope**2
    )
    radius = area / perimeter
    return (
        area
        * radius ** (2.0 / 3.0)
        * math.sqrt(section.bed_slope)
        / section.manning_n
    )


class TestNormalDepth:
    def test_normal_depth_satisfies_the_manning_equation(self):
        flow = 4.0

        depth = normal_depth_m(SECTION, flow)

        assert _manning_flow(SECTION, depth) == pytest.approx(flow, rel=1e-8)

    def test_normal_depth_grows_monotonically_with_flow(self):
        depths = [normal_depth_m(SECTION, flow) for flow in (0.5, 2.0, 6.0)]

        assert depths == sorted(depths)

    @pytest.mark.parametrize("flow", [0.0, -1.0, float("nan")])
    def test_non_positive_or_non_finite_flow_is_rejected(self, flow):
        with pytest.raises(MuskingumCungeError):
            normal_depth_m(SECTION, flow)


class TestFloodWaveCelerity:
    def test_wide_rectangular_limit_matches_five_thirds_velocity(self):
        """For a very wide rectangular channel under Manning flow the
        kinematic celerity is analytically (5/3)·V."""
        wide = TrapezoidSection(
            bottom_width_m=500.0,
            depth_m=5.0,
            side_slope=0.0,
            manning_n=0.02,
            bed_slope=0.001,
        )
        flow = 300.0
        depth = normal_depth_m(wide, flow)
        velocity = flow / (wide.bottom_width_m * depth)

        celerity = flood_wave_celerity_m_s(wide, flow)

        assert celerity == pytest.approx((5.0 / 3.0) * velocity, rel=1e-2)

    def test_celerity_exceeds_particle_velocity_on_a_real_section(self):
        flow = 4.0
        depth = normal_depth_m(SECTION, flow)
        area = (SECTION.bottom_width_m + SECTION.side_slope * depth) * depth

        celerity = flood_wave_celerity_m_s(SECTION, flow)

        assert celerity > flow / area

    def test_celerity_is_dq_da_not_q_over_a(self):
        """c must track the rating-curve slope: perturbing the flow by a
        small amount, ΔQ/ΔA computed from two normal states must agree."""
        flow = 4.0
        delta = 0.01
        states = {}
        for q in (flow - delta, flow + delta):
            depth = normal_depth_m(SECTION, q)
            states[q] = (SECTION.bottom_width_m + SECTION.side_slope * depth) * depth
        expected = (2.0 * delta) / (states[flow + delta] - states[flow - delta])

        assert flood_wave_celerity_m_s(SECTION, flow) == pytest.approx(
            expected, rel=1e-3
        )


class TestRouteStepResponse:
    def test_step_response_is_causal_nonnegative_and_mass_conserving(self):
        outflows = route_step_response(
            SECTION,
            length_m=1450.0,
            reference_flow_m3s=4.0,
            timestep_seconds=60.0,
            horizon_steps=240,
        )

        assert all(flow >= 0.0 for flow in outflows)
        assert outflows[-1] == pytest.approx(4.0, rel=1e-6)
        inflow_volume = 4.0 * 60.0 * len(outflows)
        outflow_volume = sum(flow * 60.0 for flow in outflows)
        storage = inflow_volume - outflow_volume
        assert storage >= -1e-6
        assert storage <= 4.0 * 60.0 * len(outflows) * 0.5

    def test_longer_reach_arrives_later(self):
        short = route_step_response(
            SECTION, 500.0, 4.0, timestep_seconds=60.0, horizon_steps=240
        )
        long = route_step_response(
            SECTION, 5000.0, 4.0, timestep_seconds=60.0, horizon_steps=480
        )

        short_t10, _ = fit_t10_t90(short, 4.0, 60.0)
        long_t10, _ = fit_t10_t90(long, 4.0, 60.0)

        assert long_t10 > short_t10

    @pytest.mark.parametrize(
        ("length_m", "match"),
        [(0.0, "length"), (-100.0, "length")],
    )
    def test_zero_or_negative_length_is_rejected(self, length_m, match):
        with pytest.raises(MuskingumCungeError, match=match):
            route_step_response(
                SECTION, length_m, 4.0, timestep_seconds=60.0, horizon_steps=10
            )

    def test_unconverged_horizon_is_rejected(self):
        with pytest.raises(MuskingumCungeError, match="horizon"):
            route_step_response(
                SECTION,
                length_m=50000.0,
                reference_flow_m3s=4.0,
                timestep_seconds=60.0,
                horizon_steps=5,
            )


class TestFitT10T90:
    def test_extraction_interpolates_known_crossings_exactly(self):
        """Hand-built linear ramp under the end-of-step convention
        (sample i is the instantaneous outflow at (i+1)*dt): the 10%
        threshold (1.0) is reached exactly
        at sample index 1 => t = 120 s, and the 90% threshold (9.0) exactly
        at sample index 9 => t = 600 s. A mid-span threshold interpolates:
        2.5 sits halfway between samples 2 (2.0 @ 180 s) and 3 (3.0 @ 240 s)."""
        reference = 10.0
        outflows = [0.0] + [reference * index / 10.0 for index in range(1, 11)]

        t10, t90 = fit_t10_t90(outflows, reference, timestep_seconds=60.0)

        assert t10 == pytest.approx(120.0)
        assert t90 == pytest.approx(600.0)

    def test_extraction_interpolates_mid_span_crossings(self):
        """Crossings between samples interpolate linearly: with samples
        [0, 4, 8, 10, 10] @ 60 s the 10% threshold (1.0) sits a quarter of
        the way from 0 (@60 s) to 4 (@120 s) => 75 s, and the 90% threshold
        (9.0) halfway from 8 (@180 s) to 10 (@240 s) => 210 s."""
        t10, t90 = fit_t10_t90([0.0, 4.0, 8.0, 10.0, 10.0], 10.0, 60.0)

        assert t10 == pytest.approx(75.0)
        assert t90 == pytest.approx(210.0)

    def test_extraction_is_deterministic(self):
        outflows = route_step_response(
            SECTION, 1450.0, 4.0, timestep_seconds=60.0, horizon_steps=240
        )

        assert fit_t10_t90(outflows, 4.0, 60.0) == fit_t10_t90(
            outflows, 4.0, 60.0
        )

    def test_never_reaching_thresholds_is_rejected(self):
        with pytest.raises(MuskingumCungeError, match="threshold"):
            fit_t10_t90([0.0, 0.5], 10.0, 60.0)


STEEP = TrapezoidSection(
    bottom_width_m=1.2,
    depth_m=1.0,
    side_slope=1.0,
    manning_n=0.030,
    bed_slope=0.003,
)


class TestRouteCascade:
    def test_cascade_of_one_section_matches_single_section_routing(self):
        single = route_step_response(
            SECTION, 1450.0, 4.0, timestep_seconds=60.0, horizon_steps=240
        )
        cascade = route_cascade(
            (CascadeSection(SECTION, 1450.0, 4.0),),
            step_flow_m3s=4.0,
            timestep_seconds=60.0,
            horizon_steps=240,
        )

        assert cascade == single

    def test_cascade_is_causal_and_mass_conserving_across_sections(self):
        outflows = route_cascade(
            (
                CascadeSection(SECTION, 1450.0, 4.0),
                CascadeSection(STEEP, 800.0, 2.0),
            ),
            step_flow_m3s=4.0,
            timestep_seconds=60.0,
            horizon_steps=480,
        )

        assert all(flow >= 0.0 for flow in outflows)
        assert outflows[-1] == pytest.approx(4.0, rel=1e-6)
        t10_two, _ = fit_t10_t90(outflows, 4.0, 60.0)
        t10_one, _ = fit_t10_t90(
            route_step_response(SECTION, 1450.0, 4.0, 60.0, 240), 4.0, 60.0
        )
        assert t10_two > t10_one

    def test_cascade_with_fixed_states_is_order_invariant(self):
        """A constant-coefficient Muskingum-Cunge cascade is a chain of
        linear time-invariant cells, so with FIXED per-section states the
        composed response is section-order invariant (documented property).
        Physical order-sensitivity enters upstream, where the generator's
        seepage threading assigns DIFFERENT states depending on order."""
        slow_first = route_cascade(
            (
                CascadeSection(STEEP, 3000.0, 0.4),
                CascadeSection(SECTION, 1450.0, 4.0),
            ),
            step_flow_m3s=4.0,
            timestep_seconds=60.0,
            horizon_steps=960,
        )
        fast_first = route_cascade(
            (
                CascadeSection(SECTION, 1450.0, 4.0),
                CascadeSection(STEEP, 3000.0, 0.4),
            ),
            step_flow_m3s=4.0,
            timestep_seconds=60.0,
            horizon_steps=960,
        )

        t_slow = fit_t10_t90(slow_first, 4.0, 60.0)
        t_fast = fit_t10_t90(fast_first, 4.0, 60.0)
        assert t_slow == pytest.approx(t_fast, rel=1e-9)

    def test_flow_above_design_depth_capacity_is_rejected(self):
        with pytest.raises(MuskingumCungeError, match="design depth"):
            normal_depth_m(STEEP, 5.0)

    def test_custom_thresholds_change_the_fit(self):
        outflows = [0.0, 4.0, 8.0, 10.0, 10.0]

        default_fit = fit_t10_t90(outflows, 10.0, 60.0)
        wide_fit = fit_t10_t90(
            outflows, 10.0, 60.0, lower_threshold=0.3, upper_threshold=0.7
        )

        assert wide_fit != default_fit
        with pytest.raises(MuskingumCungeError, match="thresholds"):
            fit_t10_t90(outflows, 10.0, 60.0, lower_threshold=0.9,
                        upper_threshold=0.1)

    def test_empty_cascade_is_rejected(self):
        with pytest.raises(MuskingumCungeError, match="section"):
            route_cascade(
                (), step_flow_m3s=4.0, timestep_seconds=60.0, horizon_steps=10
            )
