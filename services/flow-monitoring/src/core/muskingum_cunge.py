"""Muskingum-Cunge engineering response for surveyed trapezoidal reaches.

Approved V1 policy (2026-07-17 handoff): arrival of a flow change travels
at the flood-wave celerity c = dQ/dA — never the particle velocity Q/A —
with reach travel time K = L/c, evaluated at one explicit reference
hydraulic state. The causal step response is derived with Muskingum-Cunge
coefficients fixed at that reference state (the policy's single
"(Q0+Q1)/2" evaluation point; flow dependence enters through the
per-member reference-flow perturbations, not per-step coefficient
updates). Subreaches are sized to a Courant number near one at the
reference state so every routing coefficient is non-negative: the
response is causal, mass-conserving, and monotone by construction, and
anything else fails closed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import design_profile as _design_profile

__all__ = [
    "CascadeSection",
    "MuskingumCungeError",
    "TrapezoidSection",
    "fit_t10_t90",
    "flood_wave_celerity_m_s",
    "normal_depth_m",
    "route_cascade",
    "route_step_response",
]

_MAX_SUBREACH_RETRIES = 10_000
_CONVERGENCE_REL_TOL = 1e-6


class MuskingumCungeError(ValueError):
    """A reach cannot yield a reviewed engineering response."""


@dataclass(frozen=True)
class TrapezoidSection:
    bottom_width_m: float
    depth_m: float
    side_slope: float
    manning_n: float
    bed_slope: float

    def __post_init__(self) -> None:
        for name in ("bottom_width_m", "depth_m", "manning_n", "bed_slope"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0.0
            ):
                raise MuskingumCungeError(
                    f"section {name} must be a positive finite number"
                )
        if (
            isinstance(self.side_slope, bool)
            or not isinstance(self.side_slope, (int, float))
            or not math.isfinite(self.side_slope)
            or self.side_slope < 0.0
        ):
            raise MuskingumCungeError(
                "section side_slope must be a non-negative finite number"
            )


def _as_design_section(
    section: TrapezoidSection,
) -> "_design_profile.TrapezoidSection":
    return _design_profile.TrapezoidSection(
        bottom_width_m=section.bottom_width_m,
        side_slope=section.side_slope,
        manning_n=section.manning_n,
        bed_slope=section.bed_slope,
        max_depth_m=section.depth_m,
    )


def _area_m2(section: TrapezoidSection, depth: float) -> float:
    return _design_profile.trapezoid_area_m2(depth, _as_design_section(section))


def _top_width_m(section: TrapezoidSection, depth: float) -> float:
    return section.bottom_width_m + 2.0 * section.side_slope * depth


def _manning_flow_m3s(section: TrapezoidSection, depth: float) -> float:
    # Single Manning home (C10): delegate to the consolidated design_profile
    # implementation instead of forking the flow law.
    return _design_profile.manning_flow_m3s(depth, _as_design_section(section))


def _validate_flow(flow_m3s: float) -> None:
    if (
        isinstance(flow_m3s, bool)
        or not isinstance(flow_m3s, (int, float))
        or not math.isfinite(flow_m3s)
        or flow_m3s <= 0.0
    ):
        raise MuskingumCungeError(
            "reference flow must be a positive finite number"
        )


def normal_depth_m(section: TrapezoidSection, flow_m3s: float) -> float:
    """Manning normal depth, capped at the surveyed design depth: a flow
    whose uniform stage would exceed the surveyed channel fails closed
    rather than routing on extrapolated freeboard geometry. Delegates to
    the consolidated design_profile bisection (single Manning home)."""
    _validate_flow(flow_m3s)
    try:
        return _design_profile.normal_depth_m(
            flow_m3s, _as_design_section(section)
        )
    except _design_profile.DesignProfileError as exc:
        raise MuskingumCungeError(
            "flow exceeds the Manning capacity at the surveyed design "
            f"depth; refusing to extrapolate the channel ({exc})"
        ) from exc


def flood_wave_celerity_m_s(section: TrapezoidSection, flow_m3s: float) -> float:
    """c = dQ/dA along the Manning rating (central difference)."""
    _validate_flow(flow_m3s)
    delta = max(1e-6, 1e-4 * flow_m3s)
    depth_low = normal_depth_m(section, flow_m3s - delta)
    depth_high = normal_depth_m(section, flow_m3s + delta)
    area_low = _area_m2(section, depth_low)
    area_high = _area_m2(section, depth_high)
    if area_high <= area_low:
        raise MuskingumCungeError(
            "rating curve is not monotone; celerity is undefined"
        )
    return (2.0 * delta) / (area_high - area_low)


def _routing_coefficients(
    section: TrapezoidSection,
    length_m: float,
    reference_flow_m3s: float,
    timestep_seconds: float,
) -> tuple[int, float, float, float]:
    celerity = flood_wave_celerity_m_s(section, reference_flow_m3s)
    depth = normal_depth_m(section, reference_flow_m3s)
    top_width = _top_width_m(section, depth)

    subreaches = max(1, round(length_m / (celerity * timestep_seconds)))
    for _ in range(_MAX_SUBREACH_RETRIES):
        dx = length_m / subreaches
        travel_time = dx / celerity
        weight = 0.5 - reference_flow_m3s / (
            2.0 * top_width * section.bed_slope * celerity * dx
        )
        weight = min(0.5, max(0.0, weight))
        denominator = 2.0 * travel_time * (1.0 - weight) + timestep_seconds
        c1 = (timestep_seconds - 2.0 * travel_time * weight) / denominator
        c2 = (timestep_seconds + 2.0 * travel_time * weight) / denominator
        c3 = (2.0 * travel_time * (1.0 - weight) - timestep_seconds) / denominator
        if c1 >= 0.0 and c2 >= 0.0 and c3 >= 0.0:
            return subreaches, c1, c2, c3
        subreaches += 1
    raise MuskingumCungeError(
        "no stable non-negative Muskingum-Cunge discretization exists for "
        "this reach at the requested timestep"
    )


@dataclass(frozen=True)
class CascadeSection:
    """One surveyed section of a multi-section transport reach, with the
    reference hydraulic state it is evaluated at (seepage-threaded flows
    make section order physically observable)."""

    section: TrapezoidSection
    length_m: float
    reference_flow_m3s: float


def route_step_response(
    section: TrapezoidSection,
    length_m: float,
    reference_flow_m3s: float,
    timestep_seconds: float,
    horizon_steps: int,
) -> tuple[float, ...]:
    """Outflow series for a 0 -> reference_flow step applied at t = 0."""
    return route_cascade(
        (CascadeSection(section, length_m, reference_flow_m3s),),
        step_flow_m3s=reference_flow_m3s,
        timestep_seconds=timestep_seconds,
        horizon_steps=horizon_steps,
    )


def route_cascade(
    sections: tuple[CascadeSection, ...],
    step_flow_m3s: float,
    timestep_seconds: float,
    horizon_steps: int,
) -> tuple[float, ...]:
    """Route a 0 -> step_flow step through the sections in physical order.

    Each section carries its own reference state (and hence its own
    Muskingum-Cunge coefficients); the concatenated cell chain is advanced
    one timestep at a time, so the outflow series of section i is exactly
    the inflow series of section i+1.
    """
    if not isinstance(sections, tuple) or not sections:
        raise MuskingumCungeError(
            "cascade requires at least one surveyed section"
        )
    if (
        isinstance(timestep_seconds, bool)
        or not isinstance(timestep_seconds, (int, float))
        or not math.isfinite(timestep_seconds)
        or timestep_seconds <= 0.0
    ):
        raise MuskingumCungeError("timestep must be a positive finite number")
    if not isinstance(horizon_steps, int) or horizon_steps <= 0:
        raise MuskingumCungeError("horizon_steps must be a positive integer")
    _validate_flow(step_flow_m3s)

    cell_coefficients: list[tuple[float, float, float]] = []
    for cascade_section in sections:
        if (
            isinstance(cascade_section.length_m, bool)
            or not isinstance(cascade_section.length_m, (int, float))
            or not math.isfinite(cascade_section.length_m)
            or cascade_section.length_m <= 0.0
        ):
            raise MuskingumCungeError(
                "reach length must be a positive finite number"
            )
        subreaches, c1, c2, c3 = _routing_coefficients(
            cascade_section.section,
            cascade_section.length_m,
            cascade_section.reference_flow_m3s,
            timestep_seconds,
        )
        cell_coefficients.extend([(c1, c2, c3)] * subreaches)

    cell_count = len(cell_coefficients)
    flows_previous = [0.0] * (cell_count + 1)
    outflows: list[float] = []
    for _ in range(horizon_steps):
        flows_current = [step_flow_m3s] + [0.0] * cell_count
        for index in range(1, cell_count + 1):
            c1, c2, c3 = cell_coefficients[index - 1]
            flows_current[index] = (
                c1 * flows_current[index - 1]
                + c2 * flows_previous[index - 1]
                + c3 * flows_previous[index]
            )
        outflows.append(flows_current[cell_count])
        flows_previous = flows_current

    if any(flow < 0.0 for flow in outflows):
        raise MuskingumCungeError(
            "step response produced a negative outflow; discretization is "
            "not stable"
        )
    if not math.isclose(
        outflows[-1], step_flow_m3s, rel_tol=_CONVERGENCE_REL_TOL
    ):
        raise MuskingumCungeError(
            "step response did not converge within the requested horizon"
        )
    return tuple(outflows)


def fit_t10_t90(
    outflows: tuple[float, ...] | list[float],
    reference_flow_m3s: float,
    timestep_seconds: float,
    lower_threshold: float = 0.10,
    upper_threshold: float = 0.90,
) -> tuple[float, float]:
    """First 10%/90% crossing times of the outflow step response, with
    linear interpolation between steps. Outflow index i is the end-of-step
    instantaneous outflow at time (i + 1) * timestep (the Muskingum O2
    value), so crossings interpolate between those sample instants."""
    _validate_flow(reference_flow_m3s)
    if not 0.0 < lower_threshold < upper_threshold < 1.0:
        raise MuskingumCungeError(
            "surrogate thresholds must satisfy 0 < lower < upper < 1"
        )
    crossings = []
    for threshold_fraction in (lower_threshold, upper_threshold):
        threshold = threshold_fraction * reference_flow_m3s
        crossing = None
        previous = 0.0
        for index, flow in enumerate(outflows):
            if flow >= threshold:
                span = flow - previous
                fraction = 1.0 if span <= 0.0 else (threshold - previous) / span
                crossing = (index + fraction) * timestep_seconds
                break
            previous = flow
        if crossing is None:
            raise MuskingumCungeError(
                f"outflow never reaches the {threshold_fraction:.0%} threshold "
                "within the horizon"
            )
        crossings.append(crossing)
    t10, t90 = crossings
    return t10, t90
