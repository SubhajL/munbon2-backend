"""Artifact and identity unit tests — Codex plan §4 "Artifact and identity" slice.

Covers: identity stress-free equivalence, lineage-pin drift, encode/decode
round-trip, oversized rejection (encode + both decode paths), hash/stream
corruption, unknown encoding version, exact-three-member summaries.
"""
import hashlib
import json
import zlib

import pytest

from core.prediction_repository import (
    PredictionArtifactCorrupt,
    PredictionArtifactRecord,
    canonical_json_bytes,
    prediction_run_id_for,
)
from services.prediction_artifact_service import (
    decode_prediction_artifact,
    encode_prediction_artifact,
    summarize_prediction_members,
)


def _base_request_payload() -> dict:
    return {
        "model_snapshot_id": "a" * 64,
        "model_release_id": "engineering-prior-v3-v1",
        "model_release_content_hash": "b" * 64,
        "initialization": {"kind": "dry"},
        "starts_at": "2026-07-20T23:00:00Z",
        "ends_at": "2026-07-21T05:00:00Z",
        "timestep_seconds": 300.0,
        "source_flow_events": [
            {
                "node_id": "S",
                "effective_at": "2026-07-20T23:00:00Z",
                "flow_m3s": 0.5,
            },
        ],
        "operator_withdrawal_events": [],
        "branch_allocations": [],
        "section_requirements": [
            {
                "requirement_id": "REQ-TEST-1",
                "section_id": "SEC-TEST-1",
                "delivery_node_id": "M(0,0;2,1)",
                "window_start": "2026-07-20T23:00:00Z",
                "window_end": "2026-07-21T05:00:00Z",
                "required_volume_m3": 50000.0,
                "maximum_delivery_m3s": 1.0,
                "approved_excess_m3": 0.0,
            },
        ],
    }


class TestPredictionRunId:
    """Run identity is a deterministic SHA-256 of a versioned prefix plus
    the canonical JSON request — equivalent inputs always land on the same
    stable id, while any lineage-pin drift (snapshot or release) changes it."""

    def test_prediction_run_id_normalizes_equivalent_requests(self):
        payload = _base_request_payload()
        id_a = prediction_run_id_for(payload)
        id_b = prediction_run_id_for(payload)
        assert id_a == id_b, "identical payloads must produce identical ids"
        payload_copy = json.loads(json.dumps(payload))
        id_c = prediction_run_id_for(payload_copy)
        assert id_a == id_c, (
            "JSON round-trip must preserve identity"
        )
        assert len(id_a) == 64, "run id must be a 256-bit hex string"
        assert all(c in "0123456789abcdef" for c in id_a)

    def test_prediction_run_id_changes_with_every_lineage_pin(self):
        base = _base_request_payload()
        base_id = prediction_run_id_for(base)

        drift_snapshot = {**base, "model_snapshot_id": "c" * 64}
        assert prediction_run_id_for(drift_snapshot) != base_id

        drift_release_id = {
            **base,
            "model_release_id": "engineering-prior-v999",
        }
        assert prediction_run_id_for(drift_release_id) != base_id

        drift_release_hash = {
            **base,
            "model_release_content_hash": "d" * 64,
        }
        assert prediction_run_id_for(drift_release_hash) != base_id

    def test_prediction_run_id_rejects_non_dict_input(self):
        with pytest.raises(ValueError, match="request_payload must be a mapping"):
            prediction_run_id_for("not-a-dict")  # type: ignore[arg-type]


class TestPredictionArtifactEncodeDecode:
    """Canonical JSON + zlib(level=6) round-trip preserves the response body
    byte-identically; encoding version, media type, and size are declared
    and validated on both paths."""

    def test_encode_decode_prediction_artifact_round_trips_exact_bytes(self):
        response = canonical_json_bytes(
            {
                "schema_version": 2,
                "persistence": "stored",
                "prediction_run_id": "e" * 64,
                "members": [{"member": m} for m in ("lower", "nominal", "upper")],
            }
        )
        record = encode_prediction_artifact(response)
        assert record.media_type == "application/json"
        assert record.encoding == "canonical-json+zlib"
        assert record.encoding_version == 1
        assert record.uncompressed_size_bytes == len(response)
        assert record.artifact_sha256 == hashlib.sha256(response).hexdigest()
        assert len(record.compressed_payload) > 0

        decompressed = decode_prediction_artifact(record)
        assert decompressed == response, "zlib round-trip must be byte-exact"

    def test_encode_rejects_oversized_uncompressed_artifact(self):
        # Build an artifact just over the 64 MiB limit
        big = canonical_json_bytes({"data": "x" * (64 * 1024 * 1024 + 1)})
        with pytest.raises(PredictionArtifactCorrupt, match="exceeds"):
            encode_prediction_artifact(big)

    def test_decode_rejects_declared_or_expanded_oversize(self):
        response = canonical_json_bytes({"ok": True})
        record = encode_prediction_artifact(response)

        # Declared size > 64 MiB should fail
        tampered = PredictionArtifactRecord(
            artifact_sha256=record.artifact_sha256,
            media_type=record.media_type,
            encoding=record.encoding,
            encoding_version=record.encoding_version,
            uncompressed_size_bytes=64 * 1024 * 1024 + 1,
            compressed_payload=record.compressed_payload,
        )
        with pytest.raises(
            PredictionArtifactCorrupt, match="outside the artifact bounds"
        ):
            decode_prediction_artifact(tampered)

        # Declared size = 0 should fail
        tampered_zero = PredictionArtifactRecord(
            artifact_sha256=record.artifact_sha256,
            media_type=record.media_type,
            encoding=record.encoding,
            encoding_version=record.encoding_version,
            uncompressed_size_bytes=0,
            compressed_payload=record.compressed_payload,
        )
        with pytest.raises(
            PredictionArtifactCorrupt, match="outside the artifact bounds"
        ):
            decode_prediction_artifact(tampered_zero)

    def test_decode_rejects_hash_or_stream_corruption(self):
        response = canonical_json_bytes({"ok": True})
        record = encode_prediction_artifact(response)

        # Tamper compressed bytes (last 4 bytes zeroed)
        tampered_bytes = record.compressed_payload[:-4] + b"\x00\x00\x00\x00"
        tampered = PredictionArtifactRecord(
            artifact_sha256=record.artifact_sha256,
            media_type=record.media_type,
            encoding=record.encoding,
            encoding_version=record.encoding_version,
            uncompressed_size_bytes=record.uncompressed_size_bytes,
            compressed_payload=tampered_bytes,
        )
        with pytest.raises(PredictionArtifactCorrupt):
            decode_prediction_artifact(tampered)

        # Trailing data after zlib stream
        extra_payload = (
            record.compressed_payload
            + zlib.compress(b"extra trailing garbage")
        )
        tampered_extra = PredictionArtifactRecord(
            artifact_sha256=record.artifact_sha256,
            media_type=record.media_type,
            encoding=record.encoding,
            encoding_version=record.encoding_version,
            uncompressed_size_bytes=record.uncompressed_size_bytes,
            compressed_payload=extra_payload,
        )
        with pytest.raises(
            PredictionArtifactCorrupt, match="trailing data"
        ):
            decode_prediction_artifact(tampered_extra)

        # Wrong hash — content does not match
        tampered_hash = PredictionArtifactRecord(
            artifact_sha256="f" * 64,
            media_type=record.media_type,
            encoding=record.encoding,
            encoding_version=record.encoding_version,
            uncompressed_size_bytes=record.uncompressed_size_bytes,
            compressed_payload=record.compressed_payload,
        )
        with pytest.raises(
            PredictionArtifactCorrupt, match="content hash"
        ):
            decode_prediction_artifact(tampered_hash)

    def test_decode_rejects_unknown_encoding_version(self):
        response = canonical_json_bytes({"ok": True})
        record = encode_prediction_artifact(response)
        tampered = PredictionArtifactRecord(
            artifact_sha256=record.artifact_sha256,
            media_type=record.media_type,
            encoding="broken-codec",
            encoding_version=99,
            uncompressed_size_bytes=record.uncompressed_size_bytes,
            compressed_payload=record.compressed_payload,
        )
        with pytest.raises(
            PredictionArtifactCorrupt, match="unknown artifact encoding"
        ):
            decode_prediction_artifact(tampered)

    def test_encode_rejects_empty_or_non_bytes(self):
        with pytest.raises(
            PredictionArtifactCorrupt, match="non-empty bytes"
        ):
            encode_prediction_artifact(b"")

        with pytest.raises(PredictionArtifactCorrupt):
            encode_prediction_artifact("not bytes")  # type: ignore[arg-type]


class TestMemberSummaries:
    """summarize_prediction_members extracts exactly three ordered summary
    structs — without timelines, release parameters, or key drift."""

    def test_member_summaries_cover_exactly_three_members(self):
        response = {
            "members": [
                {
                    "member": "lower",
                    "status": "completed",
                    "predicted_delivered_total_m3": 12500.0,
                    "violations": [
                        {"kind": "requirement_shortfall", "extra": "ignored"},
                    ],
                    "infeasibility": None,
                    "timeline": {"should": "be omitted from summary"},
                },
                {
                    "member": "nominal",
                    "status": "completed",
                    "predicted_delivered_total_m3": 10500.0,
                    "violations": [
                        {"kind": "requirement_shortfall"},
                        {"kind": "withdrawal_shortfall"},
                    ],
                    "infeasibility": None,
                },
                {
                    "member": "upper",
                    "status": "infeasible",
                    "predicted_delivered_total_m3": None,
                    "violations": [],
                    "infeasibility": {
                        "kind": "reach_capacity_exceeded",
                        "reach_id": "C_S_A",
                    },
                },
            ]
        }
        summaries = summarize_prediction_members(response)

        assert len(summaries) == 3
        assert [s["member"] for s in summaries] == ["lower", "nominal", "upper"]

        assert summaries[0]["predicted_delivered_total_m3"] == 12500.0
        assert summaries[0]["violation_kinds"] == ["requirement_shortfall"]
        assert summaries[0]["infeasibility_kind"] is None
        assert "timeline" not in summaries[0]

        assert summaries[1]["violation_kinds"] == [
            "requirement_shortfall",
            "withdrawal_shortfall",
        ]

        assert summaries[2]["status"] == "infeasible"
        assert summaries[2]["predicted_delivered_total_m3"] is None
        assert summaries[2]["infeasibility_kind"] == "reach_capacity_exceeded"

    def test_summarize_rejects_incorrect_member_count(self):
        for bad_members in (
            [],
            [{"member": "only-one"}],
            [{"member": m} for m in ("a", "b", "c", "d")],
        ):
            with pytest.raises(
                ValueError, match="exactly three members"
            ):
                summarize_prediction_members({"members": bad_members})

        with pytest.raises(ValueError, match="exactly three members"):
            summarize_prediction_members({"members": "not-a-list"})
