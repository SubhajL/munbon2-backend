"""Immutable hydraulic model-release contract for sensorless prediction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import math
import re
from typing import Iterable

from .config_loader import ConfigError, load_strict_json_object
from .demand_contract import content_hash as canonical_content_hash

__all__ = [
    "EvidenceClass",
    "HydraulicModelRelease",
    "ModelLineage",
    "ModelReleaseError",
    "OperatingEnvelope",
    "ParameterDistribution",
    "ReachResponseParameters",
    "SourceArtifact",
    "UnavailableReach",
    "load_configured_hydraulic_model_release",
    "load_hydraulic_model_release",
    "model_release_content_hash",
    "validate_model_release",
]

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class ModelReleaseError(ValueError):
    """A hydraulic model release is malformed or outside its declared contract."""


class EvidenceClass(str, Enum):
    ENGINEERING_PRIOR = "engineering_prior"


@dataclass(frozen=True)
class ParameterDistribution:
    lower: float
    nominal: float
    upper: float


@dataclass(frozen=True)
class SourceArtifact:
    source_id: str
    version: str
    sha256: str


@dataclass(frozen=True)
class ModelLineage:
    generator: str
    generator_version: str
    sources: tuple[SourceArtifact, ...]


@dataclass(frozen=True)
class OperatingEnvelope:
    minimum_flow_m3s: float
    maximum_flow_m3s: float
    minimum_timestep_seconds: float
    maximum_timestep_seconds: float
    maximum_horizon_seconds: float


@dataclass(frozen=True)
class ReachResponseParameters:
    reach_id: str
    delay_seconds: ParameterDistribution
    loss_fraction: ParameterDistribution
    dispersion_seconds: ParameterDistribution
    capacity_m3s: ParameterDistribution
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class UnavailableReach:
    reach_id: str
    reason: str


@dataclass(frozen=True)
class HydraulicModelRelease:
    schema_version: int
    release_id: str
    generated_at: datetime
    evidence_class: EvidenceClass
    commandable: bool
    lineage: ModelLineage
    operating_envelope: OperatingEnvelope
    reach_parameters: tuple[ReachResponseParameters, ...]
    unavailable_reaches: tuple[UnavailableReach, ...]
    content_hash: str


def model_release_content_hash(release: HydraulicModelRelease) -> str:
    return canonical_content_hash(_model_release_payload(release))


def validate_model_release(
    release: HydraulicModelRelease, expected_reach_ids: Iterable[str]
) -> None:
    if release.schema_version != 1:
        raise ModelReleaseError("schema_version must be 1")
    _validate_non_blank(release.release_id, "release_id")
    if release.generated_at.tzinfo is None or release.generated_at.utcoffset() is None:
        raise ModelReleaseError("generated_at must be timezone-aware")
    if release.evidence_class is not EvidenceClass.ENGINEERING_PRIOR:
        raise ModelReleaseError("evidence_class must be engineering_prior")
    if not isinstance(release.commandable, bool):
        raise ModelReleaseError("commandable must be a boolean")
    if release.commandable:
        raise ModelReleaseError("initial model releases must have commandable=false")

    source_ids = _validate_lineage(release.lineage)
    _validate_operating_envelope(release.operating_envelope)
    _validate_reach_parameters(release.reach_parameters, source_ids)
    _validate_reach_coverage(
        release.reach_parameters,
        release.unavailable_reaches,
        expected_reach_ids,
    )
    _validate_sha256(release.content_hash, "content_hash")
    expected_hash = model_release_content_hash(release)
    if release.content_hash != expected_hash:
        raise ModelReleaseError(
            f"content_hash drift: declared {release.content_hash!r}, expected {expected_hash!r}"
        )


def load_hydraulic_model_release(
    path: str, expected_reach_ids: Iterable[str]
) -> HydraulicModelRelease:
    try:
        data = load_strict_json_object(path)
    except ConfigError as exc:
        raise ModelReleaseError(str(exc)) from exc

    _require_exact_keys(
        data,
        {
            "schema_version",
            "release_id",
            "generated_at",
            "evidence_class",
            "commandable",
            "lineage",
            "operating_envelope",
            "reach_parameters",
            "unavailable_reaches",
            "content_hash",
        },
        "model_release",
    )
    evidence_value = _require_string(data, "evidence_class", "model_release")
    try:
        evidence_class = EvidenceClass(evidence_value)
    except ValueError as exc:
        raise ModelReleaseError(
            f"model_release.evidence_class is unknown: {evidence_value!r}"
        ) from exc

    release = HydraulicModelRelease(
        schema_version=_require_integer(data, "schema_version", "model_release"),
        release_id=_require_string(data, "release_id", "model_release"),
        generated_at=_parse_datetime(
            _require_string(data, "generated_at", "model_release"), "generated_at"
        ),
        evidence_class=evidence_class,
        commandable=_require_boolean(data, "commandable", "model_release"),
        lineage=_parse_lineage(_require_object(data, "lineage", "model_release")),
        operating_envelope=_parse_operating_envelope(
            _require_object(data, "operating_envelope", "model_release")
        ),
        reach_parameters=tuple(
            _parse_reach_parameters(value, index)
            for index, value in enumerate(
                _require_array(data, "reach_parameters", "model_release")
            )
        ),
        unavailable_reaches=tuple(
            _parse_unavailable_reach(value, index)
            for index, value in enumerate(
                _require_array(data, "unavailable_reaches", "model_release")
            )
        ),
        content_hash=_require_string(data, "content_hash", "model_release"),
    )
    validate_model_release(release, expected_reach_ids)
    return release


def load_configured_hydraulic_model_release(
    path: str | None, expected_transport_reach_ids: Iterable[str]
) -> HydraulicModelRelease | None:
    """Load the configured release against explicit transport reach IDs.

    Coverage is defined by the typed routing topology's transport elements
    only — boundary, branch, and withdrawal structures never carry reach
    responses and must not appear in a release.
    """
    if path is None:
        return None
    if not path.strip():
        raise ModelReleaseError("configured model release path must be non-empty")
    return load_hydraulic_model_release(path, expected_transport_reach_ids)


def _model_release_payload(release: HydraulicModelRelease) -> dict:
    generated_at = release.generated_at.astimezone(timezone.utc)
    return {
        "schema_version": release.schema_version,
        "release_id": release.release_id,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "evidence_class": release.evidence_class.value,
        "commandable": release.commandable,
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
                    release.lineage.sources, key=lambda source: source.source_id
                )
            ],
        },
        "operating_envelope": {
            "minimum_flow_m3s": release.operating_envelope.minimum_flow_m3s,
            "maximum_flow_m3s": release.operating_envelope.maximum_flow_m3s,
            "minimum_timestep_seconds": release.operating_envelope.minimum_timestep_seconds,
            "maximum_timestep_seconds": release.operating_envelope.maximum_timestep_seconds,
            "maximum_horizon_seconds": release.operating_envelope.maximum_horizon_seconds,
        },
        "reach_parameters": [
            {
                "reach_id": parameters.reach_id,
                "delay_seconds": _distribution_payload(parameters.delay_seconds),
                "loss_fraction": _distribution_payload(parameters.loss_fraction),
                "dispersion_seconds": _distribution_payload(
                    parameters.dispersion_seconds
                ),
                "capacity_m3s": _distribution_payload(parameters.capacity_m3s),
                "evidence_refs": sorted(parameters.evidence_refs),
            }
            for parameters in sorted(
                release.reach_parameters, key=lambda parameters: parameters.reach_id
            )
        ],
        "unavailable_reaches": [
            {"reach_id": reach.reach_id, "reason": reach.reason}
            for reach in sorted(
                release.unavailable_reaches, key=lambda reach: reach.reach_id
            )
        ],
    }


def _distribution_payload(distribution: ParameterDistribution) -> dict:
    return {
        "lower": distribution.lower,
        "nominal": distribution.nominal,
        "upper": distribution.upper,
    }


def _validate_lineage(lineage: ModelLineage) -> set[str]:
    _validate_non_blank(lineage.generator, "lineage.generator")
    _validate_non_blank(lineage.generator_version, "lineage.generator_version")
    if not lineage.sources:
        raise ModelReleaseError("lineage.sources must contain at least one source")
    source_ids: set[str] = set()
    for source in lineage.sources:
        _validate_non_blank(source.source_id, "lineage.sources[].source_id")
        _validate_non_blank(source.version, "lineage.sources[].version")
        _validate_sha256(source.sha256, "lineage.sources[].sha256")
        if source.source_id in source_ids:
            raise ModelReleaseError(
                f"lineage.sources contains duplicate source_id {source.source_id!r}"
            )
        source_ids.add(source.source_id)
    return source_ids


def _validate_operating_envelope(envelope: OperatingEnvelope) -> None:
    values = (
        ("minimum_flow_m3s", envelope.minimum_flow_m3s),
        ("maximum_flow_m3s", envelope.maximum_flow_m3s),
        ("minimum_timestep_seconds", envelope.minimum_timestep_seconds),
        ("maximum_timestep_seconds", envelope.maximum_timestep_seconds),
        ("maximum_horizon_seconds", envelope.maximum_horizon_seconds),
    )
    for field, value in values:
        _validate_finite(value, f"operating_envelope.{field}")
    if envelope.minimum_flow_m3s != 0:
        raise ModelReleaseError(
            "operating_envelope.minimum_flow_m3s must be 0 to cover closure decay"
        )
    if envelope.maximum_flow_m3s <= envelope.minimum_flow_m3s:
        raise ModelReleaseError(
            "operating_envelope.maximum_flow_m3s must exceed minimum_flow_m3s"
        )
    if envelope.minimum_timestep_seconds <= 0:
        raise ModelReleaseError(
            "operating_envelope.minimum_timestep_seconds must be > 0"
        )
    if envelope.maximum_timestep_seconds < envelope.minimum_timestep_seconds:
        raise ModelReleaseError(
            "operating_envelope.maximum_timestep_seconds must be >= minimum_timestep_seconds"
        )
    if envelope.maximum_horizon_seconds < envelope.maximum_timestep_seconds:
        raise ModelReleaseError(
            "operating_envelope.maximum_horizon_seconds must be >= maximum_timestep_seconds"
        )


def _validate_reach_parameters(
    reach_parameters: tuple[ReachResponseParameters, ...], source_ids: set[str]
) -> None:
    seen: set[str] = set()
    for parameters in reach_parameters:
        _validate_non_blank(parameters.reach_id, "reach_parameters[].reach_id")
        if parameters.reach_id in seen:
            raise ModelReleaseError(
                f"reach_parameters contains duplicate reach_id {parameters.reach_id!r}"
            )
        seen.add(parameters.reach_id)
        _validate_distribution(parameters.delay_seconds, "delay_seconds", minimum=0.0)
        _validate_distribution(
            parameters.loss_fraction,
            "loss_fraction",
            minimum=0.0,
            exclusive_maximum=1.0,
        )
        _validate_distribution(
            parameters.dispersion_seconds, "dispersion_seconds", minimum=0.0
        )
        _validate_distribution(
            parameters.capacity_m3s, "capacity_m3s", exclusive_minimum=0.0
        )
        if not parameters.evidence_refs:
            raise ModelReleaseError(
                f"reach_parameters[{parameters.reach_id!r}].evidence_refs must not be empty"
            )
        if len(set(parameters.evidence_refs)) != len(parameters.evidence_refs):
            raise ModelReleaseError(
                f"reach_parameters[{parameters.reach_id!r}].evidence_refs has duplicates"
            )
        unknown_refs = set(parameters.evidence_refs) - source_ids
        if unknown_refs:
            raise ModelReleaseError(
                f"reach_parameters[{parameters.reach_id!r}].evidence_refs contains unknown"
                f" sources: {sorted(unknown_refs)}"
            )


def _validate_distribution(
    distribution: ParameterDistribution,
    label: str,
    *,
    minimum: float | None = None,
    exclusive_minimum: float | None = None,
    exclusive_maximum: float | None = None,
) -> None:
    values = (distribution.lower, distribution.nominal, distribution.upper)
    for value in values:
        _validate_finite(value, label)
    if not distribution.lower <= distribution.nominal <= distribution.upper:
        raise ModelReleaseError(f"{label} must satisfy lower <= nominal <= upper")
    if minimum is not None and distribution.lower < minimum:
        raise ModelReleaseError(f"{label}.lower must be >= {minimum}")
    if exclusive_minimum is not None and distribution.lower <= exclusive_minimum:
        raise ModelReleaseError(f"{label}.lower must be > {exclusive_minimum}")
    if exclusive_maximum is not None and distribution.upper >= exclusive_maximum:
        raise ModelReleaseError(f"{label}.upper must be < {exclusive_maximum}")


def _validate_reach_coverage(
    reach_parameters: tuple[ReachResponseParameters, ...],
    unavailable_reaches: tuple[UnavailableReach, ...],
    expected_reach_ids: Iterable[str],
) -> None:
    expected_list = list(expected_reach_ids)
    if not expected_list:
        raise ModelReleaseError("expected_reach_ids must not be empty")
    if any(
        not isinstance(reach_id, str) or not reach_id.strip()
        for reach_id in expected_list
    ):
        raise ModelReleaseError("expected_reach_ids must contain non-empty strings")
    if len(set(expected_list)) != len(expected_list):
        raise ModelReleaseError("expected_reach_ids contains duplicates")

    available = {parameters.reach_id for parameters in reach_parameters}
    unavailable: set[str] = set()
    for reach in unavailable_reaches:
        _validate_non_blank(reach.reach_id, "unavailable_reaches[].reach_id")
        _validate_non_blank(reach.reason, "unavailable_reaches[].reason")
        if reach.reach_id in unavailable:
            raise ModelReleaseError(
                f"unavailable_reaches contains duplicate reach_id {reach.reach_id!r}"
            )
        unavailable.add(reach.reach_id)

    overlap = available & unavailable
    if overlap:
        raise ModelReleaseError(
            f"reaches cannot be both available and unavailable: {sorted(overlap)}"
        )
    expected = set(expected_list)
    covered = available | unavailable
    unknown = covered - expected
    if unknown:
        raise ModelReleaseError(
            f"model release contains unknown reaches: {sorted(unknown)}"
        )
    missing = expected - covered
    if missing:
        raise ModelReleaseError(
            f"model release is missing reaches without an unavailable record: {sorted(missing)}"
        )


def _parse_lineage(data: dict) -> ModelLineage:
    path = "lineage"
    _require_exact_keys(data, {"generator", "generator_version", "sources"}, path)
    return ModelLineage(
        generator=_require_string(data, "generator", path),
        generator_version=_require_string(data, "generator_version", path),
        sources=tuple(
            _parse_source(source, index)
            for index, source in enumerate(_require_array(data, "sources", path))
        ),
    )


def _parse_source(value: object, index: int) -> SourceArtifact:
    path = f"lineage.sources[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(data, {"source_id", "version", "sha256"}, path)
    return SourceArtifact(
        source_id=_require_string(data, "source_id", path),
        version=_require_string(data, "version", path),
        sha256=_require_string(data, "sha256", path),
    )


def _parse_operating_envelope(data: dict) -> OperatingEnvelope:
    path = "operating_envelope"
    fields = {
        "minimum_flow_m3s",
        "maximum_flow_m3s",
        "minimum_timestep_seconds",
        "maximum_timestep_seconds",
        "maximum_horizon_seconds",
    }
    _require_exact_keys(data, fields, path)
    return OperatingEnvelope(
        minimum_flow_m3s=_require_number(data, "minimum_flow_m3s", path),
        maximum_flow_m3s=_require_number(data, "maximum_flow_m3s", path),
        minimum_timestep_seconds=_require_number(
            data, "minimum_timestep_seconds", path
        ),
        maximum_timestep_seconds=_require_number(
            data, "maximum_timestep_seconds", path
        ),
        maximum_horizon_seconds=_require_number(data, "maximum_horizon_seconds", path),
    )


def _parse_reach_parameters(value: object, index: int) -> ReachResponseParameters:
    path = f"reach_parameters[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(
        data,
        {
            "reach_id",
            "delay_seconds",
            "loss_fraction",
            "dispersion_seconds",
            "capacity_m3s",
            "evidence_refs",
        },
        path,
    )
    evidence_refs = _require_array(data, "evidence_refs", path)
    if any(not isinstance(reference, str) for reference in evidence_refs):
        raise ModelReleaseError(f"{path}.evidence_refs must contain strings")
    return ReachResponseParameters(
        reach_id=_require_string(data, "reach_id", path),
        delay_seconds=_parse_distribution(
            _require_object(data, "delay_seconds", path), f"{path}.delay_seconds"
        ),
        loss_fraction=_parse_distribution(
            _require_object(data, "loss_fraction", path), f"{path}.loss_fraction"
        ),
        dispersion_seconds=_parse_distribution(
            _require_object(data, "dispersion_seconds", path),
            f"{path}.dispersion_seconds",
        ),
        capacity_m3s=_parse_distribution(
            _require_object(data, "capacity_m3s", path), f"{path}.capacity_m3s"
        ),
        evidence_refs=tuple(evidence_refs),
    )


def _parse_distribution(data: dict, path: str) -> ParameterDistribution:
    _require_exact_keys(data, {"lower", "nominal", "upper"}, path)
    return ParameterDistribution(
        lower=_require_number(data, "lower", path),
        nominal=_require_number(data, "nominal", path),
        upper=_require_number(data, "upper", path),
    )


def _parse_unavailable_reach(value: object, index: int) -> UnavailableReach:
    path = f"unavailable_reaches[{index}]"
    data = _as_object(value, path)
    _require_exact_keys(data, {"reach_id", "reason"}, path)
    return UnavailableReach(
        reach_id=_require_string(data, "reach_id", path),
        reason=_require_string(data, "reason", path),
    )


def _require_exact_keys(data: dict, expected: set[str], path: str) -> None:
    actual = set(data)
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        raise ModelReleaseError(f"{path} is missing required fields: {sorted(missing)}")
    if unexpected:
        raise ModelReleaseError(f"{path} has unexpected fields: {sorted(unexpected)}")


def _as_object(value: object, path: str) -> dict:
    if not isinstance(value, dict):
        raise ModelReleaseError(f"{path} must be an object")
    return value


def _require_object(data: dict, key: str, path: str) -> dict:
    return _as_object(data.get(key), f"{path}.{key}")


def _require_array(data: dict, key: str, path: str) -> list:
    value = data.get(key)
    if not isinstance(value, list):
        raise ModelReleaseError(f"{path}.{key} must be an array")
    return value


def _require_string(data: dict, key: str, path: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ModelReleaseError(f"{path}.{key} must be a string")
    return value


def _require_boolean(data: dict, key: str, path: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ModelReleaseError(f"{path}.{key} must be a boolean")
    return value


def _require_integer(data: dict, key: str, path: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelReleaseError(f"{path}.{key} must be an integer")
    return value


def _require_number(data: dict, key: str, path: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelReleaseError(f"{path}.{key} must be a number")
    return float(value)


def _parse_datetime(value: str, path: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelReleaseError(f"{path} must be an ISO-8601 datetime") from exc


def _validate_non_blank(value: str, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelReleaseError(f"{path} must be a non-empty string")


def _validate_finite(value: float, path: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ModelReleaseError(f"{path} must be a finite number")


def _validate_sha256(value: str, path: str) -> None:
    if not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None:
        raise ModelReleaseError(f"{path} must be a lowercase SHA-256 hex digest")
