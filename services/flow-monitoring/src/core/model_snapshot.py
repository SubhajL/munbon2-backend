"""Content-addressed snapshot of the sensorless hydraulic model.

Schema version 2: canonical SCADA graph identity, the derived typed
routing topology, and transport-response coverage are exposed as separate
concepts. Only transport elements can carry reach responses; boundary,
branch, and withdrawal structures are structural transitions.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timezone
import re

from .demand_contract import content_hash
from .model_release import (
    HydraulicModelRelease,
    ModelReleaseError,
    OperatingEnvelope,
    ParameterDistribution,
    validate_model_release,
)
from .network_topology import ROOT
from .reach_response import (
    ReachResponse,
    reach_responses_from_model_release,
)
from .routing_topology import (
    RoutingTopology,
    routing_topology_payload,
)

__all__ = ["ModelSnapshotError", "build_model_snapshot"]

_CONFIG_KEYS = {
    "network",
    "canal_geometry",
    "gate_calibrations",
    "geometry_coverage",
    "routing_topology",
}
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_NO_MODEL_REASON = "hydraulic model release is not configured"


class ModelSnapshotError(ValueError):
    """The runtime model cannot be represented as an exact snapshot."""


def build_model_snapshot(
    routing_topology: RoutingTopology,
    reach_responses: tuple[ReachResponse, ...],
    release: HydraulicModelRelease | None,
    config_sha256: Mapping[str, str],
    actuation_approved: bool,
) -> dict:
    """Return one deterministic, non-commanding view of the runtime model."""
    _validate_runtime_contract(
        routing_topology,
        reach_responses,
        release,
        config_sha256,
        actuation_approved,
    )
    transport_reach_ids = routing_topology.transport_reach_ids()
    unavailable = _unavailable_transport_reaches(transport_reach_ids, release)
    available_count = len(transport_reach_ids) - len(unavailable)
    canonical_edges = _canonical_edges(routing_topology)
    routing_payload = routing_topology_payload(routing_topology)
    role_counts: dict[str, int] = {}
    for element in routing_topology.elements:
        role_counts[element.role.value] = role_counts.get(element.role.value, 0) + 1
    node_ids = {ROOT} | {
        element.downstream_node_id for element in routing_topology.elements
    }
    payload = {
        "schema_version": 2,
        "data_status": _data_status(available_count, len(transport_reach_ids)),
        "mode": "open_loop_prediction",
        "open_loop": True,
        "actual_state_known": False,
        "commandable": False,
        "scada_graph": {
            "config_sha256": config_sha256["network"],
            "source_workbook_sha256": routing_topology.source_sha256,
            "root_node_id": ROOT,
            "gate_count": len(canonical_edges),
            "edge_count": len(canonical_edges),
            "edges": [
                {"upstream_node_id": upstream, "downstream_node_id": downstream}
                for upstream, downstream in canonical_edges
            ],
        },
        "routing_topology": {
            "schema_version": routing_topology.schema_version,
            "config_sha256": config_sha256["routing_topology"],
            "content_hash": routing_topology.content_hash,
            "root_node_id": ROOT,
            "node_count": len(node_ids),
            "element_count": len(routing_topology.elements),
            "role_counts": role_counts,
            "elements": routing_payload["elements"],
        },
        "action_model": {
            "kind": "gate_flow_event",
            "flow_unit": "m3/s",
            "allowed_node_ids": [ROOT],
            "requires_explicit_branch_allocations": True,
            "commandable": False,
            "actuation_approved": actuation_approved,
            "config_sha256": {
                "canal_geometry": config_sha256["canal_geometry"],
                "gate_calibrations": config_sha256["gate_calibrations"],
                "geometry_coverage": config_sha256["geometry_coverage"],
            },
            "operating_envelope": (
                None
                if release is None
                else _operating_envelope_payload(release.operating_envelope)
            ),
        },
        "response_model": (
            None
            if release is None
            else _response_model_payload(release, reach_responses)
        ),
        "transport_response_coverage": {
            "total_transport_reaches": len(transport_reach_ids),
            "available_transport_reaches": available_count,
            "unavailable_transport_reaches": len(unavailable),
        },
        "unavailable_transport_reaches": unavailable,
    }
    return {"snapshot_id": content_hash(payload), **payload}


def _canonical_edges(
    routing_topology: RoutingTopology,
) -> tuple[tuple[str, str], ...]:
    seen: list[tuple[str, str]] = []
    for element in routing_topology.elements:
        for edge in element.canonical_edges:
            if edge not in seen:
                seen.append(edge)
    return tuple(seen)


def _validate_runtime_contract(
    routing_topology: RoutingTopology,
    reach_responses: tuple[ReachResponse, ...],
    release: HydraulicModelRelease | None,
    config_sha256: Mapping[str, str],
    actuation_approved: bool,
) -> None:
    if not isinstance(routing_topology, RoutingTopology):
        raise ModelSnapshotError(
            "model snapshot requires a typed RoutingTopology"
        )
    if not isinstance(reach_responses, tuple):
        raise ModelSnapshotError("reach_responses must be an immutable tuple")
    if not isinstance(actuation_approved, bool):
        raise ModelSnapshotError("actuation_approved must be a boolean")
    _validate_config_sha256(config_sha256)
    if release is None:
        if reach_responses:
            raise ModelSnapshotError(
                "runtime response members exist without a model release"
            )
        return
    try:
        validate_model_release(release, routing_topology.transport_reach_ids())
    except ModelReleaseError as exc:
        raise ModelSnapshotError(str(exc)) from exc
    expected_responses = reach_responses_from_model_release(release)
    if _sorted_responses(reach_responses) != _sorted_responses(expected_responses):
        raise ModelSnapshotError(
            "runtime response members do not match the model release"
        )


def _validate_config_sha256(config_sha256: Mapping[str, str]) -> None:
    if not isinstance(config_sha256, Mapping):
        raise ModelSnapshotError("config_sha256 must be a mapping")
    if set(config_sha256) != _CONFIG_KEYS:
        raise ModelSnapshotError(
            f"config_sha256 must contain exactly {sorted(_CONFIG_KEYS)}"
        )
    if any(
        not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None
        for value in config_sha256.values()
    ):
        raise ModelSnapshotError(
            "config_sha256 values must be lowercase SHA-256 hex digests"
        )


def _unavailable_transport_reaches(
    transport_reach_ids: tuple[str, ...], release: HydraulicModelRelease | None
) -> list[dict]:
    if release is None:
        return [
            {"reach_id": reach_id, "reason": _NO_MODEL_REASON}
            for reach_id in sorted(transport_reach_ids)
        ]
    return [
        {"reach_id": reach.reach_id, "reason": reach.reason}
        for reach in sorted(
            release.unavailable_reaches,
            key=lambda unavailable: unavailable.reach_id,
        )
    ]


def _data_status(available_count: int, total_count: int) -> str:
    if available_count == total_count:
        return "complete"
    if available_count == 0:
        return "unavailable"
    return "partial"


def _response_model_payload(
    release: HydraulicModelRelease,
    reach_responses: tuple[ReachResponse, ...],
) -> dict:
    generated_at = release.generated_at.astimezone(timezone.utc)
    return {
        "schema_version": release.schema_version,
        "release_id": release.release_id,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "evidence_class": release.evidence_class.value,
        "commandable": release.commandable,
        "content_hash": release.content_hash,
        "lineage": {
            "generator": release.lineage.generator,
            "generator_version": release.lineage.generator_version,
            "sources": [
                {
                    "source_id": source.source_id,
                    "version": source.version,
                    "sha256": source.sha256,
                }
                for source in sorted(
                    release.lineage.sources,
                    key=lambda artifact: artifact.source_id,
                )
            ],
        },
        "reach_parameters": [
            _reach_parameters_payload(parameters)
            for parameters in sorted(
                release.reach_parameters,
                key=lambda parameters: parameters.reach_id,
            )
        ],
        "response_members": [
            _response_member_payload(response)
            for response in _sorted_responses(reach_responses)
        ],
    }


def _reach_parameters_payload(parameters) -> dict:
    return {
        "reach_id": parameters.reach_id,
        "delay_seconds": _distribution_payload(parameters.delay_seconds),
        "loss_fraction": _distribution_payload(parameters.loss_fraction),
        "dispersion_seconds": _distribution_payload(parameters.dispersion_seconds),
        "capacity_m3s": _distribution_payload(parameters.capacity_m3s),
        "evidence_refs": sorted(parameters.evidence_refs),
    }


def _response_member_payload(response: ReachResponse) -> dict:
    return {
        "reach_id": response.reach_id,
        "member": response.member.value,
        "delay_seconds": response.delay_seconds,
        "loss_fraction": response.loss_fraction,
        "dispersion_seconds": response.dispersion_seconds,
        "capacity_m3s": response.capacity_m3s,
        "minimum_timestep_seconds": response.minimum_timestep_seconds,
        "maximum_timestep_seconds": response.maximum_timestep_seconds,
    }


def _sorted_responses(
    responses: tuple[ReachResponse, ...],
) -> tuple[ReachResponse, ...]:
    return tuple(
        sorted(
            responses,
            key=lambda response: (response.reach_id, response.member.value),
        )
    )


def _distribution_payload(distribution: ParameterDistribution) -> dict:
    return {
        "lower": distribution.lower,
        "nominal": distribution.nominal,
        "upper": distribution.upper,
    }


def _operating_envelope_payload(envelope: OperatingEnvelope) -> dict:
    return {
        "minimum_flow_m3s": envelope.minimum_flow_m3s,
        "maximum_flow_m3s": envelope.maximum_flow_m3s,
        "minimum_timestep_seconds": envelope.minimum_timestep_seconds,
        "maximum_timestep_seconds": envelope.maximum_timestep_seconds,
        "maximum_horizon_seconds": envelope.maximum_horizon_seconds,
    }
