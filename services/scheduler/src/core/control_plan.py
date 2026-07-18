"""Pure control-plan draft composition (PR 4.3a).

No I/O: canonical serialization, content-hash identity, snapshot-topology
derivations, optimizer-problem composition, and prediction-request
construction. All failure paths raise a typed exception so the API layer can
map them to honest status codes instead of inventing defaults.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Collection, Mapping, Sequence

from algorithms.hydraulic_schedule_optimizer import (
    DeliveryObligation,
    GateEventKind,
    GatePlanEvent,
    GatePulseDuty,
    LimitedAdjustmentPlan,
    LimitedAdjustmentProblem,
    ModelOperatingEnvelope,
    QuantizedFlowCandidate,
    ReachCapacity,
    TimeWindow,
)

INPUT_HASH_PREFIX = "scheduler:control-plan-input:v1\n"
DRAFT_HASH_PREFIX = "scheduler:control-plan-draft:v1\n"

_MEMBER_NAMES = ("lower", "nominal", "upper")
_ROOT_NODE_ID = "S"
_TRANSPORT_ROLE = "transport"
_BRANCH_ROLE = "branch_structure"
_WITHDRAWAL_ROLE = "withdrawal_structure"
_MAX_SERVICE_DATE_OFFSET_DAYS = 6


class ControlPlanError(ValueError):
    """Base for all control-plan composition failures."""


class DraftInputError(ControlPlanError):
    """The caller's draft request cannot be composed into a valid problem."""


class UpstreamContractError(ControlPlanError):
    """An upstream payload violates its documented contract."""


class InternalPlanInvariantError(ControlPlanError):
    """A shipped-component invariant broke; this is a bug, not caller error."""


def _reject_non_string_keys(payload: Any) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"canonical JSON keys must be strings, got {key!r}"
                )
            _reject_non_string_keys(value)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            _reject_non_string_keys(value)


def canonical_json_text(payload: Any) -> str:
    # json.dumps would silently coerce non-string keys, letting two different
    # payloads collide in the content hash.
    _reject_non_string_keys(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DraftInputError("datetimes must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _hash_with_prefix(prefix: str, document: Mapping[str, Any]) -> str:
    text = prefix + canonical_json_text(document)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def control_plan_input_hash(document: Mapping[str, Any]) -> str:
    return _hash_with_prefix(INPUT_HASH_PREFIX, document)


def control_plan_draft_hash(document: Mapping[str, Any]) -> str:
    return _hash_with_prefix(DRAFT_HASH_PREFIX, document)


def build_parent_elements(
    routing_elements: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Index elements by downstream node; a routed tree has one inflow per node."""
    parents: dict[str, Mapping[str, Any]] = {}
    for element in routing_elements:
        downstream = element["downstream_node_id"]
        if downstream in parents:
            raise UpstreamContractError(
                f"routing topology gives node {downstream!r} more than one "
                "incoming element; a routed tree must have exactly one"
            )
        parents[downstream] = element
    return parents


def derive_path_reach_ids(
    parent_by_node: Mapping[str, Mapping[str, Any]],
    delivery_node_id: str,
) -> tuple[str, ...]:
    if delivery_node_id == _ROOT_NODE_ID:
        raise DraftInputError("delivery node must not be the source node 'S'")
    if delivery_node_id not in parent_by_node:
        raise DraftInputError(
            f"delivery node {delivery_node_id!r} does not exist in the model "
            "routing topology"
        )
    reach_ids: list[str] = []
    visited: set[str] = set()
    node = delivery_node_id
    while node != _ROOT_NODE_ID:
        if node in visited:
            raise UpstreamContractError(
                f"routing topology contains a cycle through node {node!r}"
            )
        visited.add(node)
        element = parent_by_node.get(node)
        if element is None:
            raise UpstreamContractError(
                f"node {node!r} is disconnected from the source in the "
                "routing topology"
            )
        if element["role"] == _TRANSPORT_ROLE:
            reach_ids.append(element["element_id"])
        node = element["upstream_node_id"]
    return tuple(reversed(reach_ids))


def index_response_members(
    response_members: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    members: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in response_members:
        reach_id = row["reach_id"]
        member = row["member"]
        if member not in _MEMBER_NAMES:
            raise UpstreamContractError(
                f"unknown response member {member!r} for reach {reach_id!r}"
            )
        per_reach = members.setdefault(reach_id, {})
        if member in per_reach:
            raise UpstreamContractError(
                f"duplicate response member {member!r} for reach {reach_id!r}"
            )
        per_reach[member] = row
    return members


def _complete_members_for_reach(
    members_by_reach: Mapping[str, Mapping[str, Mapping[str, Any]]],
    reach_id: str,
) -> Mapping[str, Mapping[str, Any]]:
    per_reach = members_by_reach.get(reach_id)
    if per_reach is None or set(per_reach) != set(_MEMBER_NAMES):
        raise UpstreamContractError(
            f"reach {reach_id!r} does not carry all three response members"
        )
    return per_reach


def derive_travel_delay_seconds(
    members_by_reach: Mapping[str, Mapping[str, Mapping[str, Any]]],
    path_reach_ids: Sequence[str],
    model_step_seconds: int,
) -> int:
    total = 0.0
    for reach_id in path_reach_ids:
        per_reach = _complete_members_for_reach(members_by_reach, reach_id)
        total += max(float(row["delay_seconds"]) for row in per_reach.values())
    if total == 0.0:
        return 0
    return int(math.ceil(total / model_step_seconds)) * model_step_seconds


def derive_reach_capacities(
    members_by_reach: Mapping[str, Mapping[str, Mapping[str, Any]]],
    used_reach_ids: Collection[str],
) -> tuple[ReachCapacity, ...]:
    capacities = []
    for reach_id in sorted(set(used_reach_ids)):
        per_reach = _complete_members_for_reach(members_by_reach, reach_id)
        capacities.append(
            ReachCapacity(
                reach_id=reach_id,
                maximum_flow_m3s=min(
                    float(row["capacity_m3s"]) for row in per_reach.values()
                ),
            )
        )
    return tuple(capacities)


def derive_delivery_fractions(
    members_by_reach: Mapping[str, Mapping[str, Mapping[str, Any]]],
    path_reach_ids: Sequence[str],
) -> tuple[float, float]:
    products = []
    for member in _MEMBER_NAMES:
        product = 1.0
        for reach_id in path_reach_ids:
            per_reach = _complete_members_for_reach(members_by_reach, reach_id)
            loss = float(per_reach[member]["loss_fraction"])
            if not 0.0 <= loss < 1.0:
                raise UpstreamContractError(
                    f"reach {reach_id!r} member {member!r} loss fraction "
                    f"{loss} is outside [0, 1)"
                )
            product *= 1.0 - loss
        products.append(product)
    minimum, maximum = min(products), max(products)
    if minimum <= 0.0:
        raise DraftInputError(
            "delivery path loses all water in at least one response member"
        )
    return minimum, maximum


def _window(mapping: Mapping[str, Any], name: str) -> TimeWindow:
    starts_at = mapping["starts_at"]
    ends_at = mapping["ends_at"]
    if not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime):
        raise DraftInputError(f"{name} bounds must be datetimes")
    return TimeWindow(starts_at=starts_at, ends_at=ends_at)


def _is_step_aligned(
    instant: datetime, starts_at: datetime, model_step_seconds: int
) -> bool:
    offset = (instant - starts_at).total_seconds()
    return offset % model_step_seconds == 0


def validate_branch_allocations(
    routing_elements: Sequence[Mapping[str, Any]],
    branch_allocations: Sequence[Mapping[str, Any]],
) -> None:
    """Reproduce flow's network-wide branch-allocation contract before optimize.

    Flow requires every branching node (a non-withdrawal node with more than one
    child) to have all its children covered and its sibling fractions sum to
    exactly 1. Enforcing it here turns a caller mistake into a 422 instead of a
    prediction-time 400 mis-mapped to 500.
    """
    children: dict[str, list[str]] = {}
    for element in routing_elements:
        if element["role"] == _WITHDRAWAL_ROLE:
            continue
        children.setdefault(element["upstream_node_id"], []).append(
            element["downstream_node_id"]
        )
    branch_nodes = {
        upstream
        for upstream, downstreams in children.items()
        if len(downstreams) > 1
    }
    seen: set[tuple[str, str]] = set()
    fractions: dict[str, float] = {}
    for allocation in branch_allocations:
        edge = (allocation["upstream_node_id"], allocation["downstream_node_id"])
        if edge in seen:
            raise DraftInputError(f"duplicate branch allocation edge {edge}")
        seen.add(edge)
        upstream, downstream = edge
        if upstream not in branch_nodes or downstream not in children.get(
            upstream, []
        ):
            raise DraftInputError(
                f"branch allocation {edge} is not a branching-node edge in the "
                "model topology"
            )
        fraction = float(allocation["fraction"])
        if fraction < 0.0:
            raise DraftInputError(
                f"branch allocation {edge} fraction {fraction} is negative"
            )
        fractions[edge] = fraction
    for upstream in sorted(branch_nodes):
        expected = {(upstream, child) for child in children[upstream]}
        actual = {edge for edge in fractions if edge[0] == upstream}
        if actual != expected or not math.isclose(
            sum(fractions[edge] for edge in expected),
            1.0,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise DraftInputError(
                f"branch allocations for node {upstream!r} must cover every "
                "child and sum to 1"
            )


def validate_operator_withdrawals(
    operator_withdrawals: Sequence[Mapping[str, Any]],
    routing_elements: Sequence[Mapping[str, Any]],
    horizon_start: datetime,
    horizon_end: datetime,
    model_step_seconds: int,
) -> None:
    """Enforce flow's withdrawal-event contract before the prediction call."""
    withdrawal_nodes = {
        element["downstream_node_id"]
        for element in routing_elements
        if element["role"] == _WITHDRAWAL_ROLE
    }
    seen: set[tuple[str, datetime]] = set()
    for event in operator_withdrawals:
        structure_id = event["structure_id"]
        effective_at = event["effective_at"]
        if structure_id not in withdrawal_nodes:
            raise DraftInputError(
                f"withdrawal structure {structure_id!r} is not a withdrawal "
                "structure in the model topology"
            )
        if not horizon_start <= effective_at < horizon_end:
            raise DraftInputError(
                f"withdrawal event for {structure_id!r} at "
                f"{effective_at.isoformat()} is outside the draft horizon"
            )
        if not _is_step_aligned(effective_at, horizon_start, model_step_seconds):
            raise DraftInputError(
                f"withdrawal event for {structure_id!r} at "
                f"{effective_at.isoformat()} is not aligned to the model step"
            )
        key = (structure_id, effective_at)
        if key in seen:
            raise DraftInputError(
                f"duplicate withdrawal event for {structure_id!r} at "
                f"{effective_at.isoformat()}"
            )
        seen.add(key)


def build_limited_adjustment_problem(
    *,
    snapshot_id: str,
    routing_elements: Sequence[Mapping[str, Any]],
    response_members: Sequence[Mapping[str, Any]],
    operating_envelope: Mapping[str, Any],
    unavailable_reach_ids: Collection[str],
    requirement_items: Sequence[Mapping[str, Any]],
    section_bindings: Mapping[str, Mapping[str, Any]],
    requirement_policies: Mapping[str, Mapping[str, Any]],
    flow_candidates: Sequence[Mapping[str, Any]],
    pulse_duties: Sequence[Mapping[str, Any]],
    branch_allocations: Sequence[Mapping[str, Any]],
    operator_withdrawals: Sequence[Mapping[str, Any]],
    horizon_start: datetime,
    horizon_end: datetime,
    model_step_seconds: int,
) -> tuple[LimitedAdjustmentProblem, dict[str, Any]]:
    """Compose the optimizer problem and its canonical derived document."""
    parent_by_node = build_parent_elements(routing_elements)
    members_by_reach = index_response_members(response_members)
    unavailable = set(unavailable_reach_ids)

    horizon_seconds = (horizon_end - horizon_start).total_seconds()
    if horizon_seconds <= 0 or horizon_seconds % model_step_seconds != 0:
        raise DraftInputError(
            "draft horizon must be a positive whole number of model steps"
        )
    if horizon_seconds > float(operating_envelope["maximum_horizon_seconds"]):
        raise DraftInputError(
            "draft horizon exceeds the model operating envelope"
        )

    validate_branch_allocations(routing_elements, branch_allocations)
    validate_operator_withdrawals(
        operator_withdrawals,
        routing_elements,
        horizon_start,
        horizon_end,
        model_step_seconds,
    )
    for duty in pulse_duties:
        if (
            int(duty["minimum_open_seconds"]) % model_step_seconds != 0
            or int(duty["maximum_open_seconds"]) % model_step_seconds != 0
        ):
            raise DraftInputError(
                f"pulse duty for gate {duty['gate_id']!r} bounds must be whole "
                "model-step multiples"
            )

    positive_items = [
        item for item in requirement_items if item["required_volume_m3"] > 0.0
    ]
    zero_ids = sorted(
        item["requirement_id"]
        for item in requirement_items
        if item["required_volume_m3"] <= 0.0
    )
    if not positive_items:
        raise DraftInputError(
            "no positive-volume requirement exists; nothing to plan"
        )

    positive_sections = {item["section_id"] for item in positive_items}
    positive_ids = {item["requirement_id"] for item in positive_items}
    missing_bindings = sorted(positive_sections - set(section_bindings))
    if missing_bindings:
        raise DraftInputError(
            f"sections without a delivery binding: {missing_bindings}"
        )
    orphan_bindings = sorted(set(section_bindings) - positive_sections)
    if orphan_bindings:
        raise DraftInputError(
            f"bindings for sections with no positive requirement: {orphan_bindings}"
        )
    missing_policies = sorted(positive_ids - set(requirement_policies))
    if missing_policies:
        raise DraftInputError(
            f"positive requirements without a policy: {missing_policies}"
        )
    orphan_policies = sorted(set(requirement_policies) - positive_ids)
    if orphan_policies:
        raise DraftInputError(
            f"policies for unknown or zero requirements: {orphan_policies}"
        )

    envelope = ModelOperatingEnvelope(
        minimum_flow_m3s=float(operating_envelope["minimum_flow_m3s"]),
        maximum_flow_m3s=float(operating_envelope["maximum_flow_m3s"]),
        minimum_timestep_seconds=float(
            operating_envelope["minimum_timestep_seconds"]
        ),
        maximum_timestep_seconds=float(
            operating_envelope["maximum_timestep_seconds"]
        ),
        maximum_horizon_seconds=float(
            operating_envelope["maximum_horizon_seconds"]
        ),
    )

    last_service_date = horizon_start.date() + timedelta(
        days=_MAX_SERVICE_DATE_OFFSET_DAYS
    )

    obligations: list[DeliveryObligation] = []
    derived_obligations: list[dict[str, Any]] = []
    used_reach_ids: set[str] = set()
    for item in sorted(positive_items, key=lambda entry: entry["requirement_id"]):
        requirement_id = item["requirement_id"]
        binding = section_bindings[item["section_id"]]
        policy = requirement_policies[requirement_id]
        if not (
            horizon_start <= item["window_start"] < item["window_end"] <= horizon_end
        ):
            raise DraftInputError(
                f"requirement {requirement_id!r} delivery window must lie "
                "entirely within the draft horizon"
            )
        for boundary in (item["window_start"], item["window_end"]):
            if not _is_step_aligned(boundary, horizon_start, model_step_seconds):
                raise DraftInputError(
                    f"requirement {requirement_id!r} delivery window boundary "
                    f"{boundary.isoformat()} is not aligned to the model step"
                )
        if not horizon_start.date() <= item["service_date"] <= last_service_date:
            raise DraftInputError(
                f"requirement {requirement_id!r} service_date "
                f"{item['service_date']} is outside the horizon's D..D+6 window"
            )
        delivery_node_id = binding["delivery_node_id"]
        path = derive_path_reach_ids(parent_by_node, delivery_node_id)
        blocked = sorted(set(path) & unavailable)
        if blocked:
            raise DraftInputError(
                f"requirement {requirement_id!r} path crosses unavailable "
                f"transport reaches {blocked}"
            )
        used_reach_ids.update(path)
        travel_delay = derive_travel_delay_seconds(
            members_by_reach, path, model_step_seconds
        )
        minimum_fraction, maximum_fraction = derive_delivery_fractions(
            members_by_reach, path
        )
        rotation_windows = tuple(
            _window(window, "rotation_window")
            for window in policy["rotation_windows"]
        )
        if not rotation_windows:
            raise DraftInputError(
                f"requirement {requirement_id!r} policy carries no rotation "
                "windows"
            )
        obligations.append(
            DeliveryObligation(
                requirement_id=requirement_id,
                service_date=item["service_date"],
                section_id=item["section_id"],
                gate_id=binding["gate_id"],
                required_volume_m3=float(item["required_volume_m3"]),
                maximum_excess_volume_m3=float(policy["approved_excess_m3"]),
                delivery_window=TimeWindow(
                    starts_at=item["window_start"],
                    ends_at=item["window_end"],
                ),
                rotation_windows=rotation_windows,
                path_reach_ids=path,
                travel_delay_seconds=travel_delay,
                minimum_delivery_fraction=minimum_fraction,
                maximum_delivery_fraction=maximum_fraction,
            )
        )
        derived_obligations.append(
            {
                "requirement_id": requirement_id,
                "section_id": item["section_id"],
                "delivery_node_id": delivery_node_id,
                "gate_id": binding["gate_id"],
                "path_reach_ids": list(path),
                "travel_delay_seconds": travel_delay,
                "minimum_delivery_fraction": minimum_fraction,
                "maximum_delivery_fraction": maximum_fraction,
            }
        )

    obligation_gates = {entry.gate_id for entry in obligations}
    candidate_gates = {entry["gate_id"] for entry in flow_candidates}
    if candidate_gates != obligation_gates:
        raise DraftInputError(
            "flow candidate gates must exactly cover the bound obligation "
            f"gates; candidates {sorted(candidate_gates)} vs obligations "
            f"{sorted(obligation_gates)}"
        )
    duty_gates = {entry["gate_id"] for entry in pulse_duties}
    if duty_gates != obligation_gates:
        raise DraftInputError(
            "pulse duties must exactly cover the bound obligation gates; "
            f"duties {sorted(duty_gates)} vs obligations "
            f"{sorted(obligation_gates)}"
        )
    for candidate in flow_candidates:
        flow = float(candidate["source_flow_m3s"])
        if not envelope.minimum_flow_m3s < flow <= envelope.maximum_flow_m3s:
            raise DraftInputError(
                f"candidate flow {flow} m3/s for gate "
                f"{candidate['gate_id']!r} is outside the model operating "
                f"envelope ({envelope.minimum_flow_m3s}, "
                f"{envelope.maximum_flow_m3s}]"
            )

    capacities = derive_reach_capacities(members_by_reach, used_reach_ids)
    problem = LimitedAdjustmentProblem(
        model_snapshot_id=snapshot_id,
        operating_envelope=envelope,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        obligations=tuple(obligations),
        flow_candidates=tuple(
            QuantizedFlowCandidate(
                gate_id=entry["gate_id"],
                target_position_m=float(entry["target_position_m"]),
                source_flow_m3s=float(entry["source_flow_m3s"]),
            )
            for entry in flow_candidates
        ),
        reach_capacities=capacities,
        pulse_duties=tuple(
            GatePulseDuty(
                gate_id=entry["gate_id"],
                minimum_open_seconds=int(entry["minimum_open_seconds"]),
                maximum_open_seconds=int(entry["maximum_open_seconds"]),
            )
            for entry in pulse_duties
        ),
    )
    derived_document = {
        "model_snapshot_id": snapshot_id,
        "horizon_start": canonical_instant(horizon_start),
        "horizon_end": canonical_instant(horizon_end),
        "model_step_seconds": model_step_seconds,
        "operating_envelope": {
            "minimum_flow_m3s": envelope.minimum_flow_m3s,
            "maximum_flow_m3s": envelope.maximum_flow_m3s,
            "minimum_timestep_seconds": envelope.minimum_timestep_seconds,
            "maximum_timestep_seconds": envelope.maximum_timestep_seconds,
            "maximum_horizon_seconds": envelope.maximum_horizon_seconds,
        },
        "obligations": derived_obligations,
        "reach_capacities": [
            {
                "reach_id": entry.reach_id,
                "maximum_flow_m3s": entry.maximum_flow_m3s,
            }
            for entry in capacities
        ],
        "zero_volume_requirement_ids": zero_ids,
    }
    return problem, derived_document


def serialize_limited_adjustment_plan(
    plan: LimitedAdjustmentPlan,
) -> dict[str, Any]:
    return {
        "status": plan.status.value,
        "model_snapshot_id": plan.model_snapshot_id,
        "model_step_seconds": plan.model_step_seconds,
        "events": [
            {
                "gate_id": event.gate_id,
                "kind": event.kind.value,
                "planned_at": canonical_instant(event.planned_at),
                "target_position_m": event.target_position_m,
            }
            for event in plan.events
        ],
        "allocations": [
            {
                "requirement_id": allocation.requirement_id,
                "gate_id": allocation.gate_id,
                "release_start": canonical_instant(allocation.release_start),
                "release_end": canonical_instant(allocation.release_end),
                "predicted_arrival_start": canonical_instant(
                    allocation.predicted_arrival_start
                ),
                "predicted_arrival_end": canonical_instant(
                    allocation.predicted_arrival_end
                ),
                "target_position_m": allocation.target_position_m,
                "lower_volume_m3": allocation.lower_volume_m3,
                "upper_volume_m3": allocation.upper_volume_m3,
            }
            for allocation in plan.allocations
        ],
        "objective": (
            None
            if plan.objective is None
            else {
                "intermediate_trims": plan.objective.intermediate_trims,
                "excess_volume_m3": plan.objective.excess_volume_m3,
                "physical_moves": plan.objective.physical_moves,
                "source_variation_m3s": plan.objective.source_variation_m3s,
                "open_seconds": plan.objective.open_seconds,
            }
        ),
        "infeasible_reasons": list(plan.infeasible_reasons),
    }


def build_source_flow_events(
    plan_events: Sequence[GatePlanEvent],
    flow_candidates: Sequence[Mapping[str, Any]],
    starts_at: datetime,
    ends_at: datetime,
) -> list[dict[str, Any]]:
    """Collapse per-gate plan events into the source-node flow timeline."""
    flow_by_candidate = {
        (entry["gate_id"], float(entry["target_position_m"])): float(
            entry["source_flow_m3s"]
        )
        for entry in flow_candidates
    }
    active_flow: dict[str, float] = {}
    events_by_time: dict[datetime, list[GatePlanEvent]] = {}
    for event in plan_events:
        if event.planned_at < starts_at or event.planned_at > ends_at:
            raise InternalPlanInvariantError(
                f"optimizer event at {event.planned_at.isoformat()} lies "
                "outside the draft horizon"
            )
        events_by_time.setdefault(event.planned_at, []).append(event)

    timeline: list[dict[str, Any]] = []
    previous_total: float | None = None
    for effective_at in sorted(events_by_time):
        for event in events_by_time[effective_at]:
            if event.kind is GateEventKind.CLOSE:
                active_flow[event.gate_id] = 0.0
                continue
            key = (event.gate_id, float(event.target_position_m))
            flow = flow_by_candidate.get(key)
            if flow is None:
                raise InternalPlanInvariantError(
                    f"optimizer event for gate {event.gate_id!r} at position "
                    f"{event.target_position_m} matches no flow candidate"
                )
            active_flow[event.gate_id] = flow
        total = sum(active_flow.values())
        if previous_total is not None and total == previous_total:
            continue
        if effective_at < ends_at:
            timeline.append(
                {"node_id": _ROOT_NODE_ID, "effective_at": effective_at,
                 "flow_m3s": total}
            )
        previous_total = total
    if not timeline or timeline[0]["effective_at"] != starts_at:
        timeline.insert(
            0,
            {"node_id": _ROOT_NODE_ID, "effective_at": starts_at,
             "flow_m3s": 0.0},
        )
    return timeline


def build_control_prediction_request(
    *,
    model_snapshot_id: str,
    model_release_id: str,
    model_release_content_hash: str,
    starts_at: datetime,
    ends_at: datetime,
    timestep_seconds: float,
    plan_events: Sequence[GatePlanEvent],
    flow_candidates: Sequence[Mapping[str, Any]],
    operator_withdrawals: Sequence[Mapping[str, Any]],
    branch_allocations: Sequence[Mapping[str, Any]],
    section_requirements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_events = build_source_flow_events(
        plan_events, flow_candidates, starts_at, ends_at
    )
    return {
        "model_snapshot_id": model_snapshot_id,
        "model_release_id": model_release_id,
        "model_release_content_hash": model_release_content_hash,
        "initialization": {"kind": "dry"},
        "starts_at": canonical_instant(starts_at),
        "ends_at": canonical_instant(ends_at),
        "timestep_seconds": timestep_seconds,
        "source_flow_events": [
            {
                "node_id": entry["node_id"],
                "effective_at": canonical_instant(entry["effective_at"]),
                "flow_m3s": entry["flow_m3s"],
            }
            for entry in source_events
        ],
        "operator_withdrawal_events": [
            {
                "structure_id": entry["structure_id"],
                "effective_at": canonical_instant(entry["effective_at"]),
                "planned_flow_m3s": entry["planned_flow_m3s"],
                "purpose": entry["purpose"],
                "operator_reference": entry["operator_reference"],
            }
            for entry in operator_withdrawals
        ],
        "branch_allocations": [
            {
                "upstream_node_id": entry["upstream_node_id"],
                "downstream_node_id": entry["downstream_node_id"],
                "fraction": entry["fraction"],
            }
            for entry in branch_allocations
        ],
        "section_requirements": [
            {
                "requirement_id": entry["requirement_id"],
                "section_id": entry["section_id"],
                "delivery_node_id": entry["delivery_node_id"],
                "window_start": canonical_instant(entry["window_start"]),
                "window_end": canonical_instant(entry["window_end"]),
                "required_volume_m3": entry["required_volume_m3"],
                "maximum_delivery_m3s": entry["maximum_delivery_m3s"],
                "approved_excess_m3": entry["approved_excess_m3"],
            }
            for entry in section_requirements
        ],
    }


def summarize_prediction_status(response: Mapping[str, Any]) -> str:
    members = response.get("members")
    if not isinstance(members, list) or len(members) != 3:
        raise UpstreamContractError(
            "prediction response must carry exactly three members"
        )
    labels = {member.get("member") for member in members}
    if labels != {"lower", "nominal", "upper"}:
        raise UpstreamContractError(
            "prediction response must carry each of lower, nominal, upper "
            f"exactly once; got {sorted(str(label) for label in labels)}"
        )
    statuses = {member.get("status") for member in members}
    unknown = statuses - {"completed", "infeasible"}
    if unknown:
        raise UpstreamContractError(
            f"prediction members carry unknown statuses {sorted(unknown)}"
        )
    return "infeasible" if "infeasible" in statuses else "completed"
