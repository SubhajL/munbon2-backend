"""asyncpg implementation of the PredictionRepository Protocol (PR 4.1).

This module ONLY implements the persistence Protocol pinned in
core/prediction_repository.py — it never creates schema, never updates,
never upserts, never deletes. Schema is owned exclusively by the migration
runner in migrations/. A missing or unmigrated table logs a warning and
returns None; the API layer is responsible for surfacing 503.
"""

from __future__ import annotations

import json
from datetime import timezone

import asyncpg
import structlog

from core.prediction_repository import (

    PredictionArtifactCorrupt,
    PredictionArtifactRecord,

    PredictionRunConflict,
    PredictionRunRecord,
    PredictionStoreUnavailable,
    canonical_json_bytes,
)

logger = structlog.get_logger()


def _row_to_run(row: dict) -> PredictionRunRecord:
    """Deserialize one asyncpg row into the frozen record type.

    member_summaries is always a tuple of dicts; request_payload is a parsed
    dict. JSONB columns come back as Python objects from asyncpg."""
    artifact = PredictionArtifactRecord(
        artifact_sha256=row["artifact_sha256"],
        media_type=row["media_type"],
        encoding=row["encoding"],
        encoding_version=row["encoding_version"],
        uncompressed_size_bytes=row["uncompressed_size_bytes"],
        compressed_payload=bytes(row["compressed_payload"]),
    )
    # asyncpg returns JSONB as text when no codec is registered: parse the
    # whole column, never iterate the raw string.
    summaries = tuple(json.loads(row["member_summaries"]))
    # asyncpg returns timestamptz as datetime with tzinfo; normalize to UTC
    starts_at = row["starts_at"]
    ends_at = row["ends_at"]
    stored_at = row["stored_at"]
    if starts_at is not None and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if ends_at is not None and ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    if stored_at is not None and stored_at.tzinfo is None:
        stored_at = stored_at.replace(tzinfo=timezone.utc)

    try:
        return _record_from_row_fields(row, artifact, summaries,
                                       starts_at, ends_at)
    except PredictionRunConflict as exc:
        # A stored row whose payload no longer hashes to its own id is
        # STORAGE corruption, not a client conflict — surface it as such.
        raise PredictionArtifactCorrupt(
            f"stored prediction run {row['prediction_run_id']!r} fails "
            f"identity recomputation: {exc}"
        ) from exc


def _record_from_row_fields(row, artifact, summaries, starts_at, ends_at):
    return PredictionRunRecord(
        prediction_run_id=row["prediction_run_id"],
        identity_version=row["identity_version"],
        response_schema_version=row["response_schema_version"],
        request_payload=json.loads(row["request_payload"]),
        model_snapshot_id=row["model_snapshot_id"],
        model_release_id=row["model_release_id"],
        model_release_content_hash=row["model_release_content_hash"],
        starts_at=starts_at,
        ends_at=ends_at,
        timestep_seconds=row["timestep_seconds"],
        member_summaries=summaries,
        artifact=artifact,
    )


async def create_prediction_repository_if_migrated(
    pool: asyncpg.Pool,
) -> PostgresPredictionRepository | None:
    """Probe both prediction tables exist; return a wired repository or None.

    This never creates schema — migrations/ owns that exclusively. A missing
    table logs a warning; the caller leaves prediction endpoints at 503."""
    try:
        async with pool.acquire() as conn:
            runs = await conn.fetchval(
                "SELECT to_regclass('flow_monitoring.prediction_runs')"
            )
            artifacts = await conn.fetchval(
                "SELECT to_regclass('flow_monitoring.prediction_artifacts')"
            )
    except (asyncpg.PostgresError, OSError) as exc:
        logger.warning(
            "prediction_repository.migration_probe_failed",
            error=str(exc),
        )
        return None

    if runs is None or artifacts is None:
        logger.warning(
            "prediction_repository.not_migrated",
            runs_table=bool(runs),
            artifacts_table=bool(artifacts),
        )
        return None

    logger.info("prediction_repository.migrated_and_ready")
    return PostgresPredictionRepository(pool)


class PostgresPredictionRepository:
    """asyncpg-backed repository pinning the PredictionRepository Protocol.

    Every persist is an atomic header-then-artifact insert in ONE transaction.
    The deferred composite FK validates at commit — either both rows land or
    neither does. On unique-violation race: retry once, load the winner,
    validate request identity, and return the immutable winner.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def persist_prediction_run(
        self, run: PredictionRunRecord,
    ) -> tuple[PredictionRunRecord, bool]:
        try:
            return await self._persist_once(run)
        except asyncpg.exceptions.UniqueViolationError:
            logger.info(
                "prediction_repository.unique_race_retrying",
                prediction_run_id=run.prediction_run_id,
            )
        except (asyncpg.PostgresError, OSError) as exc:
            # EVERY non-race DB failure is fail-closed unavailability — the
            # route must answer 503, never a raw 500.
            raise PredictionStoreUnavailable(
                f"failed to persist prediction run: {exc}"
            ) from exc
        try:
            winner = await self.load_prediction_run(run.prediction_run_id)
        except (asyncpg.PostgresError, OSError) as exc:
            raise PredictionStoreUnavailable(
                f"failed to load prediction run after race: {exc}"
            ) from exc
        if winner is None:
            raise PredictionStoreUnavailable(
                "prediction run disappeared after unique-violation race"
            )
        if canonical_json_bytes(winner.request_payload) != (
            canonical_json_bytes(run.request_payload)
        ):
            raise PredictionRunConflict(
                f"prediction run {run.prediction_run_id!r} exists "
                "with different request content"
            )
        return winner, True

    async def _persist_once(
        self, run: PredictionRunRecord,
    ) -> tuple[PredictionRunRecord, bool]:
        async with self._pool.acquire() as conn, conn.transaction():
            # Insert header row first (no artifact FK yet — deferred check)
            await conn.execute(
                """
                INSERT INTO flow_monitoring.prediction_runs (
                    prediction_run_id,
                    identity_version,
                    response_schema_version,
                    request_payload,
                    model_snapshot_id,
                    model_release_id,
                    model_release_content_hash,
                    starts_at,
                    ends_at,
                    timestep_seconds,
                    member_summaries,
                    artifact_sha256
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                """,
                run.prediction_run_id,
                run.identity_version,
                run.response_schema_version,
                canonical_json_bytes(run.request_payload).decode("utf-8"),
                run.model_snapshot_id,
                run.model_release_id,
                run.model_release_content_hash,
                run.starts_at,
                run.ends_at,
                run.timestep_seconds,
                canonical_json_bytes(list(run.member_summaries)).decode(
                    "utf-8"
                ),
                run.artifact.artifact_sha256,
            )
            # Insert artifact — deferred FK validates at commit
            await conn.execute(
                """
                INSERT INTO flow_monitoring.prediction_artifacts (
                    prediction_run_id,
                    artifact_sha256,
                    media_type,
                    encoding,
                    encoding_version,
                    uncompressed_size_bytes,
                    compressed_payload
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7
                )
                """,
                run.prediction_run_id,
                run.artifact.artifact_sha256,
                run.artifact.media_type,
                run.artifact.encoding,
                run.artifact.encoding_version,
                run.artifact.uncompressed_size_bytes,
                run.artifact.compressed_payload,
            )
            return run, False

    async def load_prediction_run(
        self, prediction_run_id: str,
    ) -> PredictionRunRecord | None:
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        r.prediction_run_id,
                        r.identity_version,
                        r.response_schema_version,
                        r.request_payload,
                        r.model_snapshot_id,
                        r.model_release_id,
                        r.model_release_content_hash,
                        r.starts_at,
                        r.ends_at,
                        r.timestep_seconds,
                        r.member_summaries,
                        r.artifact_sha256,
                        r.stored_at,
                        a.media_type,
                        a.encoding,
                        a.encoding_version,
                        a.uncompressed_size_bytes,
                        a.compressed_payload
                    FROM flow_monitoring.prediction_runs r
                    LEFT JOIN flow_monitoring.prediction_artifacts a
                        ON r.prediction_run_id = a.prediction_run_id
                        AND r.artifact_sha256 = a.artifact_sha256
                    WHERE r.prediction_run_id = $1
                    """,
                    prediction_run_id,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PredictionStoreUnavailable(
                f"failed to load prediction run: {exc}"
            ) from exc

        if row is None:
            return None
        # A header row without the artifact join is corruption
        if row["media_type"] is None:
            raise PredictionArtifactCorrupt(
                f"prediction run {prediction_run_id!r} has a header row "
                "but its artifact row is missing — the data is corrupt"
            )
        return _row_to_run(dict(row))
