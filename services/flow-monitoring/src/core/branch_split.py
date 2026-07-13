"""
core.branch_split — the B8 branch-split inverse (Wave 2.7, offline slice).

Given a per-reach flow target for one concurrently-active set of gates, compute the
gate opening each reach needs, using the SINGLE corrected flow law (`core.gate_flow`,
F-01) — never a re-implemented one. This module is PURE (no I/O, no solver, no assumed
levels): the caller supplies each reach's real upstream/downstream levels and assembled
`GateFlowCalibration`, so it is fully unit-testable and needs no external data. The
wired `/control` path that provides freshness-stamped real levels is deferred (plan
HIGH #11): with assumed heads/default geometry the openings would be fiction.

The result is an HONEST infeasibility surface (plan HIGH #12): every reach reports
requested / achievable / deficit / reason, the delivered flow is FORWARD-RECOMPUTED at
the actually-commanded (quantized) opening rather than silently assuming the target was
met, a demand below the gate's minimum deliverable (Cs-floor) flow is flagged for
temporal pulsing instead of a tiny continuous crack, and a commanded opening that would
push MORE than the reach can carry is surfaced (canal overtop) rather than silently
capped.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .gate_flow import (
    GateFlowCalibration,
    gate_flow_m3s,
    min_deliverable_flow_m3s,
    required_opening_m,
)

# Per-reach outcome tags. A reach is feasible only when tagged DELIVERED or NO_DEMAND.
REASON_DELIVERED = "delivered"
REASON_NO_DEMAND = "no_demand"
REASON_DRY_GATE = "dry_gate"
REASON_NO_HEAD = "no_driving_head"
REASON_BELOW_FLOOR_PULSING = "below_floor_needs_pulsing"
REASON_CAPACITY_BELOW_FLOOR = "capacity_below_gate_floor"
REASON_CAPACITY_CLAMPED = "capacity_clamped"
REASON_GATE_LIMITED = "gate_capacity_limited"
REASON_OVER_CAPACITY = "over_capacity_command"
REASON_QUANTIZATION_DEFICIT = "quantization_deficit"

# Quantizer maps a continuous opening (m) to the actuator's achievable opening (m); the
# discrete-level quantizer itself is Wave 3.3 (gated on E5), so 2.7 only owns the seam.
Quantizer = Callable[[float], float]

_DEFAULT_TOL = 1e-3


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class ReachTarget:
    """One concurrently-active reach's demand and the boundary conditions to serve it.

    `capacity_m3s` is the reach's own carrying limit (e.g. canal design discharge); when
    None the gate's rated `q_max_m3s` is the only ceiling. Levels are real water-surface
    elevations (m MSL) — the caller must supply finite ones; this module never assumes
    heads. Invalid inputs fail closed at construction rather than producing a plausible
    but fictional opening.
    """

    reach: tuple[str, str]
    calibration: GateFlowCalibration
    upstream_level_m: float
    downstream_level_m: float
    target_flow_m3s: float
    capacity_m3s: Optional[float] = None

    def __post_init__(self) -> None:
        if not (
            isinstance(self.reach, tuple)
            and len(self.reach) == 2
            and all(isinstance(node, str) and node for node in self.reach)
        ):
            raise ValueError(
                f"reach must be a (upstream, downstream) pair of node-id strings, got {self.reach!r}"
            )
        if not isinstance(self.calibration, GateFlowCalibration):
            raise ValueError(
                f"calibration must be a GateFlowCalibration, got {type(self.calibration).__name__}"
            )
        for name in ("upstream_level_m", "downstream_level_m"):
            if not _finite(getattr(self, name)):
                raise ValueError(f"{name} must be a finite number, got {getattr(self, name)!r}")
        # A demand is a magnitude: 0 means "no delivery", but a negative (sign-flipped)
        # target is a bad input — reject it rather than silently treating it as no-demand
        # and letting it subtract from the network total in branch_split_summary.
        if not _finite(self.target_flow_m3s) or self.target_flow_m3s < 0:
            raise ValueError(
                f"target_flow_m3s must be a finite non-negative number, got {self.target_flow_m3s!r}"
            )
        if self.capacity_m3s is not None and (
            not _finite(self.capacity_m3s) or self.capacity_m3s < 0
        ):
            raise ValueError(
                f"capacity_m3s must be a finite non-negative number or None, got {self.capacity_m3s!r}"
            )


@dataclass(frozen=True)
class ReachOpening:
    """The gate command for one reach plus the honest accounting behind it."""

    reach: tuple[str, str]
    requested_m3s: float
    capacity_m3s: float
    opening_m: float  # continuous inverse, before quantization
    commanded_opening_m: float  # what is actually sent (quantized + clamped to travel)
    commanded_gate_flow_m3s: float  # raw flow the commanded opening passes (pre-capacity)
    achievable_m3s: float  # flow the reach actually conveys = min(gate flow, capacity)
    deficit_m3s: float  # max(0, requested - achievable)
    feasible: bool
    needs_pulsing: bool
    reason: str
    confidence: float


def branch_split_openings(
    targets: Iterable[ReachTarget],
    quantizer: Optional[Quantizer] = None,
    tol: float = _DEFAULT_TOL,
) -> list[ReachOpening]:
    """Solve each reach's inverse independently, in input order. Each reach's gate
    controls its own branch, so the split is per-reach; the shared-upstream capacity
    coupling (Σ children ≤ parent) is the rotation scheduler's concern (B7), not this
    slice's."""
    if not _finite(tol) or tol <= 0:
        # A non-finite tol would defeat every feasibility comparison (NaN comparisons are
        # all False), silently turning infeasible reaches feasible — fail closed.
        raise ValueError(f"tol must be a finite positive number, got {tol!r}")
    return [_solve_reach(target, quantizer, tol) for target in targets]


def _solve_reach(
    target: ReachTarget, quantizer: Optional[Quantizer], tol: float
) -> ReachOpening:
    cal = target.calibration
    upstream, downstream = target.upstream_level_m, target.downstream_level_m
    requested = target.target_flow_m3s
    # The binding ceiling is the tighter of the reach's carrying capacity and the gate's
    # own rated q_max — a gate cannot pass more than either.
    capacity = cal.q_max_m3s
    if target.capacity_m3s is not None:
        capacity = min(capacity, target.capacity_m3s)

    if requested <= 0:
        return _shut(target, capacity, REASON_NO_DEMAND, deficit=0.0, feasible=True)

    # The most the gate can pass at these levels. Exactly zero means no deliverable head —
    # a dry sill (Hu<=0) OR no gradient (downstream >= upstream) — so NO opening delivers
    # anything. Shut it; never command a pointless (and, if the gradient later reverses,
    # unsafe) opening that passes nothing. A genuinely tiny-but-positive q_hi is a real,
    # servable gate and falls through to the inverse.
    q_hi = gate_flow_m3s(cal, upstream, downstream, cal.max_opening_m)
    if q_hi <= 0.0:
        reason = REASON_DRY_GATE if upstream - cal.sill_m <= 0 else REASON_NO_HEAD
        return _shut(target, capacity, reason, deficit=requested, feasible=False)

    # The reach cannot carry even the gate's minimum continuous (Cs-floor) flow, so a
    # pulse to that floor would OVERTOP it — pulsing does not help. Flag the capacity
    # limit honestly rather than promising a pulse schedule that can't run. (This also
    # covers a zero-capacity reach.)
    floor = min_deliverable_flow_m3s(cal, upstream, downstream)
    if capacity < floor:
        return _shut(target, capacity, REASON_CAPACITY_BELOW_FLOOR, deficit=requested,
                     feasible=False)

    q_for_inverse = min(requested, capacity)
    opening_m, info = required_opening_m(cal, upstream, downstream, q_for_inverse, tol=tol)
    confidence = info.get("confidence", cal.confidence)
    code = info.get("code")

    if code == "below_floor":
        # capacity >= floor (checked above), so the sub-floor target is the DEMAND
        # itself: a continuous opening would overdeliver several-fold the instant it
        # cracks. Pulse the gate to the floor and let the duty cycle average down to the
        # demand — never hold a tiny continuous opening.
        return _shut(target, capacity, REASON_BELOW_FLOOR_PULSING, deficit=requested,
                     feasible=False, needs_pulsing=True, confidence=confidence)

    commanded = opening_m if quantizer is None else float(quantizer(opening_m))
    if not _finite(commanded):
        raise ValueError(f"quantizer returned a non-finite opening: {commanded!r}")
    # Clamp to physical travel [0, max]. A quantizer may legitimately command 0 (shut);
    # do NOT force a sub-minimum command up to min_opening_m — that would crack open a
    # gate the quantizer meant to close. The forward-recompute below then reports the
    # resulting (zero) delivery honestly as a deficit.
    commanded = max(0.0, min(commanded, cal.max_opening_m))

    # Forward-recompute the flow the COMMANDED opening actually passes, then the flow the
    # reach conveys (capped by capacity). Keeping both makes an over-capacity command
    # (raw > capacity — the canal would overtop) visible rather than silently swallowed.
    commanded_gate_flow = gate_flow_m3s(cal, upstream, downstream, commanded)
    delivered = min(commanded_gate_flow, capacity)
    deficit = max(0.0, requested - delivered)

    # `+ tol` is symmetric with the deficit tolerance below: a command within the flow
    # tolerance of capacity is "at capacity", not a material overtop, and the un-quantized
    # inverse (target clamped to capacity) never materially exceeds it. A quantizer that
    # pushes the command past capacity by more than tol is surfaced, not swallowed.
    if commanded_gate_flow > capacity + tol:
        outcome, feasible = REASON_OVER_CAPACITY, False
    elif deficit <= tol:
        outcome, feasible = REASON_DELIVERED, True
    elif code == "over_capacity":
        # The gate at full opening cannot pass q_for_inverse at these levels: the head,
        # not the demand-vs-capacity budget, is the binding limit — even the clamped
        # target (capacity) is unreachable. This precedes the capacity check because the
        # gate is the tighter constraint.
        outcome, feasible = REASON_GATE_LIMITED, False
    elif requested > capacity + tol:
        outcome, feasible = REASON_CAPACITY_CLAMPED, False
    else:
        outcome, feasible = REASON_QUANTIZATION_DEFICIT, False

    return ReachOpening(
        reach=target.reach,
        requested_m3s=requested,
        capacity_m3s=capacity,
        opening_m=opening_m,
        commanded_opening_m=commanded,
        commanded_gate_flow_m3s=commanded_gate_flow,
        achievable_m3s=delivered,
        deficit_m3s=deficit,
        feasible=feasible,
        needs_pulsing=False,
        reason=outcome,
        confidence=confidence,
    )


def _shut(
    target: ReachTarget,
    capacity: float,
    reason: str,
    *,
    deficit: float,
    feasible: bool,
    needs_pulsing: bool = False,
    confidence: Optional[float] = None,
) -> ReachOpening:
    """A fully-closed gate outcome (no demand, dry, or below-floor)."""
    return ReachOpening(
        reach=target.reach,
        requested_m3s=target.target_flow_m3s,
        capacity_m3s=capacity,
        opening_m=0.0,
        commanded_opening_m=0.0,
        commanded_gate_flow_m3s=0.0,
        achievable_m3s=0.0,
        deficit_m3s=deficit,
        feasible=feasible,
        needs_pulsing=needs_pulsing,
        reason=reason,
        confidence=target.calibration.confidence if confidence is None else confidence,
    )


def branch_split_summary(openings: Iterable[ReachOpening]) -> dict:
    """Roll-up of a solved reach-SET: the reaches that fell short plus per-reach-set flow
    sums. `feasible` is True only when every reach was served within tolerance.

    WARNING: `requested_m3s`/`achievable_m3s`/`deficit_m3s` are sums OVER THE REACH SET, not
    network throughput totals. The same water flows through every serial reach on a supply
    path, so on a serial chain these sums double-count the demand once per hop — do NOT
    surface them as a network total (the /openings response deliberately omits them and
    reports the true per-reach values on each ReachOpening instead). They are useful only as
    per-reach-set diagnostics for a set known to be independent (parallel) reaches."""
    openings = list(openings)
    return {
        "requested_m3s": sum(o.requested_m3s for o in openings),
        "achievable_m3s": sum(o.achievable_m3s for o in openings),
        "deficit_m3s": sum(o.deficit_m3s for o in openings),
        "feasible": all(o.feasible for o in openings),
        "infeasible_reaches": [o.reach for o in openings if not o.feasible],
        "reaches_needing_pulsing": [o.reach for o in openings if o.needs_pulsing],
    }
