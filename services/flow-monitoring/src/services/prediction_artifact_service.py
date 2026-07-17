"""Pure encode/decode for the ONE compressed canonical prediction artifact.

The artifact is the exact response body a client received; replay/GET must
return it byte-identically. Encoding is versioned and bounded: corruption,
truncation, trailing garbage, oversize, or non-canonical content all fail
closed as PredictionArtifactCorrupt — never a partially decoded result.
"""

from __future__ import annotations

import hashlib
import json
import zlib

from core.prediction_repository import (
    PredictionArtifactCorrupt,
    PredictionArtifactRecord,
    canonical_json_bytes,
)

PREDICTION_ARTIFACT_MEDIA_TYPE = "application/json"
PREDICTION_ARTIFACT_ENCODING = "canonical-json+zlib"
PREDICTION_ARTIFACT_ENCODING_VERSION = 1
PREDICTION_ARTIFACT_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
_ZLIB_LEVEL = 6


def _require_canonical(response_bytes: bytes) -> None:
    try:
        payload = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PredictionArtifactCorrupt(
            f"artifact bytes are not valid UTF-8 JSON: {exc}"
        ) from exc
    if canonical_json_bytes(payload) != response_bytes:
        raise PredictionArtifactCorrupt(
            "artifact bytes are not in canonical JSON form"
        )


def encode_prediction_artifact(response_bytes: bytes) -> PredictionArtifactRecord:
    if not isinstance(response_bytes, bytes) or not response_bytes:
        raise PredictionArtifactCorrupt("artifact bytes must be non-empty bytes")
    if len(response_bytes) > PREDICTION_ARTIFACT_MAX_UNCOMPRESSED_BYTES:
        raise PredictionArtifactCorrupt(
            f"artifact of {len(response_bytes)} bytes exceeds the "
            f"{PREDICTION_ARTIFACT_MAX_UNCOMPRESSED_BYTES}-byte limit"
        )
    _require_canonical(response_bytes)
    return PredictionArtifactRecord(
        artifact_sha256=hashlib.sha256(response_bytes).hexdigest(),
        media_type=PREDICTION_ARTIFACT_MEDIA_TYPE,
        encoding=PREDICTION_ARTIFACT_ENCODING,
        encoding_version=PREDICTION_ARTIFACT_ENCODING_VERSION,
        uncompressed_size_bytes=len(response_bytes),
        compressed_payload=zlib.compress(response_bytes, _ZLIB_LEVEL),
    )


def decode_prediction_artifact(record: PredictionArtifactRecord) -> bytes:
    if record.encoding != PREDICTION_ARTIFACT_ENCODING or (
        record.encoding_version != PREDICTION_ARTIFACT_ENCODING_VERSION
    ):
        raise PredictionArtifactCorrupt(
            f"unknown artifact encoding {record.encoding!r} "
            f"v{record.encoding_version!r}"
        )
    if not (
        0
        < record.uncompressed_size_bytes
        <= PREDICTION_ARTIFACT_MAX_UNCOMPRESSED_BYTES
    ):
        raise PredictionArtifactCorrupt(
            f"declared uncompressed size {record.uncompressed_size_bytes!r} "
            "is outside the artifact bounds"
        )
    decompressor = zlib.decompressobj()
    try:
        response_bytes = decompressor.decompress(
            record.compressed_payload, record.uncompressed_size_bytes
        )
    except zlib.error as exc:
        raise PredictionArtifactCorrupt(f"artifact zlib stream failed: {exc}") from exc
    if decompressor.unconsumed_tail or not decompressor.eof or (
        decompressor.unused_data
    ):
        raise PredictionArtifactCorrupt(
            "artifact stream is truncated, oversized, or carries trailing data"
        )
    if len(response_bytes) != record.uncompressed_size_bytes:
        raise PredictionArtifactCorrupt(
            f"artifact expanded to {len(response_bytes)} bytes but declared "
            f"{record.uncompressed_size_bytes}"
        )
    digest = hashlib.sha256(response_bytes).hexdigest()
    if digest != record.artifact_sha256:
        raise PredictionArtifactCorrupt(
            "artifact content hash does not match the stored digest"
        )
    _require_canonical(response_bytes)
    return response_bytes


def summarize_prediction_members(response_payload: dict) -> tuple[dict, ...]:
    """Exactly three ordered relational summaries — never timelines or
    release parameters (the artifact is the single trajectory authority)."""
    members = response_payload.get("members")
    if not isinstance(members, list) or len(members) != 3:
        raise ValueError("response payload must carry exactly three members")
    summaries = []
    for member in members:
        infeasibility = member.get("infeasibility")
        summaries.append(
            {
                "member": member["member"],
                "status": member["status"],
                "predicted_delivered_total_m3": member[
                    "predicted_delivered_total_m3"
                ],
                "violation_kinds": sorted(
                    {violation["kind"] for violation in member["violations"]}
                ),
                "infeasibility_kind": (
                    None if infeasibility is None else infeasibility["kind"]
                ),
            }
        )
    return tuple(summaries)
