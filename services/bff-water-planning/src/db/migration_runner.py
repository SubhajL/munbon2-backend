from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class MigrationManifestError(RuntimeError):
    pass


class MigrationChecksumError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    migration_id: str
    filename: str
    sha256: str
    sql: str


def load_migration_manifest(migrations_dir: Path) -> tuple[Migration, ...]:
    try:
        document = json.loads(
            (migrations_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationManifestError("migration manifest is unavailable") from exc
    if set(document) != {"manifest_version", "migrations"}:
        raise MigrationManifestError("migration manifest has invalid keys")
    if document["manifest_version"] != 1 or not isinstance(
        document["migrations"], list
    ):
        raise MigrationManifestError("migration manifest version is unsupported")

    migrations = []
    for item in document["migrations"]:
        if set(item) != {"migration_id", "filename", "sha256"}:
            raise MigrationManifestError("migration entry has invalid keys")
        filename = item["filename"]
        if (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or not filename.endswith(".sql")
        ):
            raise MigrationManifestError("migration filename is unsafe")
        path = migrations_dir / filename
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise MigrationManifestError("migration SQL is unavailable") from exc
        sha256 = hashlib.sha256(raw).hexdigest()
        if sha256 != item["sha256"]:
            raise MigrationChecksumError(
                f"migration file checksum drift: {item['migration_id']}"
            )
        migrations.append(
            Migration(
                migration_id=item["migration_id"],
                filename=filename,
                sha256=sha256,
                sql=raw.decode("utf-8"),
            )
        )

    ids = [item.migration_id for item in migrations]
    filenames = [item.filename for item in migrations]
    if (
        len(ids) != len(set(ids))
        or len(filenames) != len(set(filenames))
        or filenames != sorted(filenames)
        or set(filenames) != {path.name for path in migrations_dir.glob("*.sql")}
    ):
        raise MigrationManifestError("migration manifest is incomplete or unordered")
    return tuple(migrations)


async def _ensure_registry(connection) -> None:
    async with connection.transaction():
        await connection.execute(
            """
            CREATE SCHEMA IF NOT EXISTS water_planning;
            CREATE TABLE IF NOT EXISTS water_planning.schema_migrations (
                migration_id TEXT PRIMARY KEY,
                checksum CHAR(64) NOT NULL
                    CHECK (checksum ~ '^[0-9a-f]{64}$'),
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )


async def _validate_registry(
    connection,
    migrations: tuple[Migration, ...],
) -> None:
    rows = await connection.fetch(
        "SELECT migration_id, checksum "
        "FROM water_planning.schema_migrations ORDER BY migration_id"
    )
    expected = {migration.migration_id: migration.sha256 for migration in migrations}
    if set(row["migration_id"] for row in rows) - set(expected):
        raise MigrationManifestError("migration registry contains unknown entries")
    for row in rows:
        if row["checksum"] != expected[row["migration_id"]]:
            raise MigrationChecksumError(
                f"applied migration checksum drift: {row['migration_id']}"
            )


async def apply_migrations(connection, migrations_dir: Path) -> list[str]:
    migrations = load_migration_manifest(migrations_dir)
    await _ensure_registry(connection)
    await _validate_registry(connection, migrations)
    applied = []
    for migration in migrations:
        async with connection.transaction():
            row = await connection.fetchrow(
                """
                SELECT checksum
                FROM water_planning.schema_migrations
                WHERE migration_id = $1
                FOR UPDATE
                """,
                migration.migration_id,
            )
            if row is not None:
                if row["checksum"] != migration.sha256:
                    raise MigrationChecksumError(
                        f"applied migration checksum drift: {migration.migration_id}"
                    )
                continue
            await connection.execute(migration.sql)
            await connection.execute(
                "INSERT INTO water_planning.schema_migrations "
                "(migration_id, checksum) VALUES ($1, $2)",
                migration.migration_id,
                migration.sha256,
            )
            applied.append(migration.migration_id)
    return applied


async def migration_status(connection, migrations_dir: Path) -> list[dict]:
    migrations = load_migration_manifest(migrations_dir)
    await _ensure_registry(connection)
    await _validate_registry(connection, migrations)
    rows = await connection.fetch(
        "SELECT migration_id, checksum "
        "FROM water_planning.schema_migrations ORDER BY migration_id"
    )
    applied = {row["migration_id"]: row["checksum"] for row in rows}
    return [
        {
            "migration_id": migration.migration_id,
            "sha256": migration.sha256,
            "applied": migration.migration_id in applied,
        }
        for migration in migrations
    ]
