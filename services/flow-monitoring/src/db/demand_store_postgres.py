"""
db.demand_store_postgres — asyncpg twin of core.demand_store.InMemoryDemandStore.

Three separate append-only record tables (one per concept, HIGH #8) plus ONE
kind-namespaced idempotency-key registry: replays must be able to BIND a freshly
regenerated key to an existing record version, which a UNIQUE column on the record
row cannot express. Immutability is enforced in code (classification before INSERT)
and by constraints; there is deliberately NO update statement in this module and no
updated_at trigger. Infra failures raise DemandStoreUnavailable (fail closed, 2.6b
rule): a broken store must never read as "no demand". A concurrent writer losing the
unique-constraint race is re-classified by one retry (honest replay/conflict instead
of a misleading 503); only a persistent race fails closed.
"""
import json

import asyncpg
import structlog

from core.demand_contract import canonical_json
from core.demand_store import (
    KINDS,
    DemandStoreError,
    DemandStoreUnavailable,
    DuplicateIdempotencyKey,
    ImmutabilityViolation,
    PutResult,
    VersionConflict,
    require_known_kind,
    semantic_content_hash,
    validate_put_args,
)

logger = structlog.get_logger()

__all__ = [
    "DDL_STATEMENTS",
    "IDEMPOTENCY_TABLE",
    "DemandStoreUnavailable",
    "PostgresDemandStore",
    "TABLES",
]

TABLES = {
    "demand": "ros_gis.demand_records",
    "allocation": "ros_gis.allocation_records",
    "delivery": "ros_gis.delivery_observations",
}
assert set(TABLES) == set(KINDS)

IDEMPOTENCY_TABLE = "ros_gis.contract_idempotency_keys"

_RECORD_COLUMNS = (
    "id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
    "logical_key TEXT NOT NULL, "
    "version INTEGER NOT NULL CHECK (version >= 1), "
    "idempotency_key TEXT NOT NULL, "  # the key that CREATED the row (audit)
    "content_hash TEXT NOT NULL, "
    "record JSONB NOT NULL, "
    "stored_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
    "UNIQUE (logical_key, version)"
)

DDL_STATEMENTS = (
    ("CREATE SCHEMA IF NOT EXISTS ros_gis",)
    + tuple(
        f"CREATE TABLE IF NOT EXISTS {table} ({_RECORD_COLUMNS})"
        for table in TABLES.values()
    )
    + (
        f"CREATE TABLE IF NOT EXISTS {IDEMPOTENCY_TABLE} ("
        "kind TEXT NOT NULL, "
        "idempotency_key TEXT NOT NULL, "
        "logical_key TEXT NOT NULL, "
        "version INTEGER NOT NULL, "
        "content_hash TEXT NOT NULL, "
        "stored_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "PRIMARY KEY (kind, idempotency_key))",
    )
)

SELECT_IDEMPOTENCY = (
    f"SELECT logical_key, version, content_hash FROM {IDEMPOTENCY_TABLE} "
    "WHERE kind = $1 AND idempotency_key = $2"
)
# One round-trip answers both classification reads: the latest version for the
# logical key AND the stored hash at the submitted version (NULL when absent).
SELECT_KEY_STATE = (
    "SELECT COALESCE(MAX(version), 0) AS latest_version, "
    "MAX(content_hash) FILTER (WHERE version = $2) AS existing_hash "
    "FROM {table} WHERE logical_key = $1"
)
INSERT_RECORD = (
    "INSERT INTO {table} (logical_key, version, idempotency_key, content_hash, record) "
    "VALUES ($1, $2, $3, $4, $5::jsonb)"
)
INSERT_IDEMPOTENCY = (
    f"INSERT INTO {IDEMPOTENCY_TABLE} "
    "(kind, idempotency_key, logical_key, version, content_hash) "
    "VALUES ($1, $2, $3, $4, $5)"
)
SELECT_LATEST = (
    "SELECT logical_key, version, content_hash, record FROM {table} "
    "WHERE logical_key = $1 ORDER BY version DESC LIMIT 1"
)
SELECT_CURRENT = (
    "SELECT DISTINCT ON (logical_key) logical_key, version, content_hash, record "
    "FROM {table} ORDER BY logical_key, version DESC"
)
SELECT_HISTORY = (
    "SELECT logical_key, version, content_hash, record FROM {table} "
    "WHERE logical_key = $1 ORDER BY version ASC"
)


def _envelope(row) -> dict:
    record = row["record"]
    return {
        "logical_key": row["logical_key"],
        "version": row["version"],
        "content_hash": row["content_hash"],
        "record": json.loads(record) if isinstance(record, str) else record,
    }


class PostgresDemandStore:
    def __init__(self, pool):
        self._pool = pool

    async def ensure_schema(self) -> None:
        """Create the ros_gis schema + append-only tables (idempotent, startup path)."""
        try:
            async with self._pool.acquire() as conn:
                for statement in DDL_STATEMENTS:
                    await conn.execute(statement)
        except Exception as exc:
            raise DemandStoreUnavailable(f"demand store DDL failed: {exc}") from exc

    async def put(
        self,
        kind: str,
        logical_key: str,
        version: int,
        idempotency_key: str,
        record: dict,
    ) -> PutResult:
        validate_put_args(kind, version, idempotency_key)
        digest = semantic_content_hash(record)
        payload = canonical_json(record)
        race = None
        for attempt in range(2):
            try:
                return await self._put_attempt(
                    kind, logical_key, version, idempotency_key, digest, payload
                )
            except asyncpg.exceptions.UniqueViolationError as exc:
                # A concurrent writer won the unique race; re-read and classify
                # honestly (replay / conflict) instead of reporting 503.
                race = exc
                continue
        raise DemandStoreUnavailable(
            f"demand store unavailable: persistent unique-constraint race: {race}"
        )

    async def _put_attempt(
        self,
        kind: str,
        logical_key: str,
        version: int,
        idempotency_key: str,
        digest: str,
        payload: str,
    ) -> PutResult:
        table = TABLES[kind]
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    idem = await conn.fetchrow(
                        SELECT_IDEMPOTENCY, kind, idempotency_key
                    )
                    if idem is not None:
                        if (
                            idem["logical_key"],
                            idem["version"],
                            idem["content_hash"],
                        ) == (logical_key, version, digest):
                            return PutResult(True, version, digest)
                        raise DuplicateIdempotencyKey(
                            f"idempotency key {idempotency_key!r} was already used "
                            "for different content"
                        )
                    state = await conn.fetchrow(
                        SELECT_KEY_STATE.format(table=table), logical_key, version
                    )
                    existing_hash = state["existing_hash"]
                    if existing_hash is not None:
                        if existing_hash == digest:
                            # Replay by content: bind the fresh key to the record.
                            await conn.execute(
                                INSERT_IDEMPOTENCY,
                                kind,
                                idempotency_key,
                                logical_key,
                                version,
                                digest,
                            )
                            return PutResult(True, version, digest)
                        raise ImmutabilityViolation(
                            f"{kind} {logical_key!r} version {version} exists with "
                            "different content — corrections must be the next version"
                        )
                    latest_version = state["latest_version"]
                    if version != latest_version + 1:
                        raise VersionConflict(
                            f"{kind} {logical_key!r}: expected version "
                            f"{latest_version + 1}, got {version}"
                        )
                    await conn.execute(
                        INSERT_RECORD.format(table=table),
                        logical_key,
                        version,
                        idempotency_key,
                        digest,
                        payload,
                    )
                    await conn.execute(
                        INSERT_IDEMPOTENCY,
                        kind,
                        idempotency_key,
                        logical_key,
                        version,
                        digest,
                    )
                    return PutResult(False, version, digest)
        except (DemandStoreError, asyncpg.exceptions.UniqueViolationError):
            raise
        except Exception as exc:
            logger.error("demand store put failed", kind=kind, error=str(exc))
            raise DemandStoreUnavailable(f"demand store unavailable: {exc}") from exc

    async def latest(self, kind: str, logical_key: str) -> dict | None:
        require_known_kind(kind)
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    SELECT_LATEST.format(table=TABLES[kind]), logical_key
                )
        except Exception as exc:
            logger.error("demand store read failed", kind=kind, error=str(exc))
            raise DemandStoreUnavailable(f"demand store unavailable: {exc}") from exc
        return _envelope(row) if row is not None else None

    async def current(self, kind: str) -> list[dict]:
        require_known_kind(kind)
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(SELECT_CURRENT.format(table=TABLES[kind]))
        except Exception as exc:
            logger.error("demand store read failed", kind=kind, error=str(exc))
            raise DemandStoreUnavailable(f"demand store unavailable: {exc}") from exc
        return [_envelope(row) for row in rows]

    async def history(self, kind: str, logical_key: str) -> list[dict]:
        require_known_kind(kind)
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    SELECT_HISTORY.format(table=TABLES[kind]), logical_key
                )
        except Exception as exc:
            logger.error("demand store read failed", kind=kind, error=str(exc))
            raise DemandStoreUnavailable(f"demand store unavailable: {exc}") from exc
        return [_envelope(row) for row in rows]
