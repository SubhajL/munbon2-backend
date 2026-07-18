"""Checksum migration runner locks (PR 4.2) — tmp-dir pairs + FakeConn."""

import hashlib
from contextlib import asynccontextmanager

import pytest

import migrations.migrate as migrate
from migrations.migrate import (
    MigrationError,
    apply_migration,
    migration_checksum,
    migration_status,
    postgres_connection_kwargs,
    rollback_migration,
)


def _write_pair(tmp_path, migration_id, up_sql, down_sql):
    (tmp_path / f"{migration_id}.up.sql").write_text(up_sql, encoding="utf-8")
    (tmp_path / f"{migration_id}.down.sql").write_text(
        down_sql, encoding="utf-8"
    )


@pytest.fixture
def pair_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
    _write_pair(
        tmp_path, "0001_probe", "CREATE TABLE probe (id INT);", "DROP TABLE probe;"
    )
    return tmp_path


class _FakeConn:
    def __init__(self, applied_checksum=None, registry_exists=True,
                 fail_on=None):
        self.executed: list[str] = []
        self._applied_checksum = applied_checksum
        self._registry_exists = registry_exists
        self._fail_on = fail_on

    async def execute(self, sql, *args):
        self.executed.append(sql)
        if self._fail_on and self._fail_on in sql:
            raise OSError("simulated mid-DDL failure")
        return None

    async def fetchrow(self, sql, *args):
        if self._applied_checksum is None:
            return None
        return {"checksum": self._applied_checksum}

    async def fetchval(self, sql):
        return "scheduler.schema_migrations" if self._registry_exists else None

    async def fetch(self, sql):
        return []

    def transaction(self):
        @asynccontextmanager
        async def tx():
            yield

        return tx()


class TestChecksums:
    def test_migration_checksum_binds_both_directions(self, pair_dir):
        original = migration_checksum("0001_probe")
        _write_pair(
            pair_dir, "0001_probe", "CREATE TABLE probe (id INT);",
            "DROP TABLE probe CASCADE;"
        )
        assert migration_checksum("0001_probe") != original

    def test_lock_seed_and_registry_are_scheduler_scoped(self):
        expected = int.from_bytes(
            hashlib.sha256(b"scheduler.schema_migrations").digest()[:8],
            "big",
            signed=True,
        )
        assert migrate.MIGRATIONS_LOCK_ID == expected
        assert "scheduler.schema_migrations" in migrate.MIGRATIONS_REGISTRY_DDL


class TestApply:
    @pytest.mark.asyncio
    async def test_migration_checksum_drift_is_rejected(self, pair_dir):
        conn = _FakeConn(applied_checksum="d" * 64)
        with pytest.raises(MigrationError, match="drift"):
            await apply_migration(conn, "0001_probe")
        assert not any("CREATE TABLE probe" in sql for sql in conn.executed)

    @pytest.mark.asyncio
    async def test_apply_is_idempotent_when_checksum_matches(self, pair_dir):
        conn = _FakeConn(applied_checksum=migration_checksum("0001_probe"))
        assert await apply_migration(conn, "0001_probe") == "already-applied"
        assert not any("CREATE TABLE probe" in sql for sql in conn.executed)
        assert not any(
            "INSERT INTO" in sql and "schema_migrations" in sql
            for sql in conn.executed
        )

    @pytest.mark.asyncio
    async def test_apply_uses_advisory_lock_and_registers(self, pair_dir):
        conn = _FakeConn(applied_checksum=None)
        assert await apply_migration(conn, "0001_probe") == "applied"
        assert any("pg_advisory_xact_lock" in sql for sql in conn.executed)
        assert any("CREATE TABLE probe" in sql for sql in conn.executed)
        assert any(
            "INSERT INTO" in sql and "schema_migrations" in sql
            for sql in conn.executed
        )

    @pytest.mark.asyncio
    async def test_mid_apply_failure_never_registers(self, pair_dir):
        conn = _FakeConn(applied_checksum=None, fail_on="CREATE TABLE probe")
        with pytest.raises(OSError, match="simulated"):
            await apply_migration(conn, "0001_probe")
        assert not any(
            "INSERT INTO" in sql and "schema_migrations" in sql
            for sql in conn.executed
        )

    @pytest.mark.asyncio
    async def test_unknown_migration_is_refused(self, pair_dir):
        with pytest.raises(MigrationError, match="unknown migration"):
            await apply_migration(_FakeConn(), "0002_missing")


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_refuses_when_either_direction_drifted(
        self, pair_dir
    ):
        conn = _FakeConn(applied_checksum="d" * 64)
        with pytest.raises(MigrationError, match="drift"):
            await rollback_migration(conn, "0001_probe")
        assert not any("DROP TABLE probe" in sql for sql in conn.executed)

    @pytest.mark.asyncio
    async def test_rollback_refuses_unapplied_migration(self, pair_dir):
        conn = _FakeConn(applied_checksum=None)
        with pytest.raises(MigrationError, match="not applied"):
            await rollback_migration(conn, "0001_probe")


class TestStatus:
    @pytest.mark.asyncio
    async def test_status_does_not_create_registry(self, pair_dir):
        conn = _FakeConn(registry_exists=False)
        assert await migration_status(conn) == []
        assert conn.executed == []


class TestDiscoverMigrationIds:
    def test_lists_complete_pairs_in_lexical_order(self, tmp_path, monkeypatch):
        monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
        _write_pair(tmp_path, "0002_b", "CREATE TABLE b (id INT);", "DROP TABLE b;")
        _write_pair(tmp_path, "0001_a", "CREATE TABLE a (id INT);", "DROP TABLE a;")
        _write_pair(tmp_path, "0010_c", "CREATE TABLE c (id INT);", "DROP TABLE c;")
        assert migrate.discover_migration_ids() == ["0001_a", "0002_b", "0010_c"]

    def test_rejects_pair_missing_its_down(self, tmp_path, monkeypatch):
        monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
        (tmp_path / "0001_a.up.sql").write_text("CREATE TABLE a (id INT);", "utf-8")
        with pytest.raises(MigrationError, match="incomplete"):
            migrate.discover_migration_ids()

    def test_rejects_pair_missing_its_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
        (tmp_path / "0001_a.down.sql").write_text("DROP TABLE a;", "utf-8")
        with pytest.raises(MigrationError, match="incomplete"):
            migrate.discover_migration_ids()

    def test_real_scheduler_pairs_are_complete_and_sorted(self):
        # No monkeypatch: the shipped scheduler migrations must be complete pairs.
        ids = migrate.discover_migration_ids()
        assert ids == sorted(ids)
        assert "0001_control_plan_drafts" in ids
        assert "apply-all" in migrate.CLI_VERBS


class TestApplyAll:
    @pytest.mark.asyncio
    async def test_applies_every_pending_pair_in_sorted_order(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
        _write_pair(tmp_path, "0002_b", "CREATE TABLE b (id INT);", "DROP TABLE b;")
        _write_pair(tmp_path, "0001_a", "CREATE TABLE a (id INT);", "DROP TABLE a;")
        conn = _FakeConn(applied_checksum=None)

        results = await migrate.apply_all_migrations(conn)

        assert [mid for mid, _ in results] == ["0001_a", "0002_b"]
        assert all(outcome == "applied" for _, outcome in results)
        a_idx = next(i for i, s in enumerate(conn.executed) if "CREATE TABLE a" in s)
        b_idx = next(i for i, s in enumerate(conn.executed) if "CREATE TABLE b" in s)
        assert a_idx < b_idx

    @pytest.mark.asyncio
    async def test_is_idempotent_when_pair_already_applied(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
        _write_pair(tmp_path, "0001_a", "CREATE TABLE a (id INT);", "DROP TABLE a;")
        conn = _FakeConn(applied_checksum=migration_checksum("0001_a"))

        results = await migrate.apply_all_migrations(conn)

        assert results == [("0001_a", "already-applied")]
        assert not any("CREATE TABLE a" in s for s in conn.executed)

    @pytest.mark.asyncio
    async def test_aborts_on_checksum_drift_without_applying_later_pairs(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
        _write_pair(tmp_path, "0001_a", "CREATE TABLE a (id INT);", "DROP TABLE a;")
        _write_pair(tmp_path, "0002_b", "CREATE TABLE b (id INT);", "DROP TABLE b;")
        # A drifted registry (checksum never matches) makes the first pair refuse;
        # apply-all must surface it and never reach the second pair.
        conn = _FakeConn(applied_checksum="d" * 64)

        with pytest.raises(MigrationError, match="drift"):
            await migrate.apply_all_migrations(conn)

        assert not any("CREATE TABLE b" in s for s in conn.executed)


class TestUrlParser:
    def test_parser_preserves_reserved_password_characters(self):
        kwargs = postgres_connection_kwargs(
            "postgresql://user:p%40ss%23word!%26@host:5432/db"
        )
        assert kwargs == {
            "user": "user",
            "password": "p@ss#word!&",
            "host": "host",
            "database": "db",
            "port": 5432,
        }

    def test_parser_rejects_incomplete_urls(self):
        for bad in (
            "postgresql://:pass@host/db",
            "postgresql://user:pass@/db",
            "postgresql://user:pass@host",
            "mysql://user:pass@host/db",
        ):
            with pytest.raises(MigrationError):
                postgres_connection_kwargs(bad)
