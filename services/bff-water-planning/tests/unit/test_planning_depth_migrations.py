import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from db.migration_runner import (
    MigrationChecksumError,
    MigrationManifestError,
    apply_migrations,
    load_migration_manifest,
    migration_status,
)

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
REPO_ROOT = Path(__file__).resolve().parents[4]


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeConnection:
    def __init__(self, applied=None):
        self.applied = dict(applied or {})
        self.executed_migrations = []

    def transaction(self):
        return _Transaction()

    async def execute(self, sql, *args):
        if sql.startswith("INSERT INTO water_planning.schema_migrations"):
            self.applied[args[0]] = args[1]
        elif "CREATE TABLE IF NOT EXISTS water_planning.schema_migrations" not in sql:
            self.executed_migrations.append(sql)

    async def fetchrow(self, sql, migration_id):
        checksum = self.applied.get(migration_id)
        return None if checksum is None else {"checksum": checksum}

    async def fetch(self, sql):
        return [
            {"migration_id": migration_id, "checksum": checksum}
            for migration_id, checksum in sorted(self.applied.items())
        ]


def test_manifest_pins_every_owned_sql_file_and_git_tracks_them():
    manifest = json.loads((MIGRATIONS / "manifest.json").read_text(encoding="utf-8"))

    assert [item["migration_id"] for item in manifest["migrations"]] == [
        "009_crop_registry",
        "010_planning_depth_submissions",
    ]
    owned_migration_number_min = manifest["owned_migration_number_min"]
    assert {item["filename"] for item in manifest["migrations"]} == {
        path.name
        for path in MIGRATIONS.glob("*.sql")
        if int(path.name.split("_", 1)[0]) >= owned_migration_number_min
    }
    for item in manifest["migrations"]:
        path = MIGRATIONS / item["filename"]
        assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert tracked.returncode == 0, path


def test_manifest_ignores_legacy_sql_but_rejects_new_unlisted_migrations(
    tmp_path,
):
    migrations = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, migrations)
    (migrations / "001_legacy.sql").write_text("SELECT 1;\n", encoding="utf-8")

    assert [item.migration_id for item in load_migration_manifest(migrations)] == [
        "009_crop_registry",
        "010_planning_depth_submissions",
    ]

    (migrations / "011_unlisted.sql").write_text("SELECT 1;\n", encoding="utf-8")
    with pytest.raises(MigrationManifestError, match="incomplete or unordered"):
        load_migration_manifest(migrations)


@pytest.mark.asyncio
async def test_apply_is_ordered_idempotent_and_reports_checksums():
    connection = _FakeConnection()

    first = await apply_migrations(connection, MIGRATIONS)
    second = await apply_migrations(connection, MIGRATIONS)
    status = await migration_status(connection, MIGRATIONS)

    assert first == ["009_crop_registry", "010_planning_depth_submissions"]
    assert second == []
    assert len(connection.executed_migrations) == 2
    assert status == [
        {
            "migration_id": migration.migration_id,
            "sha256": migration.sha256,
            "applied": True,
        }
        for migration in load_migration_manifest(MIGRATIONS)
    ]


@pytest.mark.asyncio
async def test_applied_checksum_drift_fails_closed_before_sql_execution():
    migrations = load_migration_manifest(MIGRATIONS)
    connection = _FakeConnection(applied={migrations[0].migration_id: "0" * 64})

    with pytest.raises(MigrationChecksumError):
        await apply_migrations(connection, MIGRATIONS)

    assert connection.executed_migrations == []
