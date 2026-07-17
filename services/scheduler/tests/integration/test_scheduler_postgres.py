"""Disposable-Postgres integration tests for the PR 4.2 foundation.

ALL tests skip unless SCHEDULER_TEST_POSTGRES_URL is set; a non-loopback host
RAISES (never assert — the guard must survive `python -O`). This suite
applies/rolls back migration-owned objects and creates/drops the legacy
create_all tables — never point it at a shared database."""

import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import asyncpg
import pytest

import migrations.migrate as migrate
from migrations.migrate import (
    apply_migration,
    migration_checksum,
    migration_status,
    postgres_connection_kwargs,
    rollback_migration,
)

_TEST_URL_ENV = "SCHEDULER_TEST_POSTGRES_URL"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _test_url_loopback() -> str | None:
    url = os.environ.get(_TEST_URL_ENV)
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.hostname not in _LOOPBACK_HOSTS:
        raise RuntimeError(
            f"{_TEST_URL_ENV} host is {parsed.hostname!r} — NOT a loopback "
            "address. This suite creates and drops schema objects. Point it "
            "at a disposable loopback Postgres or unset it to skip."
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


@asynccontextmanager
async def probe_pair(tmp_path, monkeypatch):
    """Seed a throwaway migration pair into a tmp MIGRATIONS_DIR — 4.2 ships
    the runner and registry only; no tracked control migration exists yet."""
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
    (tmp_path / "0001_probe.up.sql").write_text(
        "CREATE TABLE scheduler.migration_probe (id INT PRIMARY KEY);",
        encoding="utf-8",
    )
    (tmp_path / "0001_probe.down.sql").write_text(
        "DROP TABLE scheduler.migration_probe;", encoding="utf-8"
    )
    yield "0001_probe"


@pytest.mark.asyncio
class TestMigrationRunnerOnPostgres:
    async def test_migration_apply_rollback_reapply_is_clean(
        self, test_pg_kwargs, tmp_path, monkeypatch
    ):
        async with probe_pair(tmp_path, monkeypatch) as migration_id:
            conn = await asyncpg.connect(**test_pg_kwargs)
            try:
                assert await apply_migration(conn, migration_id) == "applied"
                assert await conn.fetchval(
                    "SELECT to_regclass('scheduler.migration_probe')"
                ) is not None
                assert (
                    await apply_migration(conn, migration_id)
                    == "already-applied"
                )
                assert (
                    await rollback_migration(conn, migration_id)
                    == "rolled-back"
                )
                assert await conn.fetchval(
                    "SELECT to_regclass('scheduler.migration_probe')"
                ) is None
                assert await apply_migration(conn, migration_id) == "applied"
                await rollback_migration(conn, migration_id)
            finally:
                await conn.close()

    async def test_registry_records_pair_checksum(
        self, test_pg_kwargs, tmp_path, monkeypatch
    ):
        async with probe_pair(tmp_path, monkeypatch) as migration_id:
            conn = await asyncpg.connect(**test_pg_kwargs)
            try:
                await apply_migration(conn, migration_id)
                entries = {
                    entry["migration_id"]: entry["checksum"]
                    for entry in await migration_status(conn)
                }
                assert entries[migration_id] == migration_checksum(
                    migration_id
                )
                await rollback_migration(conn, migration_id)
            finally:
                await conn.close()


@pytest.mark.asyncio
class TestLegacyCreateAllOnPostgres:
    async def test_legacy_create_all_round_trips_weekly_schedule(
        self, test_pg_url
    ):
        """The legacy tables' owner IS create_all (exactly what production
        lifespan runs) — prove it provisions a usable schema on real
        Postgres. WeeklySchedule, not FieldTeam: the duplicate FieldTeam
        classes merge into one extend_existing mutant table (documented
        4.2 finding, out of scope)."""
        from datetime import date

        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import (
            async_sessionmaker,
            create_async_engine,
        )

        from core.database import Base
        from models.schedule import WeeklySchedule
        import models  # noqa: F401

        normalized = test_pg_url.replace("postgres://", "postgresql://", 1)
        url = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                # Disposability guard: loopback alone does not prove the DB is
                # disposable — a dev's local Postgres is loopback too. If any
                # legacy table already exists, create_all would silently
                # attach and the finally-block drop_all would DESTROY it.
                existing = await conn.run_sync(
                    lambda sync_conn: [
                        table
                        for table in Base.metadata.tables
                        if sync_conn.dialect.has_table(sync_conn, table)
                    ]
                )
                if existing:
                    raise RuntimeError(
                        f"database already holds legacy tables {existing!r} — "
                        "it is not disposable; point "
                        "SCHEDULER_TEST_POSTGRES_URL at an EMPTY throwaway "
                        "database"
                    )
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine)
            async with session_factory() as session:
                schedule = WeeklySchedule(
                    schedule_code="WS-2026-29",
                    week_number=29,
                    year=2026,
                    start_date=date(2026, 7, 13),
                    end_date=date(2026, 7, 19),
                    status="draft",
                    total_water_demand_m3=125000.0,
                    total_water_allocated_m3=118000.0,
                    total_operations=42,
                    field_days=[date(2026, 7, 14), date(2026, 7, 16)],
                )
                session.add(schedule)
                await session.commit()
                loaded = (
                    await session.execute(
                        select(WeeklySchedule).where(
                            WeeklySchedule.week_number == 29
                        )
                    )
                ).scalar_one()
                assert (loaded.year, loaded.status) == (2026, "draft")
        finally:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            await engine.dispose()
