"""Versioned external approval for a commandable hydraulic snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import json
import math
import re
from typing import Any

from .demand_contract import content_hash
from .model_release import HydraulicModelRelease

__all__ = [
    "CommandabilityApprovalError",
    "commandability_approval_content_hash",
    "is_commandability_approved",
    "load_commandability_approval",
    "verify_commandability_approval",
]


class CommandabilityApprovalError(ValueError):
    """The configured commandability approval is malformed or mismatched."""


_MAX_APPROVAL_BYTES = 262_144
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_CONFIG_KEYS = {
    "network",
    "canal_geometry",
    "gate_calibrations",
    "geometry_coverage",
    "routing_topology",
}
_ENVELOPE_KEYS = {
    "minimum_flow_m3s",
    "maximum_flow_m3s",
    "minimum_timestep_seconds",
    "maximum_timestep_seconds",
    "maximum_horizon_seconds",
}


def commandability_approval_content_hash(document: Mapping[str, Any]) -> str:
    payload = dict(document)
    payload.pop("content_hash", None)
    return content_hash(payload)


def is_commandability_approved(document: Mapping[str, Any] | None) -> bool:
    return bool(
        document is not None
        and document.get("approval_state") == "approved"
        and isinstance(document.get("approval"), Mapping)
    )


def load_commandability_approval(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.strip():
        raise CommandabilityApprovalError(
            "configured commandability approval path must be non-empty"
        )
    try:
        with open(path, "rb") as file:
            raw = file.read(_MAX_APPROVAL_BYTES + 1)
    except OSError as error:
        raise CommandabilityApprovalError(
            "configured commandability approval cannot be read"
        ) from error
    if len(raw) > _MAX_APPROVAL_BYTES:
        raise CommandabilityApprovalError(
            "commandability approval exceeds the 256 KiB size cap"
        )
    try:
        document = json.loads(raw.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError) as error:
        raise CommandabilityApprovalError(
            "commandability approval is not strict UTF-8 JSON"
        ) from error
    if not isinstance(document, dict):
        raise CommandabilityApprovalError(
            "commandability approval must be a JSON object"
        )
    _validate_document(document)
    return document


def verify_commandability_approval(
    document: Mapping[str, Any],
    release: HydraulicModelRelease | None,
    prediction_engine: Mapping[str, Any] | None,
    config_sha256: Mapping[str, str],
) -> None:
    _validate_document(dict(document))
    if release is None or prediction_engine is None:
        raise CommandabilityApprovalError(
            "commandability approval does not match an available runtime release"
        )
    expected_release = {
        "release_id": release.release_id,
        "content_hash": release.content_hash,
    }
    if document["base_model_release"] != expected_release:
        raise CommandabilityApprovalError(
            "commandability approval base release does not match runtime"
        )
    if document["prediction_engine"] != {
        "content_hash": prediction_engine.get("content_hash")
    }:
        raise CommandabilityApprovalError(
            "commandability approval prediction engine does not match runtime"
        )
    if document["model_config_sha256"] != dict(config_sha256):
        raise CommandabilityApprovalError(
            "commandability approval model config does not match runtime"
        )
    envelope = release.operating_envelope
    expected_envelope = {
        "minimum_flow_m3s": envelope.minimum_flow_m3s,
        "maximum_flow_m3s": envelope.maximum_flow_m3s,
        "minimum_timestep_seconds": envelope.minimum_timestep_seconds,
        "maximum_timestep_seconds": envelope.maximum_timestep_seconds,
        "maximum_horizon_seconds": envelope.maximum_horizon_seconds,
    }
    if document["operating_envelope"] != expected_envelope:
        raise CommandabilityApprovalError(
            "commandability approval operating envelope does not match runtime"
        )


def _reject_json_constant(value: str):
    raise ValueError(f"non-finite JSON constant {value}")


def _require_exact_keys(value: Mapping, expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise CommandabilityApprovalError(
            f"{label} must contain exactly {sorted(expected)}"
        )


def _require_object(document: Mapping, key: str, label: str) -> dict:
    value = document.get(key)
    if not isinstance(value, dict):
        raise CommandabilityApprovalError(f"{label}.{key} must be an object")
    return value


def _require_non_blank(value: Any, label: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise CommandabilityApprovalError(f"{label} must be a bounded non-blank string")
    return value


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None:
        raise CommandabilityApprovalError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_finite_number(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise CommandabilityApprovalError(f"{label} must be a finite number")
    return float(value)


def _validate_document(document: dict[str, Any]) -> None:
    _require_exact_keys(
        document,
        {
            "schema_version",
            "approval_state",
            "base_model_release",
            "prediction_engine",
            "model_config_sha256",
            "operating_envelope",
            "device_capability",
            "approval",
            "content_hash",
        },
        "commandability_approval",
    )
    if isinstance(document["schema_version"], bool) or document["schema_version"] != 1:
        raise CommandabilityApprovalError("schema_version must be integer 1")
    state = document["approval_state"]
    if state not in {"approved", "not_approved"}:
        raise CommandabilityApprovalError("approval_state is unknown")
    _validate_release(document)
    _validate_engine(document)
    _validate_config(document)
    _validate_envelope(document)
    _validate_capability(document)
    _validate_attestation(document, state)
    _require_sha256(document["content_hash"], "content_hash")
    expected_hash = commandability_approval_content_hash(document)
    if document["content_hash"] != expected_hash:
        raise CommandabilityApprovalError(
            "content_hash does not reproduce the commandability approval"
        )


def _validate_release(document: Mapping[str, Any]) -> None:
    release = _require_object(document, "base_model_release", "commandability_approval")
    _require_exact_keys(release, {"release_id", "content_hash"}, "base_model_release")
    _require_non_blank(release["release_id"], "base_model_release.release_id", 256)
    _require_sha256(release["content_hash"], "base_model_release.content_hash")


def _validate_engine(document: Mapping[str, Any]) -> None:
    engine = _require_object(document, "prediction_engine", "commandability_approval")
    _require_exact_keys(engine, {"content_hash"}, "prediction_engine")
    _require_sha256(engine["content_hash"], "prediction_engine.content_hash")


def _validate_config(document: Mapping[str, Any]) -> None:
    config = _require_object(document, "model_config_sha256", "commandability_approval")
    _require_exact_keys(config, _CONFIG_KEYS, "model_config_sha256")
    for name, value in config.items():
        _require_sha256(value, f"model_config_sha256.{name}")


def _validate_envelope(document: Mapping[str, Any]) -> None:
    envelope = _require_object(
        document, "operating_envelope", "commandability_approval"
    )
    _require_exact_keys(envelope, _ENVELOPE_KEYS, "operating_envelope")
    minimum_flow = _require_finite_number(
        envelope["minimum_flow_m3s"], "operating_envelope.minimum_flow_m3s"
    )
    maximum_flow = _require_finite_number(
        envelope["maximum_flow_m3s"], "operating_envelope.maximum_flow_m3s"
    )
    minimum_step = _require_finite_number(
        envelope["minimum_timestep_seconds"],
        "operating_envelope.minimum_timestep_seconds",
    )
    maximum_step = _require_finite_number(
        envelope["maximum_timestep_seconds"],
        "operating_envelope.maximum_timestep_seconds",
    )
    maximum_horizon = _require_finite_number(
        envelope["maximum_horizon_seconds"],
        "operating_envelope.maximum_horizon_seconds",
    )
    if not (
        minimum_flow >= 0
        and maximum_flow > minimum_flow
        and minimum_step > 0
        and maximum_step >= minimum_step
        and maximum_horizon >= maximum_step
    ):
        raise CommandabilityApprovalError("operating_envelope bounds are invalid")


def _validate_capability(document: Mapping[str, Any]) -> None:
    capability = _require_object(
        document, "device_capability", "commandability_approval"
    )
    _require_exact_keys(
        capability,
        {"capability_release_id", "capability_hash", "approved_gate_ids"},
        "device_capability",
    )
    _require_non_blank(
        capability["capability_release_id"],
        "device_capability.capability_release_id",
        256,
    )
    _require_sha256(capability["capability_hash"], "device_capability.capability_hash")
    gate_ids = capability["approved_gate_ids"]
    if (
        not isinstance(gate_ids, list)
        or not gate_ids
        or any(
            not isinstance(gate_id, str) or not gate_id.strip() for gate_id in gate_ids
        )
        or gate_ids != sorted(set(gate_ids))
    ):
        raise CommandabilityApprovalError(
            "device_capability.approved_gate_ids must be a sorted non-empty unique list"
        )


def _validate_attestation(document: Mapping[str, Any], state: str) -> None:
    approval = document["approval"]
    if state == "not_approved":
        if approval is not None:
            raise CommandabilityApprovalError(
                "not_approved state requires approval null"
            )
        return
    if not isinstance(approval, dict):
        raise CommandabilityApprovalError("approved state requires an approval object")
    _require_exact_keys(
        approval,
        {
            "approved_by_role",
            "approved_at",
            "approval_reference",
            "evidence",
        },
        "approval",
    )
    _require_non_blank(approval["approved_by_role"], "approval.approved_by_role", 128)
    approved_at = _require_non_blank(
        approval["approved_at"], "approval.approved_at", 32
    )
    try:
        parsed = datetime.fromisoformat(approved_at.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise CommandabilityApprovalError(
            "approval.approved_at must be a UTC instant"
        ) from error
    if not approved_at.endswith("Z") or parsed.utcoffset().total_seconds() != 0:
        raise CommandabilityApprovalError("approval.approved_at must be a UTC instant")
    _require_non_blank(
        approval["approval_reference"], "approval.approval_reference", 256
    )
    evidence = approval["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise CommandabilityApprovalError("approval.evidence must be non-empty")
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise CommandabilityApprovalError(
                f"approval.evidence[{index}] must be an object"
            )
        _require_exact_keys(
            item, {"kind", "reference", "sha256"}, "approval.evidence[]"
        )
        _require_non_blank(item["kind"], f"approval.evidence[{index}].kind", 64)
        _require_non_blank(item["reference"], f"approval.evidence[{index}].reference")
        _require_sha256(item["sha256"], f"approval.evidence[{index}].sha256")
