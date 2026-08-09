"""Real-Postgres proof that ros_gis.dataset_versions is append-only with an
immutable identity (#150).

Applies migrations 0001 (dataset-version parent + history) then 0004 (append-only
identity trigger) against a disposable Postgres, then proves the R0 provenance
pair `(dataset_version_id, source_hash)` cannot be orphaned by ANY ros_gis write:

  * changing `source_hash`                -> rejected (identity immutable)
  * changing `dataset_kind`               -> rejected (identity immutable)
  * changing `created_at`                 -> rejected (identity immutable)
  * `SET dataset_version_id = DEFAULT`    -> rejected (identity immutable)
        (the GENERATED-ALWAYS reassignment hole: Postgres permits this natively
         and it would assign a fresh id, orphaning the pair)
  * `SET dataset_version_id = <explicit>` -> rejected natively (GENERATED ALWAYS)
  * `DELETE` of the parent row            -> rejected (append-only), even for a
        CHILDLESS active version that no FK protects
  * `TRUNCATE ... CASCADE`                -> rejected (append-only, statement-level)

...while proving the trigger is COLUMN-SELECTIVE under UPDATE: the full
draft -> active -> superseded lifecycle with effective_* still succeeds. The down
migration is exercised (apply -> rollback -> reapply), not just string-checked.
Gated on DATASET_VERSION_TEST_POSTGRES_URL (a disposable loopback database).
"""
import os
from contextlib import asynccontextmanager

import asyncpg
import pytest

from migrations.migrate import (
    MigrationError,
    apply_migration,
    rollback_migration,
)

POSTGRES_URL = os.environ.get("DATASET_VERSION_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="DATASET_VERSION_TEST_POSTGRES_URL is not configured",
)

MIGRATION_0004 = "0004_dataset_version_identity_immutable"


async def _noninternal_trigger_count(conn) -> int:
    return await conn.fetchval(
        "SELECT count(*) FROM pg_trigger t "
        "JOIN pg_class c ON c.oid = t.tgrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname='ros_gis' AND c.relname='dataset_versions' "
        "AND NOT t.tgisinternal"
    )

# Substrings of the trigger's RAISE messages — asserted so a rejection is
# attributed to THIS trigger, not to some incidental constraint.
IDENTITY_ERROR = "identity is immutable"
APPEND_ONLY_ERROR = "append-only"

# The schema is committed once per test process; later tests re-use it (each still
# opens its own connection so test data stays isolated in a rolled-back tx).
_schema_applied = False


async def _ensure_schema(conn: asyncpg.Connection) -> None:
    global _schema_applied
    if _schema_applied:
        return
    await apply_migration(conn, "0001_dataset_version_parent")
    await apply_migration(conn, MIGRATION_0004)
    _schema_applied = True


@asynccontextmanager
async def _prepared_conn():
    """A connection with the schema applied and test data isolated in a
    transaction that is always rolled back, so tests never leave residue and never
    collide on the one-active-per-kind partial unique index."""
    connection = await asyncpg.connect(POSTGRES_URL)
    try:
        await _ensure_schema(connection)
        tx = connection.transaction()
        await tx.start()
        try:
            yield connection
        finally:
            await tx.rollback()
    finally:
        await connection.close()


async def _insert_version(conn, *, source_hash, kind="section_master"):
    return await conn.fetchval(
        """
        INSERT INTO ros_gis.dataset_versions (dataset_kind, source_hash, status)
        VALUES ($1, $2, 'draft')
        RETURNING dataset_version_id
        """,
        kind,
        source_hash,
    )


async def _expect_rejected(conn, sql, *args):
    """Run a mutating statement in a SAVEPOINT and require it to raise, leaving the
    surrounding transaction usable for read-back."""
    with pytest.raises(asyncpg.PostgresError) as exc:
        async with conn.transaction():  # savepoint; rolls back on the raise
            await conn.execute(sql, *args)
    return exc.value


@pytest.mark.asyncio
async def test_source_hash_update_is_rejected_and_row_unchanged():
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="hash-A")
        err = await _expect_rejected(
            conn,
            "UPDATE ros_gis.dataset_versions SET source_hash=$1 "
            "WHERE dataset_version_id=$2",
            "hash-B",
            vid,
        )
        assert IDENTITY_ERROR in str(err)
        assert (
            await conn.fetchval(
                "SELECT source_hash FROM ros_gis.dataset_versions "
                "WHERE dataset_version_id=$1",
                vid,
            )
            == "hash-A"
        )


@pytest.mark.asyncio
async def test_dataset_kind_update_is_rejected_and_row_unchanged():
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="hash-A", kind="section_master")
        err = await _expect_rejected(
            conn,
            "UPDATE ros_gis.dataset_versions SET dataset_kind='gate_crosswalk' "
            "WHERE dataset_version_id=$1",
            vid,
        )
        assert IDENTITY_ERROR in str(err)
        assert (
            await conn.fetchval(
                "SELECT dataset_kind FROM ros_gis.dataset_versions "
                "WHERE dataset_version_id=$1",
                vid,
            )
            == "section_master"
        )


@pytest.mark.asyncio
async def test_created_at_update_is_rejected_and_row_unchanged():
    # created_at is a creation timestamp that never legitimately changes; a mutable
    # one would let audit ordering be forged. Immutable like the identity columns.
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="hash-A")
        before = await conn.fetchval(
            "SELECT created_at FROM ros_gis.dataset_versions "
            "WHERE dataset_version_id=$1",
            vid,
        )
        err = await _expect_rejected(
            conn,
            "UPDATE ros_gis.dataset_versions "
            "SET created_at = created_at - interval '1 year' "
            "WHERE dataset_version_id=$1",
            vid,
        )
        assert IDENTITY_ERROR in str(err)
        assert (
            await conn.fetchval(
                "SELECT created_at FROM ros_gis.dataset_versions "
                "WHERE dataset_version_id=$1",
                vid,
            )
            == before
        )


@pytest.mark.asyncio
async def test_identity_pk_reset_to_default_is_rejected_by_the_trigger():
    # The subtle hole: dataset_version_id is GENERATED ALWAYS AS IDENTITY, which
    # Postgres lets you reset with `= DEFAULT` (assigning a fresh sequence value)
    # even though it rejects explicit values. That reassignment would orphan the
    # provenance pair, so the trigger must reject it -- the only guard for this
    # path, hence a non-vacuous trigger branch.
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="hash-A")
        err = await _expect_rejected(
            conn,
            "UPDATE ros_gis.dataset_versions SET dataset_version_id=DEFAULT "
            "WHERE dataset_version_id=$1",
            vid,
        )
        assert IDENTITY_ERROR in str(err)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM ros_gis.dataset_versions "
                "WHERE dataset_version_id=$1",
                vid,
            )
            == 1
        )


@pytest.mark.asyncio
async def test_identity_pk_explicit_value_update_is_rejected():
    # Reinforced by the GENERATED ALWAYS column definition itself (native
    # rejection), independent of the trigger; asserted so the whole identity is
    # provably closed, not just the DEFAULT path.
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="hash-A")
        await _expect_rejected(
            conn,
            "UPDATE ros_gis.dataset_versions SET dataset_version_id=$1 "
            "WHERE dataset_version_id=$2",
            vid + 100000,
            vid,
        )
        assert (
            await conn.fetchval(
                "SELECT dataset_version_id FROM ros_gis.dataset_versions "
                "WHERE dataset_version_id=$1",
                vid,
            )
            == vid
        )


@pytest.mark.asyncio
async def test_delete_is_rejected_append_only_even_for_childless_active_version():
    # A childless active version has NO history children, so the 0001 FK does not
    # protect it -- yet a stored provenance pair may point at it. DELETE must be
    # rejected outright so the pair cannot orphan.
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="keep-me")
        await conn.execute(
            "UPDATE ros_gis.dataset_versions SET status='active', "
            "effective_from=now() WHERE dataset_version_id=$1",
            vid,
        )
        err = await _expect_rejected(
            conn,
            "DELETE FROM ros_gis.dataset_versions WHERE dataset_version_id=$1",
            vid,
        )
        assert APPEND_ONLY_ERROR in str(err)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM ros_gis.dataset_versions "
                "WHERE dataset_version_id=$1 AND source_hash=$2",
                vid,
                "keep-me",
            )
            == 1
        )


@pytest.mark.asyncio
async def test_truncate_cascade_is_rejected_append_only():
    # Row-level triggers never fire on TRUNCATE, so a statement-level guard is
    # needed or `TRUNCATE ... CASCADE` would silently wipe the ledger and orphan
    # every provenance pair. CASCADE is required because the history tables
    # FK-reference dataset_versions.
    async with _prepared_conn() as conn:
        await _insert_version(conn, source_hash="keep-me")
        err = await _expect_rejected(
            conn, "TRUNCATE ros_gis.dataset_versions CASCADE"
        )
        assert APPEND_ONLY_ERROR in str(err)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM ros_gis.dataset_versions "
                "WHERE source_hash=$1",
                "keep-me",
            )
            == 1
        )


@pytest.mark.asyncio
async def test_full_activation_lifecycle_still_succeeds():
    # Column-selectivity guard: the UPDATE path must NOT be the blanket history
    # pattern. The complete draft -> active -> superseded transition, including a
    # non-null effective_to, must commit while the identity stays fixed.
    # (effective_from/effective_to use distinct instants; both now() calls in one
    # tx share the transaction timestamp, which would trip the effective_from <
    # effective_to check -- a constraint, not this trigger.)
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="hash-A")
        await conn.execute(
            "UPDATE ros_gis.dataset_versions "
            "SET status='active', effective_from=now() - interval '1 day', "
            "    source_description='activated by #150 test' "
            "WHERE dataset_version_id=$1",
            vid,
        )
        await conn.execute(
            "UPDATE ros_gis.dataset_versions "
            "SET status='superseded', effective_to=now() "
            "WHERE dataset_version_id=$1",
            vid,
        )
        row = await conn.fetchrow(
            "SELECT status, effective_from, effective_to, source_description, "
            "source_hash, dataset_kind FROM ros_gis.dataset_versions "
            "WHERE dataset_version_id=$1",
            vid,
        )
        assert row["status"] == "superseded"
        assert row["effective_from"] is not None
        assert row["effective_to"] is not None
        assert row["source_description"] == "activated by #150 test"
        # identity untouched by the whole lifecycle
        assert row["source_hash"] == "hash-A"
        assert row["dataset_kind"] == "section_master"


@pytest.mark.asyncio
async def test_provenance_pair_cannot_be_orphaned_by_any_write():
    # The issue's explicit exit-gate proof: a stored (dataset_version_id,
    # source_hash) pair resolves to exactly one row before AND after every
    # identity-mutating UPDATE, the DELETE, and the TRUNCATE the ROS side could
    # attempt. The vectors are deliberately re-listed here as one aggregate check;
    # the focused per-vector tests above remain the primary regression guards (a
    # new immutable column gets its own focused test), so this list drifting would
    # weaken the aggregate but never remove coverage of that column.
    async with _prepared_conn() as conn:
        vid = await _insert_version(conn, source_hash="prov-hash")

        async def pair_resolves():
            return await conn.fetchval(
                "SELECT count(*) FROM ros_gis.dataset_versions "
                "WHERE dataset_version_id=$1 AND source_hash=$2",
                vid,
                "prov-hash",
            )

        assert await pair_resolves() == 1
        attacks = [
            ("UPDATE ros_gis.dataset_versions SET source_hash='moved' "
             "WHERE dataset_version_id=$1", (vid,)),
            ("UPDATE ros_gis.dataset_versions SET dataset_kind='gate_crosswalk' "
             "WHERE dataset_version_id=$1", (vid,)),
            ("UPDATE ros_gis.dataset_versions "
             "SET created_at = created_at - interval '1 year' "
             "WHERE dataset_version_id=$1", (vid,)),
            ("UPDATE ros_gis.dataset_versions SET dataset_version_id=DEFAULT "
             "WHERE dataset_version_id=$1", (vid,)),
            ("UPDATE ros_gis.dataset_versions SET dataset_version_id=$1 "
             "WHERE dataset_version_id=$2", (vid + 100000, vid)),
            ("DELETE FROM ros_gis.dataset_versions "
             "WHERE dataset_version_id=$1", (vid,)),
            ("TRUNCATE ros_gis.dataset_versions CASCADE", ()),
        ]
        for sql, args in attacks:
            await _expect_rejected(conn, sql, *args)
        # unchanged and still uniquely resolvable
        assert await pair_resolves() == 1


@pytest.mark.asyncio
async def test_down_migration_round_trips_against_real_postgres():
    # Service convention (CLAUDE.md 0002 note): DDL pairs are proven by apply ->
    # rollback -> reapply on real PostGIS, not just a string check of the down SQL.
    # Runs committed operations on its own connection and always restores 0004.
    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        await _ensure_schema(conn)
        try:
            assert await _noninternal_trigger_count(conn) == 2  # identity + truncate guards
            await rollback_migration(conn, MIGRATION_0004)
            assert await _noninternal_trigger_count(conn) == 0  # the down really executed
        finally:
            # Always restore, so a mid-test failure cannot break sibling tests.
            await apply_migration(conn, MIGRATION_0004)
        assert await _noninternal_trigger_count(conn) == 2  # reapply restored both guards
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_out_of_order_rollback_is_refused_with_no_persistent_change():
    # #155 incident path: with 0001 and 0004 both registered, rolling back 0001
    # must raise MigrationError and leave NO persistent change — triggers and
    # the full registry survive the attempt unchanged. (That the refusal happens
    # before the down statement is even attempted is pinned statement-level by
    # the unit suite's executed-list assert, which a real rolled-back tx cannot
    # distinguish.)
    async def registered_ids(conn):
        return [
            row["migration_id"]
            for row in await conn.fetch(
                "SELECT migration_id FROM ros_gis.schema_migrations "
                "ORDER BY migration_id"
            )
        ]

    conn = await asyncpg.connect(POSTGRES_URL)
    try:
        await _ensure_schema(conn)
        before = await registered_ids(conn)
        assert "0001_dataset_version_parent" in before
        assert MIGRATION_0004 in before
        assert await _noninternal_trigger_count(conn) == 2
        try:
            with pytest.raises(MigrationError, match="latest-first") as excinfo:
                await rollback_migration(conn, "0001_dataset_version_parent")
            assert MIGRATION_0004 in str(excinfo.value)
            assert await _noninternal_trigger_count(conn) == 2
            assert await registered_ids(conn) == before
        finally:
            # If the guard is absent or broken, the rollback executed 0001's
            # down (dropping the parent table when no FK from 0002 blocks it);
            # restore 0001+0004 so sibling tests keep a valid schema.
            await apply_migration(conn, "0001_dataset_version_parent")
            if await _noninternal_trigger_count(conn) == 0:
                await rollback_migration(conn, MIGRATION_0004)
                await apply_migration(conn, MIGRATION_0004)
    finally:
        await conn.close()
