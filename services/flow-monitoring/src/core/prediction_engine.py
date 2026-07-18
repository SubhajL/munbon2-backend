"""Content-addressed identity of the running prediction ENGINE (PR 4.4b-1).

The engine descriptor pins the exact bytes of the prediction closure — the
ordered manifest of source files whose behaviour defines a prediction run —
into one deterministic, reproducible fingerprint. It is derived from file
bytes ALONE: no git state, branch, timestamp, or dirty-checkout ever enters
it, so a clean rebuild of the same tree yields a byte-identical descriptor.

The descriptor rides into a model snapshot (schema v3), so an engine change
changes the snapshot id and therefore the identity-v2 prediction run id: a
prediction produced by different engine bytes can never collide with one
produced by these bytes. Canonicalization is the SAME `content_hash` /
`canonical_json_bytes` used by the snapshot and run identity — never a second
copy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from .demand_contract import content_hash
from .prediction_repository import canonical_json_bytes

__all__ = [
    "PredictionEngineError",
    "PREDICTION_ENGINE_ID",
    "PREDICTION_ENGINE_SCHEMA_VERSION",
    "PREDICTION_ENGINE_SEMANTIC_CONTRACT_VERSION",
    "PREDICTION_ENGINE_MANIFEST",
    "PREDICTION_ENGINE_MANIFEST_PREFIX",
    "PREDICTION_ENGINE_DESCRIPTOR_FIELDS",
    "build_prediction_engine_descriptor",
    "descriptor_from_build_digest",
    "load_prediction_engine_descriptor",
    "validate_prediction_engine_descriptor",
    "engine_identity_fields",
]

PREDICTION_ENGINE_ID = "munbon.flow-monitoring.network-transient"
PREDICTION_ENGINE_SCHEMA_VERSION = 1
PREDICTION_ENGINE_SEMANTIC_CONTRACT_VERSION = 1

# The EXACT prediction-behaviour closure, relative to the service root, in a
# FIXED sorted order. Any edit to one of these files re-fingerprints the
# engine; nothing outside it is part of the pinned identity.
PREDICTION_ENGINE_MANIFEST: tuple[str, ...] = tuple(
    sorted(
        (
            "requirements.txt",
            "src/api/control.py",
            "src/core/branch_split.py",
            "src/core/fulfillment.py",
            "src/core/model_snapshot.py",
            "src/core/muskingum_cunge.py",
            "src/core/network_topology.py",
            "src/core/network_transient.py",
            "src/core/reach_response.py",
            "src/core/routing_topology.py",
            "src/schemas/control.py",
            "src/services/control_prediction_service.py",
        )
    )
)

# Domain separation so this digest can never be confused with another sha256
# over JSON (run identity, artifact bytes, model release).
PREDICTION_ENGINE_MANIFEST_PREFIX = b"flow-monitoring:prediction-engine-manifest:v1\n"

# The four content-addressed fields; content_hash is computed OVER these.
PREDICTION_ENGINE_DESCRIPTOR_FIELDS = (
    "schema_version",
    "engine_id",
    "semantic_contract_version",
    "build_digest",
)
_DESCRIPTOR_KEYS = frozenset(PREDICTION_ENGINE_DESCRIPTOR_FIELDS) | {"content_hash"}
_SHA256_HEX = tuple("0123456789abcdef")


class PredictionEngineError(ValueError):
    """The prediction engine descriptor is missing, malformed, or drifted."""


def _is_sha256_hex(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _SHA256_HEX for character in value)
    )


def descriptor_from_build_digest(
    build_digest: str,
    *,
    engine_id: str = PREDICTION_ENGINE_ID,
    semantic_contract_version: int = PREDICTION_ENGINE_SEMANTIC_CONTRACT_VERSION,
) -> dict:
    """Assemble a descriptor from an already-computed build digest.

    The ONE place a descriptor's content_hash is computed, so a fabricated
    descriptor (tests) and a real one are hashed identically."""
    if not _is_sha256_hex(build_digest):
        raise PredictionEngineError("build_digest must be a 64-char sha256 hex")
    fields = {
        "schema_version": PREDICTION_ENGINE_SCHEMA_VERSION,
        "engine_id": engine_id,
        "semantic_contract_version": semantic_contract_version,
        "build_digest": build_digest,
    }
    return {**fields, "content_hash": content_hash(fields)}


def build_prediction_engine_descriptor(source_root: Path) -> dict:
    """Fingerprint the prediction closure from file bytes at ``source_root``.

    Reads every manifest file in the fixed sorted order, hashes each, then
    hashes the ordered ``(relative_path, file_sha256)`` list under a
    domain-separated prefix. Reproducible from bytes alone."""
    root = Path(source_root)
    ordered: list[list[str]] = []
    for relative_path in PREDICTION_ENGINE_MANIFEST:
        file_path = root / relative_path
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            raise PredictionEngineError(
                f"prediction engine manifest file is unreadable: {relative_path} ({exc})"
            ) from exc
        ordered.append([relative_path, hashlib.sha256(data).hexdigest()])
    build_digest = hashlib.sha256(
        PREDICTION_ENGINE_MANIFEST_PREFIX + canonical_json_bytes(ordered)
    ).hexdigest()
    return descriptor_from_build_digest(build_digest)


def validate_prediction_engine_descriptor(descriptor: Mapping) -> None:
    """Fail closed unless ``descriptor`` has the EXACT shape and its content_hash
    re-derives from its own fields (drift → raise)."""
    if not isinstance(descriptor, Mapping):
        raise PredictionEngineError("engine descriptor must be a mapping")
    keys = set(descriptor)
    if keys != _DESCRIPTOR_KEYS:
        raise PredictionEngineError(
            f"engine descriptor keys must be exactly {sorted(_DESCRIPTOR_KEYS)}, "
            f"got {sorted(keys)}"
        )
    if descriptor["schema_version"] != PREDICTION_ENGINE_SCHEMA_VERSION:
        raise PredictionEngineError(
            f"engine descriptor schema_version must be "
            f"{PREDICTION_ENGINE_SCHEMA_VERSION}"
        )
    engine_id = descriptor["engine_id"]
    if not isinstance(engine_id, str) or not engine_id.strip():
        raise PredictionEngineError("engine_id must be a non-blank string")
    semantic_contract_version = descriptor["semantic_contract_version"]
    if (
        isinstance(semantic_contract_version, bool)
        or not isinstance(semantic_contract_version, int)
    ):
        raise PredictionEngineError("semantic_contract_version must be an int")
    if not _is_sha256_hex(descriptor["build_digest"]):
        raise PredictionEngineError("build_digest must be a 64-char sha256 hex")
    if not _is_sha256_hex(descriptor["content_hash"]):
        raise PredictionEngineError("content_hash must be a 64-char sha256 hex")
    recomputed = content_hash(
        {field: descriptor[field] for field in PREDICTION_ENGINE_DESCRIPTOR_FIELDS}
    )
    if recomputed != descriptor["content_hash"]:
        raise PredictionEngineError(
            "engine descriptor content_hash does not match its fields (drift)"
        )


def load_prediction_engine_descriptor(path: Path) -> dict:
    """Load, validate, and return the committed descriptor. Missing/malformed/
    drifted all fail closed as PredictionEngineError."""
    file_path = Path(path)
    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PredictionEngineError(
            f"engine descriptor is not readable at {file_path}: {exc}"
        ) from exc
    try:
        descriptor = json.loads(raw)
    except ValueError as exc:
        raise PredictionEngineError(
            f"engine descriptor at {file_path} is not valid JSON: {exc}"
        ) from exc
    validate_prediction_engine_descriptor(descriptor)
    return descriptor


def engine_identity_fields(descriptor: Mapping) -> dict:
    """The four identity columns a v2 prediction run persists, from a validated
    descriptor. Validates first so a malformed descriptor never leaks."""
    validate_prediction_engine_descriptor(descriptor)
    return {
        "engine_id": descriptor["engine_id"],
        "semantic_contract_version": descriptor["semantic_contract_version"],
        "build_digest": descriptor["build_digest"],
        "engine_descriptor_content_hash": descriptor["content_hash"],
    }
