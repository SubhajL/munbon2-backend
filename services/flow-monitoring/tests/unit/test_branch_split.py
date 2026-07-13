"""
Unit tests for core.branch_split — the B8 branch-split inverse (Wave 2.7-offline).

Pure, I/O-free tests. The module orchestrates the corrected flow law
(core.gate_flow) across a set of concurrently-active reaches, so expected openings
and flows are computed from the SAME primitives (required_opening_m / gate_flow_m3s /
min_deliverable_flow_m3s) the module builds on — never re-derived by hand. The
scenarios exercise the honest infeasibility surface the plan requires (HIGH #12):
requested / achievable / deficit / reason per reach, forward-recompute after
quantization, and below-floor demands flagged for pulsing rather than a tiny opening.
"""
import pytest

from core.branch_split import (
    REASON_BELOW_FLOOR_PULSING,
    REASON_CAPACITY_BELOW_FLOOR,
    REASON_CAPACITY_CLAMPED,
    REASON_DELIVERED,
    REASON_DRY_GATE,
    REASON_GATE_LIMITED,
    REASON_NO_DEMAND,
    REASON_NO_HEAD,
    REASON_OVER_CAPACITY,
    REASON_QUANTIZATION_DEFICIT,
    ReachTarget,
    branch_split_openings,
    branch_split_summary,
)
from core.gate_flow import (
    build_gate_flow_calibration,
    gate_flow_m3s,
    min_deliverable_flow_m3s,
    required_opening_m,
)

# A rectangular gate with a comfortable deliverable band at the levels below, so a
# mid-band target is feasible, a small one is below the Cs floor, and a large one
# exceeds what the gate passes at full opening. These SUBMERGED levels (Hd/Hu=0.83)
# and the FREE levels below (Hd/Hu=0.25) exercise both flow regimes.
UPSTREAM_M, DOWNSTREAM_M = 1.2, 1.0
FREE_UPSTREAM_M, FREE_DOWNSTREAM_M = 2.0, 0.5


def _cal(q_max_m3s=5.0, max_opening_m=2.0):
    return build_gate_flow_calibration(
        k1=1.0, k2=-1.0, width_m=1.0, sill_m=0.0,
        min_opening_m=0.0, max_opening_m=max_opening_m,
        q_max_m3s=q_max_m3s, confidence=0.9,
    )


def build_cal_min_opening(min_opening_m=0.1):
    return build_gate_flow_calibration(
        k1=1.0, k2=-1.0, width_m=1.0, sill_m=0.0,
        min_opening_m=min_opening_m, max_opening_m=2.0,
        q_max_m3s=5.0, confidence=0.9,
    )


def _target(target_flow_m3s, *, capacity_m3s=None, cal=None,
            upstream=UPSTREAM_M, downstream=DOWNSTREAM_M, reach=("M(0,0)", "M(0,1)")):
    return ReachTarget(
        reach=reach,
        calibration=cal if cal is not None else _cal(),
        upstream_level_m=upstream,
        downstream_level_m=downstream,
        target_flow_m3s=target_flow_m3s,
        capacity_m3s=capacity_m3s,
    )


def _band(cal=None, upstream=UPSTREAM_M, downstream=DOWNSTREAM_M):
    """(floor, ceiling) deliverable flows at these levels — from the flow law itself."""
    cal = cal if cal is not None else _cal()
    floor = min_deliverable_flow_m3s(cal, upstream, downstream)
    ceiling = gate_flow_m3s(cal, upstream, downstream, cal.max_opening_m)
    return floor, ceiling


class TestSingleReachInverse:
    def test_feasible_target_delivers_within_tolerance(self):
        floor, ceiling = _band()
        target = 0.5 * (floor + ceiling)  # squarely inside the band
        [opening] = branch_split_openings([_target(target)])
        expected_opening, _ = required_opening_m(_cal(), UPSTREAM_M, DOWNSTREAM_M, target)
        assert opening.reason == REASON_DELIVERED
        assert opening.feasible is True
        assert opening.needs_pulsing is False
        assert opening.opening_m == pytest.approx(expected_opening, abs=1e-4)
        assert opening.commanded_opening_m == pytest.approx(expected_opening, abs=1e-4)
        assert opening.achievable_m3s == pytest.approx(target, abs=1e-2)
        assert opening.deficit_m3s == pytest.approx(0.0, abs=1e-2)

    def test_zero_target_is_no_demand_and_shuts_the_gate(self):
        [opening] = branch_split_openings([_target(0.0)])
        assert opening.reason == REASON_NO_DEMAND
        assert opening.feasible is True
        assert (opening.commanded_opening_m, opening.achievable_m3s) == (0.0, 0.0)
        assert opening.deficit_m3s == 0.0

    def test_below_floor_target_is_flagged_for_pulsing_not_a_tiny_opening(self):
        floor, _ = _band()
        target = 0.5 * floor  # unreachable by any continuous opening (Cs floor)
        [opening] = branch_split_openings([_target(target)])
        assert opening.reason == REASON_BELOW_FLOOR_PULSING
        assert opening.needs_pulsing is True
        assert opening.feasible is False
        assert opening.commanded_opening_m == 0.0  # NOT a small continuous crack
        assert opening.achievable_m3s == 0.0
        assert opening.deficit_m3s == pytest.approx(target)

    def test_target_above_full_open_flow_is_gate_limited(self):
        floor, ceiling = _band()
        target = ceiling * 1.5  # gate at full opening cannot pass this at these levels
        [opening] = branch_split_openings([_target(target, capacity_m3s=1e9)])
        assert opening.reason == REASON_GATE_LIMITED
        assert opening.feasible is False
        assert opening.needs_pulsing is False
        assert opening.commanded_opening_m == pytest.approx(_cal().max_opening_m)
        assert opening.achievable_m3s == pytest.approx(ceiling, abs=1e-3)
        assert opening.deficit_m3s == pytest.approx(target - ceiling, abs=1e-3)

    def test_target_above_reach_capacity_is_capacity_clamped(self):
        floor, ceiling = _band()
        capacity = 0.5 * (floor + ceiling)  # a reach ceiling below the gate's own limit
        target = capacity + 0.3
        [opening] = branch_split_openings([_target(target, capacity_m3s=capacity)])
        assert opening.reason == REASON_CAPACITY_CLAMPED
        assert opening.feasible is False
        assert opening.achievable_m3s == pytest.approx(capacity, abs=1e-2)
        assert opening.deficit_m3s == pytest.approx(target - capacity, abs=1e-2)

    def test_dry_gate_delivers_nothing_and_is_flagged(self):
        # Upstream level at the sill => no head over sill => the gate is dry.
        [opening] = branch_split_openings([_target(1.0, upstream=0.0, downstream=0.0)])
        assert opening.reason == REASON_DRY_GATE
        assert opening.feasible is False
        assert opening.achievable_m3s == 0.0
        assert opening.deficit_m3s == pytest.approx(1.0)

    # A tiny target (<= tol) must NOT slip past the no-head shut — the second HIGH the
    # gpt-5.6-sol re-review found: a sub-tolerance target on a no-head gate had been
    # classified at_capacity and commanded fully open.
    @pytest.mark.parametrize("target", [1.0, 0.0005])
    def test_no_driving_head_gate_is_shut_not_commanded_fully_open(self, target):
        # A wetted sill (Hu>0) but downstream at/above upstream gives zero driving head,
        # so the gate passes nothing. It must be SHUT, never commanded fully open
        # (pointless now, unsafe if the gradient later reverses).
        [opening] = branch_split_openings(
            [_target(target, upstream=1.0, downstream=1.2)]  # downstream ABOVE upstream
        )
        assert opening.reason == REASON_NO_HEAD
        assert opening.feasible is False
        assert opening.commanded_opening_m == 0.0
        assert opening.achievable_m3s == 0.0
        assert opening.deficit_m3s == pytest.approx(target)

    def test_tiny_but_real_gate_is_served_not_falsely_shut(self):
        # QCHECK MEDIUM (gpt-5.6-sol): a genuinely positive-head gate whose full-open
        # flow is tiny (but > 0) must be SERVED, not mislabelled no_driving_head. Guards
        # against a `q_hi <= tol` proxy that would shut real low-capacity gates.
        tiny = build_gate_flow_calibration(
            k1=1.0, k2=-1.0, width_m=0.0001, sill_m=0.0,
            min_opening_m=0.0, max_opening_m=2.0, q_max_m3s=5.0, confidence=0.9,
        )
        floor, ceiling = _band(cal=tiny)
        assert 0.0 < ceiling  # the gate really does pass a (tiny) positive flow
        target = 0.5 * (floor + ceiling)
        [opening] = branch_split_openings([_target(target, cal=tiny)])
        assert opening.reason == REASON_DELIVERED
        assert opening.feasible is True
        assert opening.achievable_m3s == pytest.approx(target, abs=max(1e-4, target * 1e-2))


class TestQuantizationSeam:
    def test_down_rounding_quantizer_reports_the_deficit_not_a_silent_clamp(self):
        floor, ceiling = _band()
        target = 0.5 * (floor + ceiling)
        # Round the opening DOWN to the nearest 0.25 m so the commanded opening
        # under-delivers; the module must forward-recompute and surface the deficit.
        def floor_quarter(opening_m):
            return (int(opening_m / 0.25)) * 0.25
        [opening] = branch_split_openings([_target(target)], quantizer=floor_quarter)
        expected_commanded = floor_quarter(
            required_opening_m(_cal(), UPSTREAM_M, DOWNSTREAM_M, target)[0]
        )
        expected_delivered = gate_flow_m3s(
            _cal(), UPSTREAM_M, DOWNSTREAM_M, expected_commanded
        )
        assert opening.commanded_opening_m == pytest.approx(expected_commanded)
        assert opening.achievable_m3s == pytest.approx(expected_delivered, abs=1e-6)
        assert opening.achievable_m3s < target  # genuinely under-delivered
        assert opening.deficit_m3s == pytest.approx(target - expected_delivered, abs=1e-6)
        assert opening.reason == REASON_QUANTIZATION_DEFICIT
        assert opening.feasible is False

    def test_quantizer_that_still_meets_target_reports_delivered(self):
        floor, ceiling = _band()
        target = 0.5 * (floor + ceiling)
        # Round UP to full opening: over-delivers, so no deficit remains.
        [opening] = branch_split_openings(
            [_target(target)], quantizer=lambda _o: _cal().max_opening_m
        )
        assert opening.commanded_opening_m == pytest.approx(_cal().max_opening_m)
        assert opening.achievable_m3s >= target
        assert opening.deficit_m3s == 0.0
        assert opening.reason == REASON_DELIVERED
        assert opening.feasible is True

    def test_non_finite_quantizer_output_is_rejected(self):
        # QCHECK LOW (gpt-5.6-sol): a quantizer returning NaN/inf is an invalid actuator
        # command — fail closed rather than silently clamping it to a shut gate.
        floor, ceiling = _band()
        with pytest.raises(ValueError, match="quantizer"):
            branch_split_openings(
                [_target(0.5 * (floor + ceiling))], quantizer=lambda _o: float("nan")
            )

    def test_quantized_command_never_exceeds_gate_travel(self):
        floor, ceiling = _band()
        target = 0.5 * (floor + ceiling)
        # A quantizer that over-shoots must be clamped to the gate's max opening.
        [opening] = branch_split_openings(
            [_target(target)], quantizer=lambda _o: 999.0
        )
        assert opening.commanded_opening_m == pytest.approx(_cal().max_opening_m)

    def test_quantizer_that_shuts_the_gate_is_respected_not_forced_to_min_opening(self):
        # QCHECK (workflow): a quantizer may snap a small opening to 0 (shut). The clamp
        # must NOT force it up to min_opening_m — cracking open a gate meant to be closed.
        # The zero delivery is then surfaced honestly as a quantization deficit.
        cal = build_cal_min_opening(min_opening_m=0.1)
        floor, ceiling = _band(cal=cal)
        target = 0.5 * (floor + ceiling)
        [opening] = branch_split_openings(
            [_target(target, cal=cal)], quantizer=lambda _o: 0.0
        )
        assert opening.commanded_opening_m == 0.0  # NOT forced to 0.1
        assert opening.achievable_m3s == 0.0
        assert opening.deficit_m3s == pytest.approx(target)
        assert opening.reason == REASON_QUANTIZATION_DEFICIT
        assert opening.feasible is False


class TestBranchSplitAcrossReaches:
    def test_each_reach_is_solved_independently_and_keyed_by_its_edge(self):
        floor, ceiling = _band()
        feasible = 0.5 * (floor + ceiling)
        openings = branch_split_openings([
            _target(feasible, reach=("M(0,0)", "M(0,1)")),
            _target(0.5 * floor, reach=("M(0,1)", "M(0,1;1,0)")),
            _target(ceiling * 1.5, capacity_m3s=1e9, reach=("M(0,1)", "M(0,1;1,1)")),
        ])
        by_reach = {o.reach: o for o in openings}
        assert by_reach[("M(0,0)", "M(0,1)")].reason == REASON_DELIVERED
        assert by_reach[("M(0,1)", "M(0,1;1,0)")].reason == REASON_BELOW_FLOOR_PULSING
        assert by_reach[("M(0,1)", "M(0,1;1,1)")].reason == REASON_GATE_LIMITED

    def test_summary_aggregates_requested_delivered_and_infeasible_reaches(self):
        floor, ceiling = _band()
        feasible = 0.5 * (floor + ceiling)
        pulse = 0.5 * floor
        openings = branch_split_openings([
            _target(feasible, reach=("M(0,0)", "M(0,1)")),
            _target(pulse, reach=("M(0,1)", "M(0,1;1,0)")),
        ])
        summary = branch_split_summary(openings)
        assert summary["requested_m3s"] == pytest.approx(feasible + pulse)
        assert summary["achievable_m3s"] == pytest.approx(feasible, abs=1e-2)
        assert summary["deficit_m3s"] == pytest.approx(pulse, abs=1e-2)
        assert summary["feasible"] is False
        assert summary["infeasible_reaches"] == [("M(0,1)", "M(0,1;1,0)")]
        assert summary["reaches_needing_pulsing"] == [("M(0,1)", "M(0,1;1,0)")]

    def test_all_feasible_summary_is_feasible(self):
        floor, ceiling = _band()
        openings = branch_split_openings([
            _target(0.5 * (floor + ceiling), reach=("M(0,0)", "M(0,1)")),
            _target(0.6 * (floor + ceiling), reach=("M(0,1)", "M(0,1;1,0)")),
        ])
        summary = branch_split_summary(openings)
        assert summary["feasible"] is True
        assert summary["deficit_m3s"] == pytest.approx(0.0, abs=1e-2)
        assert summary["infeasible_reaches"] == []


class TestRoundTripProperty:
    @pytest.mark.parametrize("fraction", [0.3, 0.5, 0.7, 0.9])
    def test_feasible_target_round_trips_through_opening_and_forward_law(self, fraction):
        # For any feasible target, the un-quantized commanded opening delivers it back
        # within solver tolerance — the inverse and the forward law agree.
        floor, ceiling = _band()
        target = floor + fraction * (ceiling - floor)
        [opening] = branch_split_openings([_target(target)])
        assert opening.achievable_m3s == pytest.approx(target, abs=1e-2)
        assert opening.deficit_m3s == pytest.approx(0.0, abs=1e-2)
        assert opening.feasible is True

    @pytest.mark.parametrize("fraction", [0.3, 0.6, 0.9])
    def test_free_flow_regime_also_round_trips(self, fraction):
        # The submerged tests cover Hd/Hu>=0.8; this exercises the free-flow branch.
        floor, ceiling = _band(upstream=FREE_UPSTREAM_M, downstream=FREE_DOWNSTREAM_M)
        target = floor + fraction * (ceiling - floor)
        [opening] = branch_split_openings(
            [_target(target, upstream=FREE_UPSTREAM_M, downstream=FREE_DOWNSTREAM_M)]
        )
        assert opening.achievable_m3s == pytest.approx(target, abs=1e-2)
        assert opening.feasible is True


class TestOverCapacityCommandIsSurfaced:
    def test_quantizer_that_overtops_the_reach_is_flagged_not_silently_capped(self):
        # HIGH (gpt-5.6-sol): a quantizer rounding the opening UP can command a gate
        # flow that exceeds the reach's carrying capacity (the canal would overtop).
        # The module must SURFACE that, not silently min-cap the reported flow to
        # capacity and call it "delivered".
        floor, ceiling = _band()
        capacity = 0.5 * (floor + ceiling)  # below the full-open flow (ceiling)
        target = capacity  # a feasible in-band request
        [opening] = branch_split_openings(
            [_target(target, capacity_m3s=capacity)],
            quantizer=lambda _o: _cal().max_opening_m,  # forces full-open -> over-delivers
        )
        assert opening.reason == REASON_OVER_CAPACITY
        assert opening.feasible is False
        assert opening.commanded_gate_flow_m3s == pytest.approx(ceiling, abs=1e-3)
        assert opening.commanded_gate_flow_m3s > capacity  # the exceedance is visible
        assert opening.achievable_m3s == pytest.approx(capacity)  # canal caps conveyance


class TestReasonPrecedence:
    def test_gate_head_limit_wins_over_capacity_clamp(self):
        # HIGH (gpt-5.6-sol): when demand exceeds capacity AND the gate at full opening
        # cannot even reach capacity at the current head, the head is the binding
        # constraint — report gate_capacity_limited, not capacity_clamped.
        floor, ceiling = _band()
        capacity = ceiling + 2.0  # above what the gate passes at these levels
        target = capacity + 3.0  # also above capacity
        [opening] = branch_split_openings([_target(target, capacity_m3s=capacity)])
        assert opening.reason == REASON_GATE_LIMITED
        assert opening.feasible is False
        assert opening.achievable_m3s == pytest.approx(ceiling, abs=1e-3)


class TestBoundaryAndCapacityEdges:
    def test_target_exactly_at_floor_is_delivered_by_the_minimum_opening(self):
        floor, _ = _band()
        [opening] = branch_split_openings([_target(floor)])
        assert opening.reason == REASON_DELIVERED
        assert opening.feasible is True
        assert opening.achievable_m3s == pytest.approx(floor, abs=2e-3)

    @pytest.mark.parametrize("capacity_fraction", [0.3, 0.0])
    def test_reach_capacity_below_gate_floor_is_not_pulsable(self, capacity_fraction):
        # QCHECK (workflow + gpt-5.6-sol): the reach cannot carry even the gate's minimum
        # continuous flow (a fraction of, or exactly, zero), so pulsing to that floor
        # would OVERTOP it — this must NOT be a pulsable below-floor demand, and a
        # zero-capacity reach must land here too (not capacity_clamped).
        floor, ceiling = _band()
        capacity = capacity_fraction * floor  # below the gate's Cs floor
        target = 0.5 * (floor + ceiling)  # a demand the gate could serve if the canal could
        [opening] = branch_split_openings([_target(target, capacity_m3s=capacity)])
        assert opening.reason == REASON_CAPACITY_BELOW_FLOOR
        assert opening.needs_pulsing is False
        assert opening.feasible is False
        assert opening.commanded_opening_m == 0.0

    def test_positive_min_opening_is_respected(self):
        cal = build_cal_min_opening()
        floor, ceiling = _band(cal=cal)
        target = 0.5 * (floor + ceiling)
        [opening] = branch_split_openings([_target(target, cal=cal)])
        assert opening.commanded_opening_m >= cal.min_opening_m
        assert opening.feasible is True


class TestInputValidationFailsClosed:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -3.0, -1e-9])
    def test_non_finite_or_negative_target_is_rejected(self, bad):
        # A sign-flipped negative demand must fail closed, not be swallowed as no-demand
        # (which would subtract from the network total in branch_split_summary).
        with pytest.raises(ValueError, match="target_flow_m3s"):
            _target(bad)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_non_finite_levels_are_rejected(self, bad):
        with pytest.raises(ValueError, match="level"):
            _target(1.0, upstream=bad)

    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_invalid_capacity_is_rejected(self, bad):
        with pytest.raises(ValueError, match="capacity"):
            _target(1.0, capacity_m3s=bad)

    @pytest.mark.parametrize("bad_reach", [("A",), ("A", "B", "C"), ("A", ""), "AB", (1, 2)])
    def test_malformed_reach_is_rejected(self, bad_reach):
        with pytest.raises(ValueError, match="reach"):
            ReachTarget(bad_reach, _cal(), 1.2, 1.0, 1.0)

    def test_non_calibration_is_rejected(self):
        with pytest.raises(ValueError, match="calibration"):
            ReachTarget(("A", "B"), None, 1.2, 1.0, 1.0)

    @pytest.mark.parametrize("bad_tol", [0.0, -1e-3, float("nan"), float("inf")])
    def test_non_positive_or_non_finite_tol_is_rejected(self, bad_tol):
        # A non-finite/zero tol would defeat every feasibility comparison and silently
        # turn infeasible reaches feasible.
        with pytest.raises(ValueError, match="tol"):
            branch_split_openings([_target(1.0)], tol=bad_tol)

    def test_all_infeasible_summary_lists_every_reach(self):
        floor, _ = _band()
        openings = branch_split_openings([
            _target(0.5 * floor, reach=("A", "B")),
            _target(0.4 * floor, reach=("B", "C")),
        ])
        summary = branch_split_summary(openings)
        assert summary["feasible"] is False
        assert summary["infeasible_reaches"] == [("A", "B"), ("B", "C")]
        assert summary["achievable_m3s"] == 0.0
