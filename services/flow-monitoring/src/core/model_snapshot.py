"""Content-addressed snapshot of the sensorless hydraulic model."""

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
from .network_topology import ROOT, is_spanning_tree
from .reach_response import (
    ReachResponse,
    reach_responses_from_model_release,
)

__all__ = ["ModelSnapshotError", "build_model_snapshot"]

_CONFIG_KEYS = {"network", "canal_geometry", "gate_calibrations"}
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_NO_MODEL_REASON = "hydraulic model release is not configured"


class ModelSnapshotError(ValueError):
    """The runtime model cannot be represented as an exact snapshot."""


def build_model_snapshot(
    network_edges: tuple[tuple[str, str], ...],
    reach_responses: tuple[ReachResponse, ...],
    release: HydraulicModelRelease | None,
    config_sha256: Mapping[str, str],
    actuation_approved: bool,
) -> dict:
    """Return one deterministic, non-commanding view of the runtime model."""
    _validate_runtime_contract(
        network_edges,
        reach_responses,
        release,
        config_sha256,
        actuation_approved,
    )
    reaches = _network_reaches(network_edges)
    unavailable = _unavailable_reaches(reaches, release)
    available_count = len(reaches) - len(unavailable)
    payload = {
        "schema_version": 1,
        "data_status": _data_status(available_count, len(reaches)),
        "mode": "open_loop_prediction",
        "open_loop": True,
        "actual_state_known": False,
        "commandable": False,
        "network": {
            "config_sha256": config_sha256["network"],
            "reach_count": len(reaches),
            "reaches": reaches,
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
        "coverage": {
            "total_reaches": len(reaches),
            "available_reaches": available_count,
            "unavailable_reaches": len(unavailable),
        },
        "unavailable_reaches": unavailable,
    }
    return {"snapshot_id": content_hash(payload), **payload}


def _validate_runtime_contract(
    network_edges: tuple[tuple[str, str], ...],
    reach_responses: tuple[ReachResponse, ...],
    release: HydraulicModelRelease | None,
    config_sha256: Mapping[str, str],
    actuation_approved: bool,
) -> None:
    if not isinstance(network_edges, tuple) or not network_edges:
        raise ModelSnapshotError("network_edges must be a non-empty immutable tuple")
    if not all(
        isinstance(edge, tuple)
        and len(edge) == 2
        and all(isinstance(node, str) and node.strip() for node in edge)
        for edge in network_edges
    ):
        raise ModelSnapshotError("network_edges must contain node-id pairs")
    if not is_spanning_tree(network_edges):
        raise ModelSnapshotError("network_edges must form a rooted spanning tree")
    if not isinstance(reach_responses, tuple):
        raise ModelSnapshotError("reach_responses must be an immutable tuple")
    if not isinstance(actuation_approved, bool):
        raise ModelSnapshotError("actuation_approved must be a boolean")
    _validate_config_sha256(config_sha256)
    expected_reach_ids = tuple(
        f"C_{upstream}_{downstream}" for upstream, downstream in network_edges
    )
    if release is None:
        if reach_responses:
            raise ModelSnapshotError(
                "runtime response members exist without a model release"
            )
        return
    try:
        validate_model_release(release, expected_reach_ids)
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


def _network_reaches(
    network_edges: tuple[tuple[str, str], ...],
) -> list[dict]:
    return sorted(
        (
            {
                "reach_id": f"C_{upstream}_{downstream}",
                "upstream_node_id": upstream,
                "downstream_node_id": downstream,
            }
            for upstream, downstream in network_edges
        ),
        key=lambda reach: reach["reach_id"],
    )


def _unavailable_reaches(
    reaches: list[dict], release: HydraulicModelRelease | None
) -> list[dict]:
    if release is None:
        return [
            {"reach_id": reach["reach_id"], "reason": _NO_MODEL_REASON}
            for reach in reaches
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
