"""Prediction persistence contract: records, identity, and the in-memory twin.

The repository stores ONE immutable header + ONE compressed canonical artifact
per prediction run. Identity is content-addressed over the canonical normalized
request (which already carries the snapshot/release pins), so an identical
request replays the stored record and a colliding id with different content is
a conflict — never an overwrite. This module is pure (no I/O); the asyncpg
implementation in db/prediction_repository.py must pin to this interface.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

PREDICTION_RUN_IDENTITY_PREFIX = b"flow-monitoring:prediction-run:v1\n"
PREDICTION_RUN_IDENTITY_VERSION = 1
# Identity v2 (PR 4.4b-1): a NEW domain-separated prefix so an identity-v2 run
# id can never collide with a v1 one. The v1 prefix and canonicalization are
# frozen forever — old rows must recompute and replay byte-identically.
PREDICTION_RUN_IDENTITY_PREFIX_V2 = b"flow-monitoring:prediction-run:v2\n"
PREDICTION_RUN_IDENTITY_VERSION_V2 = 2
# The key under which an identity-v2 request payload embeds the engine
# descriptor so the engine enters the run id AND can be re-checked on load.
PREDICTION_ENGINE_REQUEST_KEY = "prediction_engine"

_IDENTITY_PREFIXES = {
    PREDICTION_RUN_IDENTITY_VERSION: PREDICTION_RUN_IDENTITY_PREFIX,
    PREDICTION_RUN_IDENTITY_VERSION_V2: PREDICTION_RUN_IDENTITY_PREFIX_V2,
}


class PredictionRunConflict(ValueError):
    """The run id exists with DIFFERENT canonical request content."""


class PredictionArtifactCorrupt(ValueError):
    """A stored artifact fails hash/size/encoding verification."""


class PredictionStoreUnavailable(RuntimeError):
    """The persistence backend cannot serve the request right now."""


def canonical_json_bytes(payload) -> bytes:
    """THE canonical serialization for identity and artifacts: sorted keys,
    compact separators, UTF-8, non-finite numbers rejected.

    Identity is BYTE-EXACT, not Unicode-canonical: NFC vs NFD spellings of a
    visually identical string hash differently (a deliberate property of
    content-addressing — the ids in real requests are ASCII)."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def prediction_run_id_for(
    request_payload: dict, identity_version: int = PREDICTION_RUN_IDENTITY_VERSION
) -> str:
    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be a mapping")
    try:
        prefix = _IDENTITY_PREFIXES[identity_version]
    except (KeyError, TypeError):
        raise ValueError(f"unsupported identity_version {identity_version!r}")
    return hashlib.sha256(
        prefix + canonical_json_bytes(request_payload)
    ).hexdigest()


@dataclass(frozen=True)
class PredictionArtifactRecord:
    artifact_sha256: str
    media_type: str
    encoding: str
    encoding_version: int
    uncompressed_size_bytes: int
    compressed_payload: bytes


@dataclass(frozen=True)
class PredictionRunRecord:
    prediction_run_id: str
    identity_version: int
    response_schema_version: int
    request_payload: dict
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    starts_at: datetime
    ends_at: datetime
    timestep_seconds: float
    member_summaries: tuple[dict, ...]
    artifact: PredictionArtifactRecord
    # Identity-v2 engine pins (PR 4.4b-1). All None for v1 rows; all present
    # for v2 rows and consistent with the descriptor embedded in the request.
    engine_id: str | None = None
    semantic_contract_version: int | None = None
    build_digest: str | None = None
    engine_descriptor_content_hash: str | None = None

    def __post_init__(self) -> None:
        if self.identity_version not in _IDENTITY_PREFIXES:
            raise ValueError(
                f"unsupported identity_version {self.identity_version!r}"
            )
        expected = prediction_run_id_for(
            self.request_payload, self.identity_version
        )
        if self.prediction_run_id != expected:
            raise PredictionRunConflict(
                "prediction_run_id does not match its canonical request "
                f"content: {self.prediction_run_id!r} vs {expected!r}"
            )
        self._validate_engine_identity()

    def _validate_engine_identity(self) -> None:
        engine_fields = (
            self.engine_id,
            self.semantic_contract_version,
            self.build_digest,
            self.engine_descriptor_content_hash,
        )
        if self.identity_version == PREDICTION_RUN_IDENTITY_VERSION:
            if any(field is not None for field in engine_fields):
                raise ValueError(
                    "identity_version 1 runs must not carry engine identity fields"
                )
            return
        # identity_version 2: the engine pins are mandatory and must match the
        # descriptor embedded in the request payload (fail closed on drift).
        if any(field is None for field in engine_fields):
            raise ValueError(
                "identity_version 2 runs require the four engine identity fields"
            )
        embedded = self.request_payload.get(PREDICTION_ENGINE_REQUEST_KEY)
        if not isinstance(embedded, dict):
            raise PredictionRunConflict(
                "identity_version 2 request payload must embed the prediction "
                f"engine descriptor under {PREDICTION_ENGINE_REQUEST_KEY!r}"
            )
        # Validate the embedded block's FULL shape before comparing pins:
        # matching the four columns to an arbitrarily shaped block (bad
        # schema_version, extra keys, self-consistent-but-fabricated
        # content_hash) would let a replay carry fabricated provenance. Lazy
        # import: prediction_engine imports canonical_json_bytes from this
        # module, so a top-level import would be circular.
        from .prediction_engine import (
            PredictionEngineError,
            validate_prediction_engine_descriptor,
        )

        try:
            validate_prediction_engine_descriptor(embedded)
        except PredictionEngineError as exc:
            raise PredictionRunConflict(
                "identity_version 2 request payload embeds a malformed "
                f"prediction engine descriptor: {exc}"
            ) from exc
        if (
            embedded["engine_id"],
            embedded["semantic_contract_version"],
            embedded["build_digest"],
            embedded["content_hash"],
        ) != engine_fields:
            raise PredictionRunConflict(
                "engine identity fields do not match the descriptor embedded in "
                "the request payload"
            )


class PredictionRepository(Protocol):
    async def persist_prediction_run(
        self, run: PredictionRunRecord
    ) -> tuple[PredictionRunRecord, bool]:
        """Store once, immutably. Returns (stored record, replayed). An
        identical id with identical canonical request returns the FIRST
        stored record with replayed=True; different content raises
        PredictionRunConflict. Header and artifact commit atomically."""
        ...

    async def load_prediction_run(
        self, prediction_run_id: str
    ) -> PredictionRunRecord | None:
        ...


def _copied(run: PredictionRunRecord) -> PredictionRunRecord:
    """Defensive copy: the only mutable member is request_payload / summaries;
    round-trip through canonical JSON so callers can never mutate stored state."""
    return PredictionRunRecord(
        prediction_run_id=run.prediction_run_id,
        identity_version=run.identity_version,
        response_schema_version=run.response_schema_version,
        request_payload=json.loads(canonical_json_bytes(run.request_payload)),
        model_snapshot_id=run.model_snapshot_id,
        model_release_id=run.model_release_id,
        model_release_content_hash=run.model_release_content_hash,
        starts_at=run.starts_at,
        ends_at=run.ends_at,
        timestep_seconds=run.timestep_seconds,
        member_summaries=tuple(
            json.loads(canonical_json_bytes(summary))
            for summary in run.member_summaries
        ),
        artifact=run.artifact,
        engine_id=run.engine_id,
        semantic_contract_version=run.semantic_contract_version,
        build_digest=run.build_digest,
        engine_descriptor_content_hash=run.engine_descriptor_content_hash,
    )


class InMemoryPredictionRepository:
    """Spec twin for DB-free tests; db/prediction_repository.py pins to it."""

    def __init__(self) -> None:
        self._runs: dict[str, PredictionRunRecord] = {}

    async def persist_prediction_run(
        self, run: PredictionRunRecord
    ) -> tuple[PredictionRunRecord, bool]:
        existing = self._runs.get(run.prediction_run_id)
        if existing is not None:
            if canonical_json_bytes(existing.request_payload) != (
                canonical_json_bytes(run.request_payload)
            ):
                raise PredictionRunConflict(
                    f"prediction run {run.prediction_run_id!r} exists with "
                    "different request content"
                )
            return _copied(existing), True
        self._runs[run.prediction_run_id] = _copied(run)
        return _copied(run), False

    async def load_prediction_run(
        self, prediction_run_id: str
    ) -> PredictionRunRecord | None:
        stored = self._runs.get(prediction_run_id)
        return None if stored is None else _copied(stored)
