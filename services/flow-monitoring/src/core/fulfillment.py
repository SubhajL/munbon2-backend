"""Predicted-only section fulfillment and conservative closure decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
import math

from .network_topology import ROOT, children_of, is_spanning_tree, nodes_of

__all__ = [
    "ClosureProjection",
    "ClosureRequirement",
    "FulfillmentError",
    "PredictedDeliveryState",
    "PredictedFulfillmentStatus",
    "TransitCommitment",
    "VolumeBounds",
    "advance_predicted_delivery",
    "earliest_safe_closure",
    "usable_in_transit_volume",
]


class FulfillmentError(ValueError):
    """A predicted fulfillment value violates its fail-closed contract."""


class PredictedFulfillmentStatus(str, Enum):
    PENDING = "pending"
    ARRIVAL_PREDICTED = "arrival_predicted"
    DELIVERY_PREDICTED_ACTIVE = "delivery_predicted_active"
    PREDICTED_FULFILLED = "predicted_fulfilled"
    PREDICTED_EXCESS = "predicted_excess"


@dataclass(frozen=True)
class VolumeBounds:
    lower: float
    nominal: float
    upper: float


@dataclass(frozen=True)
class PredictedDeliveryState:
    requirement_id: str
    section_id: str
    required_volume_m3: float
    approved_excess_m3: float
    predicted_delivered_m3: float = 0.0
    usable_in_transit_m3: float = 0.0
    status: PredictedFulfillmentStatus = PredictedFulfillmentStatus.PENDING


@dataclass(frozen=True)
class TransitCommitment:
    commitment_id: str
    requirement_id: str
    committed_at: datetime
    arrives_at: datetime
    usable_volume_m3: VolumeBounds


@dataclass(frozen=True)
class ClosureRequirement:
    requirement_id: str
    delivery_node_id: str
    required_volume_m3: float
    approved_excess_m3: float
    required_by: datetime


@dataclass(frozen=True)
class ClosureProjection:
    closes_at: datetime
    requirement_id: str
    delivered_volume_m3: VolumeBounds
    transit_commitments: tuple[TransitCommitment, ...] = ()


def advance_predicted_delivery(
    state: PredictedDeliveryState,
    delivered_delta_m3: float,
    in_transit_m3: float,
) -> PredictedDeliveryState:
    _validate_delivery_state(state)
    _validate_non_negative(delivered_delta_m3, "delivered_delta_m3")
    _validate_non_negative(in_transit_m3, "in_transit_m3")
    delivered_m3 = state.predicted_delivered_m3 + delivered_delta_m3
    projected_m3 = delivered_m3 + in_transit_m3
    approved_maximum_m3 = state.required_volume_m3 + state.approved_excess_m3
    if projected_m3 > approved_maximum_m3:
        status = PredictedFulfillmentStatus.PREDICTED_EXCESS
    elif delivered_m3 >= state.required_volume_m3:
        status = PredictedFulfillmentStatus.PREDICTED_FULFILLED
    elif delivered_m3 > 0.0:
        status = PredictedFulfillmentStatus.DELIVERY_PREDICTED_ACTIVE
    elif in_transit_m3 > 0.0:
        status = PredictedFulfillmentStatus.ARRIVAL_PREDICTED
    else:
        status = PredictedFulfillmentStatus.PENDING
    return replace(
        state,
        predicted_delivered_m3=delivered_m3,
        usable_in_transit_m3=in_transit_m3,
        status=status,
    )


def usable_in_transit_volume(
    commitments: tuple[TransitCommitment, ...],
    requirement_id: str,
    closes_at: datetime,
    required_by: datetime,
) -> VolumeBounds:
    if not isinstance(commitments, tuple):
        raise FulfillmentError("commitments must be an immutable tuple")
    _validate_non_blank(requirement_id, "requirement_id")
    _validate_aware(closes_at, "closes_at")
    _validate_aware(required_by, "required_by")
    total = VolumeBounds(0.0, 0.0, 0.0)
    for commitment in commitments:
        _validate_commitment(commitment)
        if (
            commitment.requirement_id == requirement_id
            and commitment.committed_at <= closes_at
            and closes_at < commitment.arrives_at <= required_by
        ):
            total = VolumeBounds(
                total.lower + commitment.usable_volume_m3.lower,
                total.nominal + commitment.usable_volume_m3.nominal,
                total.upper + commitment.usable_volume_m3.upper,
            )
    return total


def earliest_safe_closure(
    closing_gate_id: str,
    network_edges: tuple[tuple[str, str], ...],
    requirements: tuple[ClosureRequirement, ...],
    projections: tuple[ClosureProjection, ...],
) -> datetime | None:
    requirements_by_id = _requirements_by_id(requirements)
    projections_by_time = _projections_by_time(projections, requirements_by_id)
    expected_ids = _descendant_requirement_ids(
        closing_gate_id, network_edges, requirements_by_id
    )
    if not expected_ids:
        return None
    for closes_at in sorted(projections_by_time):
        at_time = {
            requirement_id: projection
            for requirement_id, projection in projections_by_time[closes_at].items()
            if requirement_id in expected_ids
        }
        if set(at_time) != expected_ids:
            raise FulfillmentError(
                f"closure projection coverage must equal {sorted(expected_ids)!r}"
            )
        descendant_requirements = {
            requirement_id: requirements_by_id[requirement_id]
            for requirement_id in expected_ids
        }
        if _all_requirements_safe(descendant_requirements, at_time, closes_at):
            return closes_at
    return None


def _requirements_by_id(
    requirements: tuple[ClosureRequirement, ...],
) -> dict[str, ClosureRequirement]:
    if not isinstance(requirements, tuple) or not requirements:
        raise FulfillmentError("requirements must be a non-empty immutable tuple")
    indexed = {}
    for requirement in requirements:
        _validate_closure_requirement(requirement)
        if requirement.requirement_id in indexed:
            raise FulfillmentError("requirements contains duplicate requirement_id")
        indexed[requirement.requirement_id] = requirement
    return indexed


def _descendant_requirement_ids(
    closing_gate_id: str,
    network_edges: tuple[tuple[str, str], ...],
    requirements_by_id: dict[str, ClosureRequirement],
) -> set[str]:
    _validate_non_blank(closing_gate_id, "closing_gate_id")
    if not isinstance(network_edges, tuple) or not network_edges:
        raise FulfillmentError("network_edges must be a non-empty immutable tuple")
    if not all(
        isinstance(edge, tuple)
        and len(edge) == 2
        and all(isinstance(node, str) and node.strip() for node in edge)
        for edge in network_edges
    ) or not is_spanning_tree(network_edges, ROOT):
        raise FulfillmentError("network_edges must form a rooted spanning tree")
    network_nodes = nodes_of(network_edges)
    if closing_gate_id == ROOT or closing_gate_id not in network_nodes:
        raise FulfillmentError("closing_gate_id must identify a canal gate")
    unknown_delivery_nodes = {
        requirement.delivery_node_id
        for requirement in requirements_by_id.values()
        if requirement.delivery_node_id not in network_nodes
        or requirement.delivery_node_id == ROOT
    }
    if unknown_delivery_nodes:
        raise FulfillmentError(
            "closure requirements contain unknown delivery nodes "
            f"{sorted(unknown_delivery_nodes)!r}"
        )

    descendants = set()
    pending = [closing_gate_id]
    children = children_of(network_edges)
    while pending:
        node_id = pending.pop()
        if node_id in descendants:
            continue
        descendants.add(node_id)
        pending.extend(children.get(node_id, ()))
    return {
        requirement_id
        for requirement_id, requirement in requirements_by_id.items()
        if requirement.delivery_node_id in descendants
    }


def _projections_by_time(
    projections: tuple[ClosureProjection, ...],
    requirements_by_id: dict[str, ClosureRequirement],
) -> dict[datetime, dict[str, ClosureProjection]]:
    if not isinstance(projections, tuple):
        raise FulfillmentError("projections must be an immutable tuple")
    indexed: dict[datetime, dict[str, ClosureProjection]] = {}
    for projection in projections:
        _validate_aware(projection.closes_at, "projection.closes_at")
        _validate_non_blank(projection.requirement_id, "projection.requirement_id")
        _validate_bounds(projection.delivered_volume_m3, "delivered_volume_m3")
        if projection.requirement_id not in requirements_by_id:
            raise FulfillmentError(
                f"projection contains unknown requirement_id {projection.requirement_id!r}"
            )
        at_time = indexed.setdefault(projection.closes_at, {})
        if projection.requirement_id in at_time:
            raise FulfillmentError(
                "projections contains duplicate requirement coverage"
            )
        at_time[projection.requirement_id] = projection
    return indexed


def _all_requirements_safe(
    requirements_by_id: dict[str, ClosureRequirement],
    projections_by_id: dict[str, ClosureProjection],
    closes_at: datetime,
) -> bool:
    commitment_ids = [
        commitment.commitment_id
        for projection in projections_by_id.values()
        for commitment in projection.transit_commitments
    ]
    if len(commitment_ids) != len(set(commitment_ids)):
        raise FulfillmentError(
            "closure projections contain a duplicate commitment allocation"
        )
    for requirement_id, requirement in requirements_by_id.items():
        projection = projections_by_id[requirement_id]
        if any(
            commitment.requirement_id != requirement_id
            for commitment in projection.transit_commitments
        ):
            raise FulfillmentError(
                "closure projection contains a commitment for another requirement"
            )
        tail = usable_in_transit_volume(
            projection.transit_commitments,
            requirement_id,
            closes_at,
            requirement.required_by,
        )
        lower_total_m3 = projection.delivered_volume_m3.lower + tail.lower
        upper_total_m3 = projection.delivered_volume_m3.upper + tail.upper
        if (
            lower_total_m3 < requirement.required_volume_m3
            or upper_total_m3
            > requirement.required_volume_m3 + requirement.approved_excess_m3
        ):
            return False
    return True


def _validate_delivery_state(state: PredictedDeliveryState) -> None:
    _validate_non_blank(state.requirement_id, "state.requirement_id")
    _validate_non_blank(state.section_id, "state.section_id")
    _validate_positive(state.required_volume_m3, "state.required_volume_m3")
    _validate_non_negative(state.approved_excess_m3, "state.approved_excess_m3")
    _validate_non_negative(state.predicted_delivered_m3, "state.predicted_delivered_m3")
    _validate_non_negative(state.usable_in_transit_m3, "state.usable_in_transit_m3")
    if not isinstance(state.status, PredictedFulfillmentStatus):
        raise FulfillmentError("state.status must be a PredictedFulfillmentStatus")


def _validate_commitment(commitment: TransitCommitment) -> None:
    _validate_non_blank(commitment.commitment_id, "commitment.commitment_id")
    _validate_non_blank(commitment.requirement_id, "commitment.requirement_id")
    _validate_aware(commitment.committed_at, "commitment.committed_at")
    _validate_aware(commitment.arrives_at, "commitment.arrives_at")
    if commitment.arrives_at < commitment.committed_at:
        raise FulfillmentError("commitment arrives_at must not precede committed_at")
    _validate_bounds(commitment.usable_volume_m3, "commitment.usable_volume_m3")


def _validate_closure_requirement(requirement: ClosureRequirement) -> None:
    _validate_non_blank(requirement.requirement_id, "requirement.requirement_id")
    _validate_non_blank(requirement.delivery_node_id, "requirement.delivery_node_id")
    _validate_positive(requirement.required_volume_m3, "requirement.required_volume_m3")
    _validate_non_negative(
        requirement.approved_excess_m3, "requirement.approved_excess_m3"
    )
    _validate_aware(requirement.required_by, "requirement.required_by")


def _validate_bounds(bounds: VolumeBounds, label: str) -> None:
    for member in ("lower", "nominal", "upper"):
        _validate_non_negative(getattr(bounds, member), f"{label}.{member}")
    if not bounds.lower <= bounds.nominal <= bounds.upper:
        raise FulfillmentError(
            f"{label} bounds must be ordered lower <= nominal <= upper"
        )


def _validate_non_blank(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FulfillmentError(f"{label} must be a non-empty string")


def _validate_aware(value: datetime, label: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise FulfillmentError(f"{label} must be timezone-aware")


def _validate_number(value: float, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise FulfillmentError(f"{label} must be a finite number")


def _validate_non_negative(value: float, label: str) -> None:
    _validate_number(value, label)
    if value < 0.0:
        raise FulfillmentError(f"{label} must be >= 0")


def _validate_positive(value: float, label: str) -> None:
    _validate_number(value, label)
    if value <= 0.0:
        raise FulfillmentError(f"{label} must be > 0")
