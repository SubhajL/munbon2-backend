"""
Unit tests for core.gate_flow — the single, correct gate-flow law (F-01).

These are pure, I/O-free tests. Run in isolation with:
    pytest --noconftest tests/unit/test_gate_flow.py
(the shared tests/conftest.py eagerly imports the heavy service stack, which the
pure flow law does not need.)

Scenarios use gate M(0,0) — the field-calibrated gate whose old law blew up to
~287 m3/s at 10% open. K1/K2 come from src/config/gate_calibrations.json
(k1=1.0693, k2=-1.229, q_max=11.2); geometry values are typical canal figures,
documented at each use.
"""
import math

import pytest

from core.gate_flow import (
    CS_MAX,
    CS_MIN,
    NOMINAL_GATE_VELOCITY_MS,
    GateFlowCalibration,
    GateFlowError,
    build_gate_flow_calibration,
    discharge_coeff,
    gate_flow_m3s,
    min_deliverable_flow_m3s,
    required_opening_m,
)

# --- test fixtures / builders -------------------------------------------------

# M(0,0): sill at 218.0 m MSL, 4 m wide, opens 0..2 m, rated 11.2 m3/s.
M00 = dict(
    k1=1.0693,
    k2=-1.229,
    width_m=4.0,
    sill_m=218.0,
    min_opening_m=0.0,
    max_opening_m=2.0,
    q_max_m3s=11.2,
    confidence=0.95,
    range_min=0.0,
    range_max=100.0,
)


def make_cal(**overrides):
    params = dict(M00)
    params.update(overrides)
    return GateFlowCalibration(**params)


# Submerged operating point: Hu=1.5, Hd=1.3 -> sigma=0.867 >= 0.80 (submerged),
# driving head dH=0.2 m. With these levels the gate cannot reach its 11.2 cap.
SUB_UP, SUB_DOWN = 219.5, 219.3  # sill 218.0 -> Hu=1.5, Hd=1.3

# High-head free-flow point: Hu=2.0, Hd=0.5 -> sigma=0.25 < 0.80 (free),
# large driving head so the gate WOULD exceed its 11.2 cap -> capacity binds.
HIGH_UP, HIGH_DOWN = 220.0, 218.5  # sill 218.0 -> Hu=2.0, Hd=0.5


# --- discharge_coeff -----------------------------------------------------------

class TestDischargeCoeff:
    @pytest.mark.parametrize(
        "Hs, Go",
        [(1.3, 0.05), (1.3, 0.2), (1.3, 0.6), (1.3, 1.0), (1.3, 1.5), (2.0, 0.01), (2.0, 5.0)],
    )
    def test_coeff_always_within_physical_bounds(self, Hs, Go):
        cs = discharge_coeff(M00["k1"], M00["k2"], Hs, Go)
        assert CS_MIN <= cs <= CS_MAX

    def test_coeff_increases_with_opening_in_unclamped_band(self):
        # For k2<0, Cs rises with Go until it saturates at CS_MAX.
        cs_low = discharge_coeff(M00["k1"], M00["k2"], Hs=1.3, Go=0.6)
        cs_high = discharge_coeff(M00["k1"], M00["k2"], Hs=1.3, Go=1.0)
        assert cs_high > cs_low

    def test_nonpositive_opening_or_head_returns_floor(self):
        assert discharge_coeff(M00["k1"], M00["k2"], Hs=1.3, Go=0.0) == CS_MIN
        assert discharge_coeff(M00["k1"], M00["k2"], Hs=0.0, Go=0.5) == CS_MIN


# --- gate_flow_m3s: the F-01 regression + invariants ---------------------------

class TestGateFlow:
    def test_287_regression_flow_never_blows_up_at_small_opening(self):
        # The exact input that produced 287 m3/s on the old inverted law.
        cal = make_cal()
        q = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, Go=0.10 * cal.max_opening_m)
        assert q <= cal.q_max_m3s
        assert q < 20.0  # nowhere near the historical 287

    @pytest.mark.parametrize("frac", [0.05, 0.1, 0.25, 0.5, 0.75, 1.0])
    def test_flow_never_exceeds_capacity(self, frac):
        cal = make_cal()
        q = gate_flow_m3s(cal, HIGH_UP, HIGH_DOWN, Go=frac * cal.max_opening_m)
        assert 0.0 <= q <= cal.q_max_m3s

    def test_flow_is_nondecreasing_in_opening(self):
        cal = make_cal()
        openings = [i * cal.max_opening_m / 20 for i in range(1, 21)]
        flows = [gate_flow_m3s(cal, SUB_UP, SUB_DOWN, go) for go in openings]
        for prev, nxt in zip(flows, flows[1:]):
            assert nxt >= prev - 1e-9

    def test_flow_strictly_increases_in_unclamped_band(self):
        # Go=0.6 and Go=1.0 sit in M(0,0)'s unclamped, sub-capacity band.
        cal = make_cal()
        q_low = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, Go=0.6)
        q_high = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, Go=1.0)
        assert q_high > q_low

    def test_flow_capped_at_qmax_under_high_head(self):
        cal = make_cal()
        q_full = gate_flow_m3s(cal, HIGH_UP, HIGH_DOWN, Go=cal.max_opening_m)
        assert q_full == pytest.approx(cal.q_max_m3s)

    def test_dry_gate_returns_zero(self):
        cal = make_cal()
        # upstream below sill -> no water over the gate.
        assert gate_flow_m3s(cal, 217.5, 217.0, Go=1.0) == 0.0

    def test_no_driving_head_returns_zero(self):
        cal = make_cal()
        # equal levels -> dH<=0 -> no forward flow, no NaN/exception.
        q = gate_flow_m3s(cal, 219.5, 219.5, Go=1.0)
        assert q == 0.0

    def test_msl_levels_do_not_blow_up(self):
        # Absolute MSL elevations (not depths) must stay finite and capped.
        cal = make_cal()
        q = gate_flow_m3s(cal, 219.0, 218.8, Go=0.5)  # Hu=1.0, Hd=0.8
        assert math.isfinite(q)
        assert 0.0 <= q <= cal.q_max_m3s


# --- required_opening_m: inverse via bisection ---------------------------------

class TestRequiredOpening:
    def test_round_trip_opening_recovers_target_flow(self):
        cal = make_cal()
        q_target = 5.0  # within the submerged achievable band [~3.1, ~10.3]
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target)
        assert info["feasible"] is True
        assert cal.min_opening_m <= opening <= cal.max_opening_m
        q_back = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, opening)
        assert q_back == pytest.approx(q_target, abs=1e-2)

    def test_target_over_capacity_is_infeasible(self):
        cal = make_cal()
        opening, info = required_opening_m(cal, HIGH_UP, HIGH_DOWN, q_target=cal.q_max_m3s + 5.0)
        assert info["feasible"] is False
        assert opening == cal.max_opening_m
        assert info["achievable"] <= cal.q_max_m3s

    def test_zero_or_dry_target_returns_zero_opening(self):
        cal = make_cal()
        assert required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=0.0)[0] == 0.0
        assert required_opening_m(cal, 217.0, 216.5, q_target=5.0)[0] == 0.0  # dry

    def test_confidence_is_surfaced_from_calibration(self):
        cal = make_cal(confidence=0.80)
        _, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=5.0)
        assert info["confidence"] == 0.80


# --- the Cs-floor discharge minimum (2026-07-09 review, MED) --------------------
#
# The rating law carries the opening only inside the clamped Cs, so flow is
# discontinuous at Go=0: at the SUB point any positive opening delivers at least
# CS_MIN*width*Hs*sqrt(2g*dH) ~= 3.09 m3/s. The inverse used to return an ~0
# opening with feasible=True for targets below that floor — a 3-15x overdelivery
# reported as success, with no caller checking `achievable`.

class TestMinDeliverableFloor:
    def test_min_deliverable_matches_tiny_opening_flow(self):
        cal = make_cal()
        q_floor = min_deliverable_flow_m3s(cal, SUB_UP, SUB_DOWN)
        q_tiny = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, Go=1e-6)
        assert q_floor == pytest.approx(q_tiny)
        assert q_floor > 1.0  # the floor is far from negligible at this head

    def test_dry_gate_min_deliverable_is_zero(self):
        cal = make_cal()
        assert min_deliverable_flow_m3s(cal, 217.5, 217.0) == 0.0

    @pytest.mark.parametrize("q_target", [0.2, 1.0, 2.5])
    def test_below_floor_target_is_infeasible_and_gate_stays_shut(self, q_target):
        cal = make_cal()
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target)
        assert info["feasible"] is False
        assert opening == 0.0  # fail closed: shut beats a 3-15x overdelivery
        assert info["achievable"] == 0.0
        assert info["min_deliverable"] > q_target
        assert "minimum deliverable" in info["reason"]

    def test_floor_is_reported_on_feasible_solutions_too(self):
        cal = make_cal()
        _, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=5.0)
        assert info["feasible"] is True
        assert 0.0 < info["min_deliverable"] < 5.0

    @pytest.mark.parametrize("q_target", [3.2, 5.0, 8.0, 10.0])
    def test_at_or_above_floor_targets_converge(self, q_target):
        cal = make_cal()
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target)
        assert info["feasible"] is True
        assert info["achievable"] == pytest.approx(q_target, abs=1e-2)


class TestCapacityAndFloorBoundaries:
    def test_target_exactly_at_capacity_is_feasible_full_open(self):
        cal = make_cal()
        q_hi = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, cal.max_opening_m)
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=q_hi)
        assert info["feasible"] is True
        assert opening == cal.max_opening_m
        assert info["achievable"] == pytest.approx(q_hi)

    def test_target_just_over_capacity_is_infeasible(self):
        cal = make_cal()
        q_hi = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, cal.max_opening_m)
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=q_hi + 0.01)
        assert info["feasible"] is False
        assert opening == cal.max_opening_m
        assert info["reason"] == "exceeds gate capacity at current head"

    def test_constant_cs_floor_equals_capacity_exact_target_is_feasible(self):
        # k2=0 -> Cs constant -> every positive opening delivers the same flow, so the
        # floor EQUALS capacity; the exact target must be feasible, not "over capacity".
        cal = make_cal(k2=0.0)
        q_hi = gate_flow_m3s(cal, SUB_UP, SUB_DOWN, cal.max_opening_m)
        assert min_deliverable_flow_m3s(cal, SUB_UP, SUB_DOWN) == pytest.approx(q_hi)
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=q_hi)
        assert info["feasible"] is True
        assert info["achievable"] == pytest.approx(q_hi)

    @pytest.mark.parametrize("offset", [-5e-4, 0.0, 5e-4])
    def test_floor_band_target_is_feasible_at_the_minimal_opening(self, offset):
        # Inside the tolerance band the target is honored at the floor with the
        # SMALLEST legal opening (not an arbitrary bisection point), not rejected.
        cal = make_cal()
        q_floor = min_deliverable_flow_m3s(cal, SUB_UP, SUB_DOWN)
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=q_floor + offset)
        assert info["feasible"] is True
        assert 0.0 < opening <= 1e-5  # minimal positive opening for a min_opening_m=0 gate
        assert info["achievable"] == pytest.approx(q_floor, abs=2e-3)

    def test_floor_band_target_respects_a_positive_min_opening(self):
        cal = make_cal(min_opening_m=0.5)
        q_floor = min_deliverable_flow_m3s(cal, SUB_UP, SUB_DOWN)
        opening, info = required_opening_m(cal, SUB_UP, SUB_DOWN, q_target=q_floor)
        assert info["feasible"] is True
        assert opening == 0.5  # never commands below the gate's legal minimum

    def test_min_opening_gate_probes_floor_at_its_legal_minimum(self):
        cal = make_cal(min_opening_m=0.5)
        q_floor = min_deliverable_flow_m3s(cal, SUB_UP, SUB_DOWN)
        assert q_floor == pytest.approx(gate_flow_m3s(cal, SUB_UP, SUB_DOWN, Go=0.5))


class TestCalibrationValidation:
    def test_positive_k2_is_rejected(self):
        # k2>0 inverts monotonicity (flow would DROP as the gate opens), silently
        # breaking the bisection inverse — fail at construction, not mid-solve.
        with pytest.raises(GateFlowError, match="k2"):
            make_cal(k2=0.5)

    def test_zero_k2_is_allowed(self):
        make_cal(k2=0.0)  # constant Cs: degenerate but monotone — no exception


# --- build_gate_flow_calibration: 3-source assembly + documented defaults ------

class TestBuilder:
    def test_builds_from_full_inputs(self):
        cal = build_gate_flow_calibration(
            k1=1.0693, k2=-1.229, width_m=4.0, sill_m=218.0,
            max_opening_m=2.0, q_max_m3s=11.2, confidence=0.95,
        )
        assert (cal.k1, cal.k2, cal.width_m, cal.q_max_m3s) == (1.0693, -1.229, 4.0, 11.2)
        assert cal.confidence == 0.95

    def test_missing_geometry_uses_documented_defaults_and_lowers_confidence(self):
        # A gate with K1/K2 but no sill/opening/width geometry.
        cal = build_gate_flow_calibration(
            k1=1.0693, k2=-1.229, width_m=None, sill_m=None,
            max_opening_m=None, q_max_m3s=11.2, confidence=0.80,
        )
        assert cal.width_m > 0
        assert cal.max_opening_m > 0
        assert cal.confidence < 0.80  # default geometry reduces confidence

    def test_circular_capacity_fallback_uses_disc_area_not_bounding_box(self):
        # 2.3-retro HIGH: an UNRATED circular gate (q_max absent) must estimate its
        # capacity from the disc area (π/4·d²·v), not the d×d bounding box the
        # rectangular model uses — over-reporting a small orifice's capacity is unsafe.
        d = 0.4
        cal = build_gate_flow_calibration(
            k1=1.2, k2=-2.5, width_m=d, max_opening_m=d, q_max_m3s=None,
            confidence=0.5, shape="circular",
        )
        assert cal.q_max_m3s == pytest.approx(
            math.pi / 4 * d * d * NOMINAL_GATE_VELOCITY_MS
        )
        # strictly below the rectangular bounding-box estimate it replaces
        assert cal.q_max_m3s < d * d * NOMINAL_GATE_VELOCITY_MS

    def test_rectangular_capacity_fallback_uses_width_times_opening(self):
        # Regression guard: non-circular gates keep the width×opening×v estimate.
        cal = build_gate_flow_calibration(
            k1=1.1, k2=-1.8, width_m=2.0, max_opening_m=1.5, q_max_m3s=None,
            confidence=0.6, shape="rectangular",
        )
        assert cal.q_max_m3s == pytest.approx(2.0 * 1.5 * NOMINAL_GATE_VELOCITY_MS)
