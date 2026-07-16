"""Pure causal lag-and-dispersion routing for one canal reach."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model_release import HydraulicModelRelease, ParameterDistribution

__all__ = [
    "ReachResponse",
    "ReachResponseError",
    "ReachState",
    "ResponseMember",
    "TransitVolume",
    "reach_responses_from_model_release",
    "route_reach_step",
    "validate_reach_response",
]

_MASS_BALANCE_ABS_TOLERANCE_M3 = 1e-8


class ReachResponseError(ValueError):
    """A reach response or routing step violates its physical contract."""


class ResponseMember(str, Enum):
    LOWER = "lower"
    NOMINAL = "nominal"
    UPPER = "upper"


@dataclass(frozen=True)
class ReachResponse:
    model_release_id: str
    reach_id: str
    member: ResponseMember
    delay_seconds: float
    loss_fraction: float
    dispersion_seconds: float
    capacity_m3s: float
    minimum_timestep_seconds: float
    maximum_timestep_seconds: float


@dataclass(frozen=True)
class TransitVolume:
    remaining_volume_m3: float
    remaining_delay_seconds: float
    remaining_release_seconds: float


@dataclass(frozen=True)
class ReachState:
    model_release_id: str
    reach_id: str
    member: ResponseMember
    transit_volumes: tuple[TransitVolume, ...] = ()
    initial_volume_m3: float = 0.0
    cumulative_inflow_m3: float = 0.0
    cumulative_outflow_m3: float = 0.0
    cumulative_withdrawal_m3: float = 0.0
    cumulative_declared_loss_m3: float = 0.0
    cumulative_operational_loss_m3: float = 0.0
    outflow_m3s: float = 0.0

    @property
    def in_transit_volume_m3(self) -> float:
        return sum(packet.remaining_volume_m3 for packet in self.transit_volumes)


def validate_reach_response(response: ReachResponse) -> None:
    _validate_non_blank(response.model_release_id, "model_release_id")
    _validate_non_blank(response.reach_id, "reach_id")
    if not isinstance(response.member, ResponseMember):
        raise ReachResponseError("member must be a ResponseMember")
    _validate_non_negative(response.delay_seconds, "delay_seconds")
    _validate_non_negative(response.loss_fraction, "loss_fraction")
    if response.loss_fraction >= 1.0:
        raise ReachResponseError("loss_fraction must be < 1")
    _validate_non_negative(response.dispersion_seconds, "dispersion_seconds")
    _validate_positive(response.capacity_m3s, "capacity_m3s")
    _validate_positive(response.minimum_timestep_seconds, "minimum_timestep_seconds")
    _validate_positive(response.maximum_timestep_seconds, "maximum_timestep_seconds")
    if response.maximum_timestep_seconds < response.minimum_timestep_seconds:
        raise ReachResponseError(
            "maximum_timestep_seconds must be >= minimum_timestep_seconds"
        )


def reach_responses_from_model_release(
    release: "HydraulicModelRelease",
) -> tuple[ReachResponse, ...]:
    responses = []
    for parameters in sorted(
        release.reach_parameters, key=lambda parameters: parameters.reach_id
    ):
        for member in ResponseMember:
            response = ReachResponse(
                model_release_id=release.release_id,
                reach_id=parameters.reach_id,
                member=member,
                delay_seconds=_distribution_member(parameters.delay_seconds, member),
                loss_fraction=_distribution_member(parameters.loss_fraction, member),
                dispersion_seconds=_distribution_member(
                    parameters.dispersion_seconds, member
                ),
                capacity_m3s=_distribution_member(parameters.capacity_m3s, member),
                minimum_timestep_seconds=(
                    release.operating_envelope.minimum_timestep_seconds
                ),
                maximum_timestep_seconds=(
                    release.operating_envelope.maximum_timestep_seconds
                ),
            )
            validate_reach_response(response)
            dry_state = ReachState(
                model_release_id=response.model_release_id,
                reach_id=response.reach_id,
                member=response.member,
            )
            route_reach_step(
                response,
                dry_state,
                inflow_m3s=0.0,
                dt_s=response.minimum_timestep_seconds,
            )
            responses.append(response)
    return tuple(responses)


def route_reach_step(
    response: ReachResponse,
    state: ReachState,
    inflow_m3s: float,
    dt_s: float,
    withdrawal_m3s: float = 0.0,
    operational_loss_m3s: float = 0.0,
) -> ReachState:
    validate_reach_response(response)
    _validate_state(state)
    _validate_state_lineage(response, state)
    _validate_non_negative(inflow_m3s, "inflow_m3s")
    _validate_non_negative(withdrawal_m3s, "withdrawal_m3s")
    _validate_non_negative(operational_loss_m3s, "operational_loss_m3s")
    _validate_positive(dt_s, "dt_s")
    if (
        not response.minimum_timestep_seconds
        <= dt_s
        <= response.maximum_timestep_seconds
    ):
        raise ReachResponseError(
            f"timestep {dt_s} is outside response envelope "
            f"[{response.minimum_timestep_seconds}, {response.maximum_timestep_seconds}]"
        )
    if inflow_m3s > response.capacity_m3s:
        raise ReachResponseError(
            f"inflow_m3s {inflow_m3s} exceeds reach capacity {response.capacity_m3s}"
        )

    inflow_volume_m3 = inflow_m3s * dt_s
    declared_loss_m3 = inflow_volume_m3 * response.loss_fraction
    admitted_volume_m3 = inflow_volume_m3 - declared_loss_m3
    packets = list(state.transit_volumes)
    if admitted_volume_m3 > 0.0:
        packets.append(
            TransitVolume(
                remaining_volume_m3=admitted_volume_m3,
                remaining_delay_seconds=response.delay_seconds,
                remaining_release_seconds=response.dispersion_seconds,
            )
        )

    routed_volume_m3 = 0.0
    remaining_packets = []
    for packet in packets:
        released_m3, remaining = _advance_transit_volume(packet, dt_s)
        routed_volume_m3 += released_m3
        if remaining is not None:
            remaining_packets.append(remaining)

    capacity_volume_m3 = response.capacity_m3s * dt_s
    if routed_volume_m3 > capacity_volume_m3 + _mass_tolerance(capacity_volume_m3):
        raise ReachResponseError(
            f"routed volume {routed_volume_m3} exceeds reach capacity for timestep"
        )
    withdrawal_volume_m3 = withdrawal_m3s * dt_s
    operational_loss_volume_m3 = operational_loss_m3s * dt_s
    removed_volume_m3 = withdrawal_volume_m3 + operational_loss_volume_m3
    if routed_volume_m3 + _mass_tolerance(routed_volume_m3) < removed_volume_m3:
        raise ReachResponseError(
            "withdrawal and operational loss exceed routed volume for timestep"
        )
    outflow_volume_m3 = max(0.0, routed_volume_m3 - removed_volume_m3)

    next_state = ReachState(
        model_release_id=state.model_release_id,
        reach_id=state.reach_id,
        member=state.member,
        transit_volumes=tuple(remaining_packets),
        initial_volume_m3=state.initial_volume_m3,
        cumulative_inflow_m3=state.cumulative_inflow_m3 + inflow_volume_m3,
        cumulative_outflow_m3=state.cumulative_outflow_m3 + outflow_volume_m3,
        cumulative_withdrawal_m3=(
            state.cumulative_withdrawal_m3 + withdrawal_volume_m3
        ),
        cumulative_declared_loss_m3=(
            state.cumulative_declared_loss_m3 + declared_loss_m3
        ),
        cumulative_operational_loss_m3=(
            state.cumulative_operational_loss_m3 + operational_loss_volume_m3
        ),
        outflow_m3s=outflow_volume_m3 / dt_s,
    )
    _validate_state(next_state)
    return next_state


def _advance_transit_volume(
    packet: TransitVolume, dt_s: float
) -> tuple[float, TransitVolume | None]:
    if packet.remaining_delay_seconds >= dt_s:
        return 0.0, TransitVolume(
            remaining_volume_m3=packet.remaining_volume_m3,
            remaining_delay_seconds=packet.remaining_delay_seconds - dt_s,
            remaining_release_seconds=packet.remaining_release_seconds,
        )

    active_seconds = dt_s - packet.remaining_delay_seconds
    if packet.remaining_release_seconds == 0.0:
        return packet.remaining_volume_m3, None

    release_seconds = min(active_seconds, packet.remaining_release_seconds)
    released_m3 = (
        packet.remaining_volume_m3 * release_seconds / packet.remaining_release_seconds
    )
    remaining_release_seconds = packet.remaining_release_seconds - release_seconds
    if remaining_release_seconds == 0.0:
        return packet.remaining_volume_m3, None
    return released_m3, TransitVolume(
        remaining_volume_m3=packet.remaining_volume_m3 - released_m3,
        remaining_delay_seconds=0.0,
        remaining_release_seconds=remaining_release_seconds,
    )


def _validate_state(state: ReachState) -> None:
    _validate_non_blank(state.model_release_id, "state.model_release_id")
    _validate_non_blank(state.reach_id, "state.reach_id")
    if not isinstance(state.member, ResponseMember):
        raise ReachResponseError("state.member must be a ResponseMember")
    if not isinstance(state.transit_volumes, tuple):
        raise ReachResponseError("state.transit_volumes must be an immutable tuple")
    quantities = (
        ("state.initial_volume_m3", state.initial_volume_m3),
        ("state.cumulative_inflow_m3", state.cumulative_inflow_m3),
        ("state.cumulative_outflow_m3", state.cumulative_outflow_m3),
        ("state.cumulative_withdrawal_m3", state.cumulative_withdrawal_m3),
        ("state.cumulative_declared_loss_m3", state.cumulative_declared_loss_m3),
        (
            "state.cumulative_operational_loss_m3",
            state.cumulative_operational_loss_m3,
        ),
        ("state.outflow_m3s", state.outflow_m3s),
    )
    for label, value in quantities:
        _validate_non_negative(value, label)
    for packet in state.transit_volumes:
        _validate_positive(packet.remaining_volume_m3, "transit.remaining_volume_m3")
        _validate_non_negative(
            packet.remaining_delay_seconds, "transit.remaining_delay_seconds"
        )
        _validate_non_negative(
            packet.remaining_release_seconds, "transit.remaining_release_seconds"
        )

    supplied_m3 = state.initial_volume_m3 + state.cumulative_inflow_m3
    accounted_m3 = (
        state.cumulative_outflow_m3
        + state.cumulative_withdrawal_m3
        + state.cumulative_declared_loss_m3
        + state.cumulative_operational_loss_m3
        + state.in_transit_volume_m3
    )
    if not math.isclose(
        supplied_m3,
        accounted_m3,
        rel_tol=1e-12,
        abs_tol=_MASS_BALANCE_ABS_TOLERANCE_M3,
    ):
        raise ReachResponseError(
            f"state mass balance is broken: supplied={supplied_m3}, accounted={accounted_m3}"
        )


def _validate_state_lineage(response: ReachResponse, state: ReachState) -> None:
    for field in ("model_release_id", "reach_id", "member"):
        if getattr(state, field) != getattr(response, field):
            raise ReachResponseError(f"state {field} does not match response")


def _distribution_member(
    distribution: "ParameterDistribution", member: ResponseMember
) -> float:
    return float(getattr(distribution, member.value))


def _validate_non_blank(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ReachResponseError(f"{label} must be a non-empty string")


def _validate_finite(value: float, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ReachResponseError(f"{label} must be a finite number")


def _validate_non_negative(value: float, label: str) -> None:
    _validate_finite(value, label)
    if value < 0.0:
        raise ReachResponseError(f"{label} must be >= 0")


def _validate_positive(value: float, label: str) -> None:
    _validate_finite(value, label)
    if value <= 0.0:
        raise ReachResponseError(f"{label} must be > 0")


def _mass_tolerance(volume_m3: float) -> float:
    return max(_MASS_BALANCE_ABS_TOLERANCE_M3, abs(volume_m3) * 1e-12)
