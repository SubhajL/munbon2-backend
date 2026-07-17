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


def prediction_run_id_for(request_payload: dict) -> str:
    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be a mapping")
    return hashlib.sha256(
        PREDICTION_RUN_IDENTITY_PREFIX + canonical_json_bytes(request_payload)
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

    def __post_init__(self) -> None:
        expected = prediction_run_id_for(self.request_payload)
        if self.prediction_run_id != expected:
            raise PredictionRunConflict(
                "prediction_run_id does not match its canonical request "
                f"content: {self.prediction_run_id!r} vs {expected!r}"
            )
        if self.identity_version != PREDICTION_RUN_IDENTITY_VERSION:
            raise ValueError(
                f"unsupported identity_version {self.identity_version!r}"
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
