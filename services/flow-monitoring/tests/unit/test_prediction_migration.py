"""Migration unit tests — Codex plan §4 "Migration" slice.

Tests the migration runner against temp-dir SQL pairs, verifying checksum
binding, drift rejection, URL-parser edge cases, read-only status behaviour,
and the existence/non-emptiness of the tracked 0001 pair.
"""
from pathlib import Path

import pytest

import migrations.migrate as migrate
from migrations.migrate import (
    MigrationError,
    apply_all_migrations,
    discover_migration_ids,
    migration_checksum,
    postgres_connection_kwargs,
    rollback_migration,
    apply_migration,
    migration_status,
)

# ---------------------------------------------------------------------------
# Helpers for building disposable temp-dir migration pairs
# ---------------------------------------------------------------------------

_REAL_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _write_temp_migration(tmp_path: Path, migration_id: str, up: str, down: str):
    (tmp_path / f"{migration_id}.up.sql").write_text(up)
    (tmp_path / f"{migration_id}.down.sql").write_text(down)


def _checksum_temp(migration_id: str, tmp_path: Path) -> str:
    return migration_checksum(migration_id)


@pytest.fixture
def temp_migrations_dir(tmp_path, monkeypatch):
    """Redirect MIGRATIONS_DIR to a temp dir and seed a valid pair."""
    monkeypatch.setattr(
        "migrations.migrate.MIGRATIONS_DIR", tmp_path
    )
    _write_temp_migration(
        tmp_path,
        "0001_test",
        "CREATE TABLE test_data (id INT PRIMARY KEY);",
        "DROP TABLE IF EXISTS test_data;",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMigrationChecksumBinding:
    """The migration checksum binds BOTH SQL directions — editing either one
    changes the checksum, so drift detection covers up and down equally."""

    def test_migration_checksum_binds_both_tmp_sql_directions(
        self, temp_migrations_dir
    ):
        digest_a = _checksum_temp("0001_test", temp_migrations_dir)
        assert len(digest_a) == 64, "checksum must be a 256-bit hex string"

        # Edit only up.sql — checksum must change
        up_path = temp_migrations_dir / "0001_test.up.sql"
        up_path.write_text("CREATE TABLE drift (x INT PRIMARY KEY);")
        digest_b = _checksum_temp("0001_test", temp_migrations_dir)
        assert digest_b != digest_a, "editing up.sql must change checksum"

        # Edit only down.sql — checksum must change
        down_path = temp_migrations_dir / "0001_test.down.sql"
        down_path.write_text("DROP TABLE drift;")
        digest_c = _checksum_temp("0001_test", temp_migrations_dir)
        assert digest_c != digest_b, "editing down.sql must change checksum"
        assert digest_c != digest_a

    def test_migration_files_exist_and_are_non_empty(self):
        up_path = _REAL_MIGRATIONS_DIR / "0001_prediction_persistence.up.sql"
        down_path = _REAL_MIGRATIONS_DIR / "0001_prediction_persistence.down.sql"

        assert up_path.is_file(), (
            f"{up_path} must exist"
        )
        assert down_path.is_file(), (
            f"{down_path} must exist"
        )

        up_content = up_path.read_text().strip()
        down_content = down_path.read_text().strip()
        assert up_content, "up.sql must not be empty"
        assert down_content, "down.sql must not be empty"

    def test_migration_checksum_stable_for_tracked_pair(self):
        digest_a = migration_checksum("0001_prediction_persistence")
        digest_b = migration_checksum("0001_prediction_persistence")
        assert digest_a == digest_b, (
            "checksum of tracked pair must be stable across repeated reads"
        )
        assert len(digest_a) == 64


class TestMigrationApplyAndRollbackDrift:
    """apply refuses checksum drift (already-applied but edited); rollback
    refuses drift in EITHER direction."""

    @pytest.fixture
    def applied_migrations_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("migrations.migrate.MIGRATIONS_DIR", tmp_path)
        _write_temp_migration(
            tmp_path,
            "0001_apply_test",
            "CREATE TABLE a (id INT);",
            "DROP TABLE a;",
        )
        return tmp_path

    @pytest.mark.asyncio
    async def test_apply_replays_only_matching_pair(
        self, applied_migrations_dir, monkeypatch
    ):
        """Identical pair is idempotent — re-applying returns 'already-applied'."""
        executed: list[str] = []

        class FakeConn:
            async def execute(self, sql, *args):
                executed.append(sql)
                return None

            async def fetchrow(self, sql, *args):
                checksum = _checksum_temp("0001_apply_test", applied_migrations_dir)
                return {"checksum": checksum}

            async def fetchval(self, sql):
                return "flow_monitoring.schema_migrations"

            def transaction(self):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def tx():
                    yield

                return tx()

        # Should be a no-op (already-applied with same checksum)
        result = await apply_migration(
            FakeConn(), "0001_apply_test"
        )
        assert result == "already-applied"
        # The runner may take the lock and ensure the schema/registry exist,
        # but the MIGRATION's own DDL and a re-registration must never run.
        assert not any("CREATE TABLE a" in sql for sql in executed), (
            "re-apply must not re-execute the migration DDL"
        )
        assert not any(
            "INSERT INTO" in sql and "schema_migrations" in sql
            for sql in executed
        ), "re-apply must not re-register"

    @pytest.mark.asyncio
    async def test_apply_refuses_checksum_drift(
        self, applied_migrations_dir, monkeypatch
    ):
        """Drifted up/down pair must refuse apply, not silently re-execute."""

        class FakeConn:
            async def execute(self, sql, *args):
                return None

            async def fetchrow(self, sql, *args):
                # Return a DIFFERENT checksum — simulates drift
                return {"checksum": "d" * 64}

            async def fetchval(self, sql):
                return "flow_monitoring.schema_migrations"

            def transaction(self):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def tx():
                    yield

                return tx()

        with pytest.raises(MigrationError, match="checksum drift"):
            await apply_migration(FakeConn(), "0001_apply_test")

    @pytest.mark.asyncio
    async def test_rollback_refuses_either_direction_drift(
        self, applied_migrations_dir, monkeypatch
    ):
        """Rollback with a drifted up.sql or down.sql must raise, not execute."""

        class FakeConn:
            async def execute(self, sql, *args):
                return None

            async def fetchrow(self, sql, *args):
                return {"checksum": "d" * 64}  # drift

            async def fetchval(self, sql):
                return "flow_monitoring.schema_migrations"

            def transaction(self):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def tx():
                    yield

                return tx()

        with pytest.raises(MigrationError, match="checksum drift"):
            await rollback_migration(FakeConn(), "0001_apply_test")


class TestMigrationStatus:
    """status never creates registry tables or executes DDL — it is strictly
    read-only."""

    @pytest.mark.asyncio
    async def test_status_does_not_create_registry(self, monkeypatch):
        registry_calls = []

        class FakeConn:
            async def execute(self, sql, *args):
                registry_calls.append(sql)
                return None

            async def fetchrow(self, *args, **kwargs):
                return None

            async def fetchval(self, sql):
                # Simulate no tables exist yet
                return None

            async def fetch(self, sql, *args):
                return []

        result = await migration_status(FakeConn())
        assert result == [], "no migrations applied yet"
        # Verify no DDL was executed
        for call in registry_calls:
            assert "CREATE" not in call, (
                f"status executed DDL: {call[:80]}"
            )
            assert "INSERT" not in call, (
                f"status inserted data: {call[:80]}"
            )

    @pytest.mark.asyncio
    async def test_status_returns_applied_migrations(self, monkeypatch):
        class FakeConn:
            async def execute(self, sql, *args):
                return None

            async def fetchval(self, sql):
                return "flow_monitoring.schema_migrations"

            async def fetch(self, sql, *args):
                return [
                    {
                        "migration_id": "0001_test",
                        "checksum": "e" * 64,
                        "applied_at": "2026-07-17 00:00:00+00",
                    }
                ]

        result = await migration_status(FakeConn())
        assert len(result) == 1
        assert result[0]["migration_id"] == "0001_test"
        assert result[0]["checksum"] == "e" * 64


class TestMigrationApplyTransaction:

    @pytest.fixture
    def applied_migrations_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("migrations.migrate.MIGRATIONS_DIR", tmp_path)
        _write_temp_migration(
            tmp_path,
            "0001_apply_test",
            "CREATE TABLE a (id INT);",
            "DROP TABLE a;",
        )
        return tmp_path

    """apply wraps DDL and registry insert in one transaction with an
    advisory lock; a mid-apply failure leaves no registry entry."""

    @pytest.mark.asyncio
    async def test_apply_uses_advisory_lock_and_one_transaction(
        self, applied_migrations_dir, monkeypatch
    ):
        ddl_calls = []

        class FakeConn:
            async def execute(self, sql, *args):
                ddl_calls.append(sql)
                return None

            async def fetchrow(self, sql, *args):
                return None  # not applied yet

            async def fetchval(self, sql):
                return "flow_monitoring.schema_migrations"

            def transaction(self):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def tx():
                    yield

                return tx()

        await apply_migration(FakeConn(), "0001_apply_test")
        lock_sqls = [
            s for s in ddl_calls if "pg_advisory_xact_lock" in s
        ]
        assert len(lock_sqls) >= 1, "apply must acquire advisory lock"

        registry_sqls = [
            s for s in ddl_calls if "schema_migrations" in s and "INSERT" in s
        ]
        assert len(registry_sqls) >= 1, (
            "apply must insert into the registry"
        )

    @pytest.mark.asyncio
    async def test_mid_apply_failure_never_registers_migration(
        self, applied_migrations_dir, monkeypatch
    ):
        executed: list[str] = []

        class FailingConn:
            async def execute(self, sql, *args):
                executed.append(sql)
                # The transaction OPENS successfully; the failure happens on
                # the migration's own DDL — the realistic mid-apply path.
                if "CREATE TABLE a" in sql:
                    raise OSError("simulated connection failure mid-DDL")
                return None

            async def fetchrow(self, sql, *args):
                return None

            async def fetchval(self, sql):
                return "flow_monitoring.schema_migrations"

            def transaction(self):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def tx():
                    yield

                return tx()

        with pytest.raises(OSError, match="simulated"):
            await apply_migration(FailingConn(), "0001_apply_test")
        assert not any(
            "INSERT INTO" in sql and "schema_migrations" in sql
            for sql in executed
        ), "a failed apply must never reach the registry INSERT"


class TestDiscoverAndApplyAll:
    """`apply-all` discovers complete pairs in lexical order and applies every
    pending one under the same checksum/lock rules (start.sh migrate-before-start)."""

    def test_discovers_complete_pairs_in_lexical_order(self, tmp_path, monkeypatch):
        monkeypatch.setattr("migrations.migrate.MIGRATIONS_DIR", tmp_path)
        _write_temp_migration(tmp_path, "0002_b", "CREATE TABLE b (i INT);", "DROP TABLE b;")
        _write_temp_migration(tmp_path, "0001_a", "CREATE TABLE a (i INT);", "DROP TABLE a;")
        assert discover_migration_ids() == ["0001_a", "0002_b"]

    def test_rejects_incomplete_pair(self, tmp_path, monkeypatch):
        monkeypatch.setattr("migrations.migrate.MIGRATIONS_DIR", tmp_path)
        (tmp_path / "0001_a.up.sql").write_text("CREATE TABLE a (i INT);")
        with pytest.raises(MigrationError, match="incomplete"):
            discover_migration_ids()

    def test_real_flow_pairs_are_complete_and_sorted(self):
        ids = discover_migration_ids()
        assert ids == sorted(ids)
        assert "0001_prediction_persistence" in ids
        assert "apply-all" in migrate.CLI_VERBS

    @pytest.mark.asyncio
    async def test_apply_all_applies_pending_pairs_in_sorted_order(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr("migrations.migrate.MIGRATIONS_DIR", tmp_path)
        _write_temp_migration(tmp_path, "0002_b", "CREATE TABLE b (i INT);", "DROP TABLE b;")
        _write_temp_migration(tmp_path, "0001_a", "CREATE TABLE a (i INT);", "DROP TABLE a;")
        executed: list[str] = []

        class FakeConn:
            async def execute(self, sql, *args):
                executed.append(sql)
                return None

            async def fetchrow(self, sql, *args):
                return None  # nothing applied yet

            async def fetchval(self, sql):
                return "flow_monitoring.schema_migrations"

            def transaction(self):
                from contextlib import asynccontextmanager

                @asynccontextmanager
                async def tx():
                    yield

                return tx()

        results = await apply_all_migrations(FakeConn())
        assert [mid for mid, _ in results] == ["0001_a", "0002_b"]
        a_idx = next(i for i, s in enumerate(executed) if "CREATE TABLE a" in s)
        b_idx = next(i for i, s in enumerate(executed) if "CREATE TABLE b" in s)
        assert a_idx < b_idx


class TestPostgresUrlParser:
    """Connection URL parsing must match the ratified ros-gis runner:
    preserve reserved password characters, reject missing fields, handle
    ports correctly."""

    def test_postgres_url_parser_preserves_reserved_password_characters(self):
        url = "postgresql://user:p%40ss%23word!%26@host:5432/db"
        kwargs = postgres_connection_kwargs(url)
        assert kwargs["user"] == "user"
        assert kwargs["password"] == "p@ss#word!&"
        assert kwargs["host"] == "host"
        assert kwargs["port"] == 5432
        assert kwargs["database"] == "db"

    def test_postgres_url_parser_rejects_missing_user_host_database(self):
        for bad_url in (
            "postgresql://:pass@host/db",     # no user
            "postgresql://user:pass@/db",      # no host
            "postgresql://user:pass@host",     # no database
            "postgresql://user:pass@host/",    # empty database
        ):
            with pytest.raises(MigrationError):
                postgres_connection_kwargs(bad_url)

    def test_postgres_url_parser_rejects_non_postgres_scheme(self):
        with pytest.raises(MigrationError):
            postgres_connection_kwargs("http://user:pass@host/db")

    def test_postgres_url_parser_defaults_no_port(self):
        kwargs = postgres_connection_kwargs(
            "postgresql://user:pass@host/db"
        )
        assert "port" not in kwargs, "no port in URL means no port kwarg"

    def test_postgres_url_parser_null_password(self):
        kwargs = postgres_connection_kwargs(
            "postgres://user@host/db"
        )
        assert kwargs["password"] is None
