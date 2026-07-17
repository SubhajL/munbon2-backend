"""
Tracked schema migrations for flow_monitoring (PR 4.1: prediction persistence).

    python migrations/migrate.py apply    0001_prediction_persistence
    python migrations/migrate.py rollback 0001_prediction_persistence
    python migrations/migrate.py status

Each migration is a pair of tracked SQL files (<id>.up.sql / <id>.down.sql) applied
in ONE transaction and recorded in flow_monitoring.schema_migrations with a content
checksum over BOTH directions: re-applying an identical pair is a no-op, an edited
already-applied pair refuses apply and rollback (checksum drift), and any infra failure
aborts the whole transaction — never a half-applied schema. Connection comes from
POSTGRES_URL; there is no default host (the leaked-credential history makes silent
defaults a hazard).
"""
import asyncio
import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

MIGRATIONS_DIR = Path(__file__).resolve().parent
MIGRATIONS_LOCK_ID = int.from_bytes(
    hashlib.sha256(b"flow_monitoring.schema_migrations").digest()[:8],
    "big",
    signed=True,
)
MIGRATIONS_SCHEMA_DDL = "CREATE SCHEMA IF NOT EXISTS flow_monitoring"

MIGRATIONS_REGISTRY_DDL = (
    "CREATE TABLE IF NOT EXISTS flow_monitoring.schema_migrations ("
    "migration_id TEXT PRIMARY KEY, "
    "checksum TEXT NOT NULL, "
    "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
)


class MigrationError(RuntimeError):
    """The migration cannot proceed safely (unknown id, drift, wrong state)."""


def checksum_of(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


def _read_sql(migration_id: str, direction: str) -> str:
    path = MIGRATIONS_DIR / f"{migration_id}.{direction}.sql"
    if not path.is_file():
        raise MigrationError(
            f"unknown migration {migration_id!r} ({path.name} missing)"
        )
    return path.read_text(encoding="utf-8")


def migration_checksum(migration_id: str) -> str:
    up_sql = _read_sql(migration_id, "up")
    down_sql = _read_sql(migration_id, "down")
    return checksum_of(f"up\0{up_sql}\0down\0{down_sql}")


def postgres_connection_kwargs(url: str) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise MigrationError("POSTGRES_URL must use postgres:// or postgresql://")
    database = unquote(parsed.path.lstrip("/"))
    if not parsed.username or not parsed.hostname or not database:
        raise MigrationError("POSTGRES_URL must include user, host, and database")
    result = {
        "user": unquote(parsed.username),
        "password": unquote(parsed.password) if parsed.password is not None else None,
        "host": parsed.hostname,
        "database": database,
    }
    if parsed.port is not None:
        result["port"] = parsed.port
    return result


async def _registry_exists(conn) -> bool:
    return (
        await conn.fetchval(
            "SELECT to_regclass('flow_monitoring.schema_migrations')"
        )
        is not None
    )


async def apply_migration(conn, migration_id: str) -> str:
    up_sql = _read_sql(migration_id, "up")
    digest = migration_checksum(migration_id)
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock($1)", MIGRATIONS_LOCK_ID)
        await conn.execute(MIGRATIONS_SCHEMA_DDL)
        await conn.execute(MIGRATIONS_REGISTRY_DDL)
        row = await conn.fetchrow(
            "SELECT checksum "
            "FROM flow_monitoring.schema_migrations "
            "WHERE migration_id = $1",
            migration_id,
        )
        if row is not None:
            if row["checksum"] == digest:
                return "already-applied"
            raise MigrationError(
                f"checksum drift for {migration_id!r}: the applied migration does "
                "not match the tracked file — write a NEW migration, never edit an "
                "applied one"
            )
        await conn.execute(up_sql)
        await conn.execute(
            "INSERT INTO flow_monitoring.schema_migrations "
            "(migration_id, checksum) VALUES ($1, $2)",
            migration_id,
            digest,
        )
        return "applied"


async def rollback_migration(conn, migration_id: str) -> str:
    down_sql = _read_sql(migration_id, "down")
    digest = migration_checksum(migration_id)
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock($1)", MIGRATIONS_LOCK_ID)
        if not await _registry_exists(conn):
            raise MigrationError(
                f"{migration_id!r} is not applied — nothing to roll back"
            )
        row = await conn.fetchrow(
            "SELECT checksum "
            "FROM flow_monitoring.schema_migrations "
            "WHERE migration_id = $1",
            migration_id,
        )
        if row is None:
            raise MigrationError(
                f"{migration_id!r} is not applied — nothing to roll back"
            )
        if row["checksum"] != digest:
            raise MigrationError(
                f"checksum drift for {migration_id!r}: rollback SQL no longer "
                "matches the applied migration — restore the tracked pair before "
                "rolling back"
            )
        await conn.execute(down_sql)
        await conn.execute(
            "DELETE FROM flow_monitoring.schema_migrations WHERE migration_id = $1",
            migration_id,
        )
        return "rolled-back"


async def migration_status(conn) -> list[dict]:
    if not await _registry_exists(conn):
        return []
    rows = await conn.fetch(
        "SELECT migration_id, checksum, applied_at "
        "FROM flow_monitoring.schema_migrations "
        "ORDER BY applied_at"
    )
    return [dict(row) for row in rows]


async def _main(argv: list[str]) -> int:
    import asyncpg
    from dotenv import load_dotenv

    if len(argv) < 1 or argv[0] not in ("apply", "rollback", "status"):
        print(__doc__)
        return 2
    load_dotenv(MIGRATIONS_DIR.parent / ".env")
    url = os.environ.get("POSTGRES_URL")
    if not url:
        print(
            "POSTGRES_URL is not set — refusing to guess a database",
            file=sys.stderr,
        )
        return 2
    conn = await asyncpg.connect(**postgres_connection_kwargs(url))
    try:
        if argv[0] == "status":
            for entry in await migration_status(conn):
                print(
                    f"{entry['migration_id']}  {entry['applied_at']}  "
                    f"{entry['checksum'][:12]}"
                )
            return 0
        if len(argv) != 2:
            print(f"{argv[0]} needs exactly one migration id", file=sys.stderr)
            return 2
        action = apply_migration if argv[0] == "apply" else rollback_migration
        print(await action(conn, argv[1]))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
