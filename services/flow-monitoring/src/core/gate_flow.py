"""
core.gate_flow — the single, correct gate-flow law (F-01).

RID rating:  Q = Cs * L * Hs * sqrt(2g*dH),  Cs = K1 * (Hs/Go)^K2  (clamped).

This module is PURE (stdlib only, no I/O) so it is fully unit-testable and can be
the one source of truth for gate hydraulics. Callers assemble a `GateFlowCalibration`
(see `build_gate_flow_calibration`) from calibration + geometry, then call
`gate_flow_m3s` (forward) or `required_opening_m` (inverse).

Fixes the three stacked bugs of the old law (F-01):
  B1  Cs raised a 0..1 opening fraction to K2 instead of `(Hs/Go)^K2` with Go in metres.
  B3  Hs was taken as an absolute MSL elevation instead of head-over-sill.
  B4  Cs was unclamped, so it could reach ~18 and produce ~287 m3/s.
Plus a `q <= q_max` capacity ceiling as the final guard.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

G = 9.81
CS_MIN, CS_MAX = 0.30, 1.00
SUBMERGED_THRESHOLD = 0.80
_NO_HEAD_EPS = 1e-4

# Documented fallbacks for gates whose geometry is absent from config.
DEFAULT_WIDTH_M = 2.0
DEFAULT_MAX_OPENING_M = 2.0
DEFAULT_SILL_M = 0.0
# A gate built on default geometry is less trustworthy; scale its confidence down.
DEFAULT_GEOMETRY_CONFIDENCE_FACTOR = 0.5
# Nominal through-gate velocity (m/s) for the capacity estimate of an UNRATED gate
# (no field q_max): capacity ≈ flow area × this velocity.
NOMINAL_GATE_VELOCITY_MS = 3.0


class GateFlowError(ValueError):
    """Raised on structurally invalid gate configuration."""


@dataclass(frozen=True)
class GateFlowCalibration:
    """Everything the flow law needs for one gate (assembled from 3 sources)."""

    k1: float
    k2: float
    width_m: float
    sill_m: float
    min_opening_m: float
    max_opening_m: float
    q_max_m3s: float
    confidence: float
    range_min: float
    range_max: float

    def __post_init__(self) -> None:
        if self.width_m <= 0:
            raise GateFlowError(f"width_m must be > 0, got {self.width_m}")
        if self.max_opening_m <= self.min_opening_m:
            raise GateFlowError(
                f"max_opening_m ({self.max_opening_m}) must exceed min_opening_m ({self.min_opening_m})"
            )
        if self.q_max_m3s <= 0:
            raise GateFlowError(f"q_max_m3s must be > 0, got {self.q_max_m3s}")
        if self.k2 > 0:
            # k2>0 makes Cs (and so flow) DECREASE as the gate opens — the bisection
            # inverse assumes a non-decreasing forward law. All field/default
            # calibrations have k2<=0; a positive one is a data error, not physics.
            raise GateFlowError(f"k2 must be <= 0 (flow must not decrease as the gate opens), got {self.k2}")


def discharge_coeff(k1: float, k2: float, Hs: float, Go: float) -> float:
    """Cs = K1*(Hs/Go)^K2 (Go in metres), clamped to the physical range [0.3, 1.0]."""
    if Go <= 0 or Hs <= 0:
        return CS_MIN
    cs = k1 * (Hs / Go) ** k2
    return max(CS_MIN, min(CS_MAX, cs))


def _heads(upstream_level: float, downstream_level: float, sill_m: float) -> tuple[float, float]:
    return upstream_level - sill_m, downstream_level - sill_m


def gate_flow_m3s(
    cal: GateFlowCalibration,
    upstream_level: float,
    downstream_level: float,
    Go: float,
) -> float:
    """Forward flow (m3/s) through a gate opened `Go` metres, on real water levels.

    Returns 0 for a dry gate (Hu<=0) or no driving head (dH<=0). Never exceeds q_max.
    """
    Hu, Hd = _heads(upstream_level, downstream_level, cal.sill_m)
    if Hu <= 0:
        return 0.0
    dH = Hu - Hd
    if dH <= _NO_HEAD_EPS:
        return 0.0
    Go = min(max(Go, 0.0), cal.max_opening_m)
    if Go <= 0:
        return 0.0
    submerged = (Hd / Hu) >= SUBMERGED_THRESHOLD
    Hs = Hd if submerged else Hu
    if Hs <= 0:
        Hs = Hu
    cs = discharge_coeff(cal.k1, cal.k2, Hs, Go)
    q = cs * cal.width_m * Hs * math.sqrt(2 * G * dH)
    return min(q, cal.q_max_m3s)


# Smallest opening used to probe the discharge floor (the law is discontinuous at Go=0).
_TINY_OPENING_M = 1e-6


def min_deliverable_flow_m3s(
    cal: GateFlowCalibration,
    upstream_level: float,
    downstream_level: float,
) -> float:
    """Smallest positive flow the gate can pass at these levels (the Cs-floor discharge).

    The rating law carries the opening only inside the clamped Cs, so flow is
    DISCONTINUOUS at Go=0: any positive opening delivers at least this floor
    (~CS_MIN*width*Hs*sqrt(2g*dH)). Targets below it are physically unreachable —
    `required_opening_m` fails closed on them. Returns 0 for a dry/no-head gate.
    """
    go = max(cal.min_opening_m, _TINY_OPENING_M)
    return gate_flow_m3s(cal, upstream_level, downstream_level, go)


def required_opening_m(
    cal: GateFlowCalibration,
    upstream_level: float,
    downstream_level: float,
    q_target: float,
    tol: float = 1e-3,
) -> tuple[float, dict]:
    """Opening (metres) needed to pass `q_target`, on real levels.

    The forward law is monotone non-decreasing in Go, so bisection is used (it cannot
    diverge or oscillate the way the old Newton loop could). Returns (opening_m, info)
    where info carries feasibility, the achievable flow, the deliverable floor
    (`min_deliverable`), and the calibration confidence. Targets below the Cs-floor
    discharge fail CLOSED (opening 0.0): opening at all would overdeliver several-fold.
    """
    Hu, _ = _heads(upstream_level, downstream_level, cal.sill_m)
    if Hu <= 0:
        return 0.0, {"feasible": False, "achievable": 0.0, "confidence": cal.confidence,
                     "reason": "dry gate (no head over sill)"}
    if q_target <= 0:
        return 0.0, {"feasible": True, "achievable": 0.0, "confidence": cal.confidence}

    lo, hi = cal.min_opening_m, cal.max_opening_m
    q_hi = gate_flow_m3s(cal, upstream_level, downstream_level, hi)
    q_floor = min_deliverable_flow_m3s(cal, upstream_level, downstream_level)
    if q_target > q_hi + tol:
        return hi, {"feasible": False, "achievable": q_hi, "min_deliverable": q_floor,
                    "confidence": cal.confidence,
                    "reason": "exceeds gate capacity at current head"}
    if q_target >= q_hi - tol:
        # At capacity within tolerance: full open delivers the target (also covers the
        # constant-Cs case where the floor equals capacity and bisection cannot split).
        return hi, {"feasible": True, "achievable": q_hi, "min_deliverable": q_floor,
                    "confidence": cal.confidence}
    if q_target < q_floor - tol:
        return 0.0, {"feasible": False, "achievable": 0.0, "min_deliverable": q_floor,
                     "confidence": cal.confidence,
                     "reason": "below minimum deliverable flow at current head (Cs floor)"}
    if q_target <= q_floor + tol:
        # Floor-band target: the smallest legal opening already delivers it — return
        # that, not an arbitrary bisection point (minimizes actuator travel).
        go_min = max(cal.min_opening_m, _TINY_OPENING_M)
        return go_min, {"feasible": True, "achievable": q_floor, "min_deliverable": q_floor,
                        "confidence": cal.confidence}

    q = q_hi
    mid = hi
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        q = gate_flow_m3s(cal, upstream_level, downstream_level, mid)
        if abs(q - q_target) < tol:
            break
        if q < q_target:
            lo = mid
        else:
            hi = mid
    return mid, {"feasible": True, "achievable": q, "min_deliverable": q_floor,
                 "confidence": cal.confidence}


def build_gate_flow_calibration(
    *,
    k1: float,
    k2: float,
    confidence: float,
    q_max_m3s: float | None = None,
    width_m: float | None = None,
    sill_m: float | None = None,
    min_opening_m: float = 0.0,
    max_opening_m: float | None = None,
    shape: str | None = None,
    range_min: float = 0.0,
    range_max: float = 100.0,
) -> GateFlowCalibration:
    """Assemble a `GateFlowCalibration` from the 3 data sources.

    K1/K2/confidence/width come from the calibration loader, q_max from the calibration
    table/network, and sill/opening bounds from gate geometry. Any geometry missing from
    config falls back to a documented default AND lowers the confidence, so downstream
    consumers can see that the gate is running on assumed geometry. `shape` selects the
    flow-area model for the UNRATED-gate capacity estimate (a circular gate passes flow
    through its disc, not its bounding box).
    """
    defaulted = []
    if width_m is None or width_m <= 0:
        width_m = DEFAULT_WIDTH_M
        defaulted.append("width_m")
    if max_opening_m is None or max_opening_m <= min_opening_m:
        max_opening_m = DEFAULT_MAX_OPENING_M
        defaulted.append("max_opening_m")
    if sill_m is None:
        sill_m = DEFAULT_SILL_M
        defaulted.append("sill_m")
    if q_max_m3s is None or q_max_m3s <= 0:
        # Rough capacity estimate when the gate has no rated q_max in config: flow
        # area × a nominal velocity. A circular gate's area is its disc (π/4·d², with
        # width_m carrying the diameter), NOT the width×opening box a rectangular gate
        # uses — the latter over-reports a small orifice's capacity (2.3-retro HIGH).
        if shape == "circular":
            flow_area_m2 = math.pi / 4.0 * width_m * width_m
        else:
            flow_area_m2 = width_m * max_opening_m
        q_max_m3s = flow_area_m2 * NOMINAL_GATE_VELOCITY_MS
        defaulted.append("q_max_m3s")

    if defaulted:
        confidence = confidence * DEFAULT_GEOMETRY_CONFIDENCE_FACTOR
        logger.warning(
            "gate_flow: using default geometry %s; confidence lowered to %.3f", defaulted, confidence
        )

    return GateFlowCalibration(
        k1=k1,
        k2=k2,
        width_m=width_m,
        sill_m=sill_m,
        min_opening_m=min_opening_m,
        max_opening_m=max_opening_m,
        q_max_m3s=q_max_m3s,
        confidence=confidence,
        range_min=range_min,
        range_max=range_max,
    )
