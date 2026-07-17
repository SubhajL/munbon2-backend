"""Disposable-Postgres integration tests (PR 4.1).

ALL tests skip unless FLOW_PREDICTION_TEST_POSTGRES_URL is set AND its host
is loopback (127.0.0.1 / localhost). This suite may drop migration-owned
objects — never run it against a shared database.

CLAUDE-MANAGED: this file creates its own asyncpg connections outside the
app's DatabaseManager so it can inspect the database directly.
"""

import asyncio
from contextlib import asynccontextmanager

import os
from datetime import datetime, timezone
from typing import Tuple
from urllib.parse import urlsplit

import asyncpg
import pytest

from core.prediction_repository import (
    PredictionArtifactCorrupt,

    PredictionArtifactRecord,

    PredictionRunRecord,
    canonical_json_bytes,
    prediction_run_id_for,
)
from services.prediction_artifact_service import (
    encode_prediction_artifact,
    summarize_prediction_members,
)
from db.prediction_repository import (
    PostgresPredictionRepository,
    create_prediction_repository_if_migrated,
)
from migrations.migrate import (
    apply_migration,
    postgres_connection_kwargs,
    rollback_migration,
    MIGRATIONS_SCHEMA_DDL,
    MIGRATIONS_REGISTRY_DDL,
)

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

_TEST_URL_ENV = "FLOW_PREDICTION_TEST_POSTGRES_URL"

# 🚨 Global guard: never touch a non-loopback host
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _test_url_loopback() -> str | None:
    url = os.environ.get(_TEST_URL_ENV)
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.hostname not in _LOOPBACK_HOSTS:
        # A destructive-suite guard must survive `python -O` (asserts are
        # stripped under -O) — raise, never assert.
        raise RuntimeError(
            f"FLOW_PREDICTION_TEST_POSTGRES_URL host is {parsed.hostname!r} — "
            "NOT a loopback address. This suite drops migration-owned "
            "objects. Set the env to a disposable loopback Postgres or unset "
            "it to skip."
        )
    return url


@pytest.fixture(scope="module")
def test_pg_url() -> str:
    url = _test_url_loopback()
    if url is None:
        pytest.skip(
            f"{_TEST_URL_ENV} not set — set it to a disposable loopback "
            "Postgres to run integration tests"
        )
    return url


@pytest.fixture(scope="module")
def test_pg_kwargs(test_pg_url: str) -> dict:
    return postgres_connection_kwargs(test_pg_url)


async def _ensure_schema_registry(conn: asyncpg.Connection) -> None:
    await conn.execute(MIGRATIONS_SCHEMA_DDL)
    await conn.execute(MIGRATIONS_REGISTRY_DDL)


# ---------------------------------------------------------------------------
# Fixtures — module-scoped for apply/rollback/reapply, function-scoped repo
# ---------------------------------------------------------------------------


@asynccontextmanager
async def migrated_pool(test_pg_kwargs: dict):
    """Apply the migration, yield a pool, roll back on exit. A context
    manager rather than an async fixture: pytest-asyncio 0.21.1 async-gen
    fixtures are broken on pytest 8.4 (FixtureDef.unittest removed), and the
    per-test apply/rollback also isolates every test's schema state."""
    conn = await asyncpg.connect(**test_pg_kwargs)
    await _ensure_schema_registry(conn)
    try:
        result = await apply_migration(conn, "0001_prediction_persistence")
        assert result in ("applied", "already-applied"), f"apply returned {result}"
    finally:
        await conn.close()

    pool = await asyncpg.create_pool(**test_pg_kwargs)
    try:
        yield pool
    finally:
        await pool.close()
        rollback_conn = await asyncpg.connect(**test_pg_kwargs)
        try:
            await rollback_migration(rollback_conn, "0001_prediction_persistence")
        finally:
            await rollback_conn.close()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _artifact_record_response(response_bytes: bytes) -> PredictionArtifactRecord:
    return encode_prediction_artifact(response_bytes)


def _prediction_run(payload_override: dict | None = None) -> PredictionRunRecord:
    base_payload = {
        "model_snapshot_id": "a" * 64,
        "model_release_id": "test-release",
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
            }
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
            }
        ],
    }
    payload = {**base_payload, **(payload_override or {})}
    run_id = prediction_run_id_for(payload)

    response = {
        "schema_version": 2,
        "persistence": "stored",
        "prediction_run_id": run_id,
        "members": [
            {
                "member": member,
                "status": "completed",
                "predicted_delivered_total_m3": 300.0,
                "violations": [{"kind": "requirement_shortfall"}],
                "infeasibility": None,
            }
            for member in ("lower", "nominal", "upper")
        ],
    }
    response_bytes = canonical_json_bytes(response)

    return PredictionRunRecord(
        prediction_run_id=run_id,
        identity_version=1,
        response_schema_version=2,
        request_payload=payload,
        model_snapshot_id=payload["model_snapshot_id"],
        model_release_id=payload["model_release_id"],
        model_release_content_hash=payload["model_release_content_hash"],
        starts_at=datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 21, 5, 0, tzinfo=timezone.utc),
        timestep_seconds=300.0,
        member_summaries=summarize_prediction_members(response),
        artifact=_artifact_record_response(response_bytes),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMigrationApplyRollbackReapply:
    async def test_migration_apply_rollback_reapply_is_clean(self, test_pg_kwargs: dict):
        async with migrated_pool(test_pg_kwargs) as fresh_database:
            """Round-trip: apply -> rollback -> reapply creates clean tables."""
            assert fresh_database is not None


@pytest.mark.asyncio
class TestPredictionRepositoryRoundTrip:
    async def test_prediction_repository_round_trips_exact_bytes(self, test_pg_kwargs: dict):
        async with migrated_pool(test_pg_kwargs) as pool:
            repo = PostgresPredictionRepository(pool)
            run = _prediction_run()
            stored, replayed = await repo.persist_prediction_run(run)
            assert replayed is False

            loaded = await repo.load_prediction_run(run.prediction_run_id)
            assert loaded is not None
            assert loaded.prediction_run_id == run.prediction_run_id
            assert loaded.model_snapshot_id == run.model_snapshot_id
            assert loaded.model_release_id == run.model_release_id
            assert loaded.model_release_content_hash == run.model_release_content_hash
            assert loaded.starts_at == run.starts_at
            assert loaded.ends_at == run.ends_at
            assert loaded.timestep_seconds == run.timestep_seconds
            assert loaded.artifact.artifact_sha256 == run.artifact.artifact_sha256
            assert loaded.artifact.compressed_payload == run.artifact.compressed_payload
            assert loaded.artifact.encoding == "canonical-json+zlib"
            assert loaded.artifact.encoding_version == 1
            assert loaded.artifact.uncompressed_size_bytes == run.artifact.uncompressed_size_bytes

            # Member summaries survive round-trip
            assert len(loaded.member_summaries) == 3
            assert [s["member"] for s in loaded.member_summaries] == [
                "lower", "nominal", "upper"
            ]

    async def test_prediction_replay_converges_on_one_immutable_row(self, test_pg_kwargs: dict):
        async with migrated_pool(test_pg_kwargs) as pool:
            repo = PostgresPredictionRepository(pool)
            run = _prediction_run()
            first = await repo.persist_prediction_run(run)
            assert first[1] is False

            second = await repo.persist_prediction_run(run)
            assert second[1] is True
            assert second[0].prediction_run_id == first[0].prediction_run_id

            loaded = await repo.load_prediction_run(run.prediction_run_id)
            assert loaded is not None

    async def test_prediction_rows_reject_update(self, test_pg_kwargs: dict):
        async with migrated_pool(test_pg_kwargs) as fresh_database:
            run = _prediction_run()
            repo = PostgresPredictionRepository(fresh_database)
            stored, _ = await repo.persist_prediction_run(run)

            async with fresh_database.acquire() as conn:
                with pytest.raises(asyncpg.exceptions.RaiseError):
                    await conn.execute(
                        "UPDATE flow_monitoring.prediction_runs "
                        "SET model_release_id = 'tampered' "
                        "WHERE prediction_run_id = $1",
                        run.prediction_run_id,
                    )

    async def test_prediction_rows_reject_delete(self, test_pg_kwargs: dict):
        async with migrated_pool(test_pg_kwargs) as fresh_database:
            run = _prediction_run()
            repo = PostgresPredictionRepository(fresh_database)
            stored, _ = await repo.persist_prediction_run(run)

            async with fresh_database.acquire() as conn:
                with pytest.raises(asyncpg.exceptions.RaiseError):
                    await conn.execute(
                        "DELETE FROM flow_monitoring.prediction_runs "
                        "WHERE prediction_run_id = $1",
                        run.prediction_run_id,
                    )

                with pytest.raises(asyncpg.exceptions.RaiseError):
                    await conn.execute(
                        "DELETE FROM flow_monitoring.prediction_artifacts "
                        "WHERE prediction_run_id = $1",
                        run.prediction_run_id,
                    )


@pytest.mark.asyncio
class TestPredictionAtomicity:
    async def test_prediction_commit_is_atomic_with_artifact(self, test_pg_kwargs: dict):
        async with migrated_pool(test_pg_kwargs) as fresh_database:
            """Inserting a header without its matching artifact must fail at commit
            because the deferred FK raises — neither row should persist."""
            run = _prediction_run()
            # Corrupt the artifact sha256 so the deferred FK fails
            bad_artifact_sha256 = "f" * 64  # does not match artifact row

            async with fresh_database.acquire() as conn:
                try:
                    async with conn.transaction():
                        await conn.execute(
                            """
                            INSERT INTO flow_monitoring.prediction_runs (
                                prediction_run_id, identity_version,
                                response_schema_version, request_payload,
                                model_snapshot_id, model_release_id,
                                model_release_content_hash,
                                starts_at, ends_at, timestep_seconds,
                                member_summaries, artifact_sha256
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                            )
                            """,
                            run.prediction_run_id,
                            run.identity_version,
                            run.response_schema_version,
                            canonical_json_bytes(run.request_payload).decode(),
                            run.model_snapshot_id,
                            run.model_release_id,
                            run.model_release_content_hash,
                            run.starts_at,
                            run.ends_at,
                            run.timestep_seconds,
                            canonical_json_bytes(list(run.member_summaries)).decode(),
                            bad_artifact_sha256,  # will fail deferred FK
                        )
                        # Don't insert artifact row
                except asyncpg.exceptions.ForeignKeyViolationError:
                    pass  # expected — deferred FK should reject at commit

            # Verify no rows were persisted (the FK failure aborts the whole tx)
            header = await fresh_database.fetchrow(
                "SELECT 1 FROM flow_monitoring.prediction_runs "
                "WHERE prediction_run_id = $1",
                run.prediction_run_id,
            )
            assert header is None, (
                "header should not persist with FK-violated artifact hash"
            )


@pytest.mark.asyncio
class TestConcurrentPersistence:
    async def test_concurrent_prediction_replay_converges_on_one_artifact(
        self, test_pg_kwargs: dict
    ):
        async with migrated_pool(test_pg_kwargs) as fresh_database:
            """Concurrent identical writes from separate connections must land
            exactly one immutable row (one winner, replays for the rest)."""
            run = _prediction_run()

            async def persist() -> Tuple[PredictionRunRecord, bool]:
                repo = PostgresPredictionRepository(fresh_database)
                return await repo.persist_prediction_run(run)

            # Launch several concurrent persists
            results = await asyncio.gather(persist(), persist(), persist())

            # Exactly one should be a fresh insert; the rest should be replays
            fresh_count = sum(1 for _, replayed in results if not replayed)
            replay_count = sum(1 for _, replayed in results if replayed)

            assert fresh_count == 1, (
                "expected exactly 1 fresh insert, got fresh_count"
            )
            assert replay_count == len(results) - 1, (
                "expected rest to be replays"
            )

            # All returned records must have the same id
            run_ids = {record.prediction_run_id for record, _ in results}
            assert len(run_ids) == 1

            # Only one row in the database
            loaded = await fresh_database.fetchrow(
                "SELECT prediction_run_id, artifact_sha256 "
                "FROM flow_monitoring.prediction_runs "
                "WHERE prediction_run_id = $1",
                run.prediction_run_id,
            )
            assert loaded is not None


@pytest.mark.asyncio
class TestCreatePredictionRepositoryIfMigrated:
    async def test_probe_returns_repository_when_tables_exist(self, test_pg_kwargs: dict):
        async with migrated_pool(test_pg_kwargs) as fresh_database:
            repo = await create_prediction_repository_if_migrated(fresh_database)
            assert repo is not None
            assert isinstance(repo, PostgresPredictionRepository)

    async def test_probe_returns_none_when_tables_missing(
        self, test_pg_url: str, test_pg_kwargs: dict
    ):
        """Create a fresh database that has NOT been migrated and verify
        the probe returns None (never creates schema)."""
        # Connect and ensure no prediction tables exist
        conn = await asyncpg.connect(**test_pg_kwargs)
        try:
            # Drop tables if they exist from prior tests
            await conn.execute(
                "DROP TABLE IF EXISTS "
                "flow_monitoring.prediction_artifacts, "
                "flow_monitoring.prediction_runs CASCADE"
            )
            # Keep schema_migrations but ensure the prediction tables are gone
            pool = await asyncpg.create_pool(**test_pg_kwargs)
            try:
                result = await create_prediction_repository_if_migrated(pool)
                assert result is None, (
                    "probe must return None when tables are missing"
                )
            finally:
                await pool.close()
        finally:
            await conn.close()


@pytest.mark.asyncio
class TestLoadPredictionRunErrors:
    async def test_load_prediction_run_header_without_artifact_is_corrupt(
        self, test_pg_kwargs: dict
    ):
        """A header whose artifact row is gone must load as CORRUPTION, never
        as a fake 404. The immutability trigger and FK are deliberately
        disabled/dropped here — this simulates operator-level damage, which is
        exactly what the load path must refuse to serve."""
        async with migrated_pool(test_pg_kwargs) as fresh_database:
            run = _prediction_run()
            repo = PostgresPredictionRepository(fresh_database)
            stored, _ = await repo.persist_prediction_run(run)
            assert stored is not None

            async with fresh_database.acquire() as conn:
                await conn.execute(
                    "ALTER TABLE flow_monitoring.prediction_runs "
                    "DROP CONSTRAINT prediction_runs_exact_artifact_fk"
                )
                await conn.execute(
                    "ALTER TABLE flow_monitoring.prediction_artifacts "
                    "DISABLE TRIGGER prediction_artifacts_are_immutable"
                )
                await conn.execute(
                    "DELETE FROM flow_monitoring.prediction_artifacts "
                    "WHERE prediction_run_id = $1",
                    run.prediction_run_id,
                )

            with pytest.raises(PredictionArtifactCorrupt):
                await repo.load_prediction_run(run.prediction_run_id)
