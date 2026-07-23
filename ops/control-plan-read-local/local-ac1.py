#!/usr/bin/env python3
"""Pure LOCAL-AC-1 request and verification helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence
from uuid import UUID


class LocalAcceptanceError(RuntimeError):
    """A LOCAL-AC-1 invariant failed with a safe error code."""


LOCAL_ACCEPTANCE_FLOW_M3S = 0.1
LOCAL_ACCEPTANCE_EXCESS_FRACTION = 0.5


def build_branch_allocations(
    routing_elements: Sequence[Mapping[str, Any]],
    unavailable_reach_ids: set[str] | frozenset[str] = frozenset(),
) -> list[dict]:
    if any(
        not isinstance(reach_id, str) or not reach_id
        for reach_id in unavailable_reach_ids
    ):
        raise LocalAcceptanceError("routing_topology_not_accepted")
    children: dict[str, dict[str, bool]] = {}
    for element in routing_elements:
        if element.get("role") == "withdrawal_structure":
            continue
        upstream = element.get("upstream_node_id")
        downstream = element.get("downstream_node_id")
        if not isinstance(upstream, str) or not isinstance(downstream, str):
            raise LocalAcceptanceError("routing_topology_not_accepted")
        per_upstream = children.setdefault(upstream, {})
        if downstream in per_upstream:
            raise LocalAcceptanceError("routing_topology_not_accepted")
        per_upstream[downstream] = (
            element.get("role") == "transport"
            and element.get("element_id") in unavailable_reach_ids
        )
    allocations: list[dict] = []
    for upstream, downstreams in sorted(children.items()):
        if len(downstreams) < 2:
            continue
        available_count = sum(not blocked for blocked in downstreams.values())
        if available_count == 0:
            raise LocalAcceptanceError("routing_topology_not_accepted")
        allocations.extend(
            {
                "upstream_node_id": upstream,
                "downstream_node_id": downstream,
                "fraction": 0.0 if blocked else 1.0 / available_count,
            }
            for downstream, blocked in sorted(downstreams.items())
        )
    return allocations


def _accepted_snapshot(
    snapshot: Mapping[str, Any],
) -> tuple[list[dict], float, dict[str, float], set[str]]:
    action_model = snapshot.get("action_model")
    response_model = snapshot.get("response_model")
    topology = snapshot.get("routing_topology")
    unavailable = snapshot.get("unavailable_transport_reaches")
    if (
        snapshot.get("commandable") is not False
        or not isinstance(action_model, Mapping)
        or action_model.get("commandable") is not False
        or action_model.get("actuation_approved") is not False
        or not isinstance(response_model, Mapping)
        or response_model.get("commandable") is not False
        or not isinstance(response_model.get("reach_parameters"), list)
        or not isinstance(topology, Mapping)
        or not isinstance(topology.get("elements"), list)
        or not isinstance(unavailable, list)
    ):
        raise LocalAcceptanceError("snapshot_not_dark")
    envelope = action_model.get("operating_envelope")
    maximum_flow = (
        envelope.get("maximum_flow_m3s") if isinstance(envelope, Mapping) else None
    )
    if (
        isinstance(maximum_flow, bool)
        or not isinstance(maximum_flow, (int, float))
        or maximum_flow <= 0
    ):
        raise LocalAcceptanceError("snapshot_not_accepted")
    reach_capacities = {}
    for parameter in response_model["reach_parameters"]:
        capacity = (
            parameter.get("capacity_m3s") if isinstance(parameter, Mapping) else None
        )
        reach_id = parameter.get("reach_id") if isinstance(parameter, Mapping) else None
        lower = capacity.get("lower") if isinstance(capacity, Mapping) else None
        if (
            not isinstance(reach_id, str)
            or not reach_id
            or reach_id in reach_capacities
            or isinstance(lower, bool)
            or not isinstance(lower, (int, float))
            or lower <= 0
        ):
            raise LocalAcceptanceError("snapshot_not_accepted")
        reach_capacities[reach_id] = float(lower)
    unavailable_reach_ids = set()
    for item in unavailable:
        reach_id = item.get("reach_id") if isinstance(item, Mapping) else None
        if (
            not isinstance(reach_id, str)
            or not reach_id
            or reach_id in unavailable_reach_ids
        ):
            raise LocalAcceptanceError("snapshot_not_accepted")
        unavailable_reach_ids.add(reach_id)
    return (
        topology["elements"],
        float(maximum_flow),
        reach_capacities,
        unavailable_reach_ids,
    )


def _safe_gate_flows(
    routing_elements: Sequence[Mapping[str, Any]],
    reach_capacities: Mapping[str, float],
    gate_ids: Sequence[str],
    maximum_flow: float,
) -> dict[str, float]:
    parents: dict[str, Mapping[str, Any]] = {}
    for element in routing_elements:
        downstream = element.get("downstream_node_id")
        if not isinstance(downstream, str) or downstream in parents:
            raise LocalAcceptanceError("routing_topology_not_accepted")
        parents[downstream] = element
    flows = {}
    for gate_id in gate_ids:
        node = gate_id
        visited = set()
        path_capacities = []
        while node != "S":
            if node in visited:
                raise LocalAcceptanceError("routing_topology_not_accepted")
            visited.add(node)
            parent = parents.get(node)
            if parent is None:
                raise LocalAcceptanceError("routing_topology_not_accepted")
            if parent.get("role") == "transport":
                reach_id = parent.get("element_id")
                if not isinstance(reach_id, str) or reach_id not in reach_capacities:
                    raise LocalAcceptanceError("snapshot_not_accepted")
                path_capacities.append(reach_capacities[reach_id])
            upstream = parent.get("upstream_node_id")
            if not isinstance(upstream, str):
                raise LocalAcceptanceError("routing_topology_not_accepted")
            node = upstream
        if not path_capacities:
            raise LocalAcceptanceError("flow_candidates_not_accepted")
        flows[gate_id] = min(
            LOCAL_ACCEPTANCE_FLOW_M3S,
            maximum_flow,
            *path_capacities,
        )
    return flows


def _positive_requirements(
    requirements: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    positive = []
    for item in requirements:
        volume = item.get("requiredVolumeM3")
        if (
            item.get("dataStatus") != "published"
            or isinstance(volume, bool)
            or not isinstance(volume, (int, float))
            or volume < 0
        ):
            raise LocalAcceptanceError("requirements_not_accepted")
        if volume > 0:
            positive.append(item)
    if not positive:
        raise LocalAcceptanceError("requirements_not_accepted")
    return positive


def build_control_plan_draft(
    requirements: Sequence[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
    gate_by_section: Mapping[str, str],
) -> dict:
    if not requirements:
        raise LocalAcceptanceError("requirements_not_accepted")
    (
        routing_elements,
        maximum_flow,
        reach_capacities,
        unavailable_reach_ids,
    ) = _accepted_snapshot(snapshot)
    positive = _positive_requirements(requirements)
    nodes = {
        str(element[key])
        for element in routing_elements
        for key in ("upstream_node_id", "downstream_node_id")
        if isinstance(element, Mapping) and isinstance(element.get(key), str)
    }
    run_ids = {str(item.get("runId")) for item in positive}
    versions = {item.get("version") for item in positive}
    if len(run_ids) != 1 or len(versions) != 1:
        raise LocalAcceptanceError("requirements_not_accepted")
    try:
        UUID(next(iter(run_ids)))
        version_value = next(iter(versions))
        if isinstance(version_value, bool) or not isinstance(version_value, int):
            raise ValueError
        version = version_value
    except (TypeError, ValueError) as exc:
        raise LocalAcceptanceError("requirements_not_accepted") from exc
    if version < 1:
        raise LocalAcceptanceError("requirements_not_accepted")

    normalized: list[dict[str, Any]] = []
    for item in positive:
        try:
            requirement_id = str(UUID(str(item["requirementId"])))
            section_id = str(item["sectionId"])
            service_date = str(item["serviceDate"])
            zone = int(item["zone"])
            volume = float(item["requiredVolumeM3"])
            window = item["deliveryWindow"]
            starts_at = datetime.fromisoformat(str(window["start"]))
            ends_at = datetime.fromisoformat(str(window["end"]))
            gate_id = gate_by_section[section_id]
        except (KeyError, TypeError, ValueError) as exc:
            raise LocalAcceptanceError("requirements_not_accepted") from exc
        if (
            starts_at.tzinfo is None
            or ends_at.tzinfo is None
            or starts_at >= ends_at
            or gate_id not in nodes
            or not 1 <= zone <= 6
        ):
            raise LocalAcceptanceError("requirements_not_accepted")
        normalized.append(
            {
                "requirement_id": requirement_id,
                "section_id": section_id,
                "service_date": service_date,
                "zone": zone,
                "volume": volume,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "gate_id": gate_id,
            }
        )
    normalized.sort(key=lambda item: item["requirement_id"])
    gate_ids = sorted({item["gate_id"] for item in normalized})
    flow_by_gate = _safe_gate_flows(
        routing_elements,
        reach_capacities,
        gate_ids,
        maximum_flow,
    )
    horizon_start = min(item["starts_at"] for item in normalized)
    horizon_end = max(item["ends_at"] for item in normalized)
    horizon_seconds = int((horizon_end - horizon_start).total_seconds())
    scopes = sorted({(item["service_date"], item["zone"]) for item in normalized})
    return {
        "requirement_run_id": next(iter(run_ids)),
        "requirement_version": version,
        "requirement_scopes": [
            {"service_date": service_date, "zone": zone}
            for service_date, zone in scopes
        ],
        "starts_at": horizon_start.isoformat(),
        "ends_at": horizon_end.isoformat(),
        "section_bindings": [
            {
                "section_id": item["section_id"],
                "delivery_node_id": item["gate_id"],
                "gate_id": item["gate_id"],
                "maximum_delivery_m3s": flow_by_gate[item["gate_id"]],
            }
            for item in normalized
        ],
        "requirement_policies": [
            {
                "requirement_id": item["requirement_id"],
                "approved_excess_m3": (
                    item["volume"] * LOCAL_ACCEPTANCE_EXCESS_FRACTION
                ),
                "rotation_windows": [
                    {
                        "starts_at": item["starts_at"].isoformat(),
                        "ends_at": item["ends_at"].isoformat(),
                    }
                ],
            }
            for item in normalized
        ],
        "flow_candidates": [
            {
                "gate_id": gate_id,
                "target_position_m": 0.5,
                "source_flow_m3s": flow_by_gate[gate_id],
            }
            for gate_id in gate_ids
        ],
        "pulse_duties": [
            {
                "gate_id": gate_id,
                "minimum_open_seconds": 300,
                "maximum_open_seconds": horizon_seconds,
            }
            for gate_id in gate_ids
        ],
        "operator_withdrawals": [],
        "branch_allocations": build_branch_allocations(
            routing_elements,
            unavailable_reach_ids,
        ),
    }


def projection_paths(plan_id: str, plan_version: int) -> tuple[str, ...]:
    try:
        normalized_id = str(UUID(plan_id))
    except ValueError as exc:
        raise LocalAcceptanceError("plan_identity_not_accepted") from exc
    if plan_version < 1:
        raise LocalAcceptanceError("plan_identity_not_accepted")
    base = f"/api/v1/control-plans/{normalized_id}/versions/{plan_version}"
    return (
        "/api/v1/control-plans",
        base,
        f"{base}/prediction-coverage",
        f"{base}/ledger",
        f"{base}/lifecycle-history",
        f"{base}/intent-timeline",
        f"{base}/readback-observations",
        f"{base}/execution-state",
    )
