"""
Wave 2.5 dataset-version schema (WAVE_2-4_PLAN §1.5 HIGH #5): section master and
section→gate crosswalk become versioned datasets under a dataset_versions parent —
composite-key immutable history + current views — because sections.section_id as a
sole PK cannot express version+effective-date, and a GLOBAL partial-unique
is_primary would reject historical mappings.

Schema-only slice (the RID-gated load comes later): SQLAlchemy models, tracked
up/down migration SQL (exception to the blanket *.sql credential guard), and a
transactional migration runner with a checksum registry (MED #6: the exact apply/
rollback commands are `python migrations/migrate.py apply|rollback|status`).
No live DB anywhere in this suite — DDL is compiled/inspected, the runner runs
against a stub connection with failure injection (2.6b rule).
"""
import re
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from db.models import (
    Base,
    GATE_ID_PATTERN,
    DatasetVersion,
    GateMapping,
    GateMappingVersion,
    Section,
    SectionMasterVersion,
    VersionedBase,
)

SERVICE_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = SERVICE_ROOT / "migrations"
UP_SQL = MIGRATIONS / "0001_dataset_version_parent.up.sql"
DOWN_SQL = MIGRATIONS / "0001_dataset_version_parent.down.sql"


def _compiled_ddl(model) -> str:
    pieces = [str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))]
    pieces += [
        str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for index in model.__table__.indexes
    ]
    return "\n".join(pieces)


class TestDatasetVersionParentModel:
    def test_migration_owned_models_are_not_in_runtime_create_all_metadata(self):
        assert VersionedBase is not Base
        assert set(VersionedBase.metadata.tables) == {
            "ros_gis.dataset_versions",
            "ros_gis.section_master_history",
            "ros_gis.gate_mapping_history",
        }
        assert not set(VersionedBase.metadata.tables) & set(Base.metadata.tables)

    def test_parent_identity_and_kinds(self):
        table = DatasetVersion.__table__
        assert table.schema == "ros_gis" and table.name == "dataset_versions"
        assert [c.name for c in table.primary_key.columns] == ["dataset_version_id"]
        ddl = _compiled_ddl(DatasetVersion)
        assert "GENERATED ALWAYS AS IDENTITY" in ddl
        assert "section_master" in ddl and "gate_crosswalk" in ddl
        assert "'draft'" in ddl and "'active'" in ddl and "'superseded'" in ddl

    def test_only_one_active_dataset_per_kind(self):
        ddl = _compiled_ddl(DatasetVersion)
        assert "UNIQUE" in ddl.upper()
        assert "WHERE" in ddl and "active" in ddl  # partial unique on status='active'

    def test_instants_are_timestamptz(self):
        ddl = str(
            CreateTable(DatasetVersion.__table__).compile(dialect=postgresql.dialect())
        ).upper()
        assert "TIMESTAMP WITH TIME ZONE" in ddl
        assert "TIMESTAMP WITHOUT TIME ZONE" not in ddl


class TestVersionedHistoryModels:
    def test_section_history_uses_composite_key_under_the_parent(self):
        table = SectionMasterVersion.__table__
        assert table.schema == "ros_gis" and table.name == "section_master_history"
        assert [c.name for c in table.primary_key.columns] == [
            "dataset_version_id",
            "section_id",
            "valid_from",
        ]
        assert any(
            fk.column.table.name == "dataset_versions"
            for c in table.columns
            for fk in c.foreign_keys
        )
        assert "irrigation_channel" in table.columns
        ddl = _compiled_ddl(SectionMasterVersion)
        assert "dataset_kind = 'section_master'" in ddl
        assert "FOREIGN KEY(dataset_version_id, dataset_kind)" in ddl

    def test_gate_mapping_history_key_is_dataset_section_gate_validity(self):
        table = GateMappingVersion.__table__
        assert table.schema == "ros_gis" and table.name == "gate_mapping_history"
        assert [c.name for c in table.primary_key.columns] == [
            "dataset_version_id",
            "section_id",
            "gate_id",
            "valid_from",
        ]
        assert "irrigation_channel" in table.columns
        ddl = _compiled_ddl(GateMappingVersion)
        assert "dataset_kind = 'gate_crosswalk'" in ddl
        assert "FOREIGN KEY(dataset_version_id, dataset_kind)" in ddl

    @pytest.mark.parametrize("model", [SectionMasterVersion, GateMappingVersion])
    def test_overlapping_validity_ranges_are_excluded(self, model):
        # HIGH #5: 'reject overlapping validity ranges' — a real exclusion
        # constraint, not an application-side promise.
        ddl = _compiled_ddl(model)
        assert "EXCLUDE USING gist" in ddl
        assert "valid_from" in ddl and "valid_to" in ddl

    def test_primary_gate_is_exclusive_per_dataset_section_and_interval(self):
        # A HISTORICAL primary must stay storable: primary-exclusivity is scoped
        # to (dataset version, section, effective interval), never global — the
        # exact defect HIGH #5 names. With validity in the key this is an
        # exclusion constraint over the range, filtered to primary rows.
        ddl = _compiled_ddl(GateMappingVersion)
        primary_exclusions = [
            block
            for block in ddl.split("EXCLUDE USING gist")
            if "is_primary" in block and "dataset_version_id" in block
        ]
        assert primary_exclusions, "missing primary-mapping exclusion constraint"

    @pytest.mark.parametrize("model", [SectionMasterVersion, GateMappingVersion])
    def test_empty_or_reversed_validity_is_rejected(self, model):
        assert "valid_from < valid_to" in _compiled_ddl(model)


class TestGateIdVocabulary:
    """One pattern, cross-pinned: models.py constant == SQL CHECK == M(i,j) grammar."""

    @pytest.mark.parametrize(
        "gate_id", ["M(0,0)", "M(0,3)", "M (0,3)", "M(0,3;1,0)", "M (0,3; 1,0)"]
    )
    def test_accepts_the_flow_monitoring_gate_grammar(self, gate_id):
        assert re.fullmatch(GATE_ID_PATTERN, gate_id)

    @pytest.mark.parametrize("gate_id", ["S", "not-a-gate", "M(0,3", "M()", "M(a,b)"])
    def test_rejects_non_gate_ids(self, gate_id):
        assert re.fullmatch(GATE_ID_PATTERN, gate_id) is None

    def test_models_and_migration_share_the_single_pattern(self):
        up = UP_SQL.read_text(encoding="utf-8")
        assert GATE_ID_PATTERN in up, "SQL CHECK drifted from models.GATE_ID_PATTERN"
        assert GATE_ID_PATTERN in _compiled_ddl(GateMappingVersion)

    def test_legacy_current_mapping_does_not_claim_canonical_gate_vocabulary(self):
        assert GATE_ID_PATTERN not in _compiled_ddl(GateMapping)


class TestHardenedCurrentModels:
    def test_current_gate_mappings_gain_channel_and_scoped_primary(self):
        table = GateMapping.__table__
        assert "irrigation_channel" in table.columns
        ddl = _compiled_ddl(GateMapping)
        assert any(
            "UNIQUE" in line.upper() and "is_primary" in line
            for line in ddl.splitlines()
        )
        assert GateMapping.__table__.c.is_primary.default.arg is False
        assert GateMapping.__table__.c.is_primary.nullable is False
        assert GateMapping.__table__.c.is_primary.server_default is not None

    def test_sections_gain_irrigation_channel(self):
        assert "irrigation_channel" in Section.__table__.columns
        ddl = _compiled_ddl(Section)
        assert "geometry(GEOMETRY,4326)" in ddl
        assert "GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')" in ddl


class TestMigrationFiles:
    def test_both_directions_exist_and_are_tracked(self):
        assert UP_SQL.is_file() and DOWN_SQL.is_file()
        for path in (UP_SQL, DOWN_SQL):
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", str(path)],
                cwd=SERVICE_ROOT,
                capture_output=True,
            )
            assert ignored.returncode != 0, f"{path.name} is gitignored (blanket *.sql)"

        dump = MIGRATIONS / "production-dump.sql"
        ignored_dump = subprocess.run(
            ["git", "check-ignore", "-q", str(dump)],
            cwd=SERVICE_ROOT,
            capture_output=True,
        )
        assert ignored_dump.returncode == 0

    def test_up_creates_the_versioned_schema(self):
        up = UP_SQL.read_text(encoding="utf-8")
        assert "CREATE EXTENSION IF NOT EXISTS btree_gist" in up
        assert "CREATE EXTENSION IF NOT EXISTS postgis" in up
        for table in (
            "ros_gis.dataset_versions",
            "ros_gis.section_master_history",
            "ros_gis.gate_mapping_history",
        ):
            assert f"CREATE TABLE {table}" in up
            assert f"CREATE TABLE IF NOT EXISTS {table}" not in up
        assert up.count("EXCLUDE USING gist") == 3  # 2x validity overlap + primary
        assert "CREATE OR REPLACE VIEW ros_gis.sections_current" in up
        assert "CREATE OR REPLACE VIEW ros_gis.gate_mappings_current" in up
        assert "status = 'active'" in up
        assert up.count("dv.effective_from <= now()") == 2
        assert up.count("now() < dv.effective_to") == 2
        assert up.count("reject_immutable_dataset_row_change") >= 3
        assert "BEFORE UPDATE OR DELETE ON ros_gis.section_master_history" in up
        assert "BEFORE UPDATE OR DELETE ON ros_gis.gate_mapping_history" in up

    def test_up_hardens_but_never_rewrites_data(self):
        up = UP_SQL.read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS irrigation_channel" in up
        assert "ALTER TABLE IF EXISTS ros_gis.sections" in up
        assert "ALTER TABLE IF EXISTS ros_gis.gate_mappings" in up
        assert "geometry(GEOMETRY, 4326)" in up
        assert "chk_sections_polygonal_geometry" in up
        assert "'ros_gis.sections'::regclass" not in up
        assert "chk_gate_mappings_gate_id_grammar" not in up
        assert "duplicate primary gate mappings for section" in up
        assert "HAVING COUNT(*) > 1" in up
        assert "CREATE UNIQUE INDEX uq_gate_mappings_one_primary_per_section" in up
        upper = up.upper()
        assert "DROP TABLE" not in upper
        assert "\nUPDATE " not in upper and "DELETE FROM" not in upper
        assert "TIMESTAMPTZ" in up
        assert not re.search(r"\bTIMESTAMP\b(?!TZ)", up)

    def test_down_reverses_only_what_up_created(self):
        down = DOWN_SQL.read_text(encoding="utf-8")
        for name in (
            "ros_gis.gate_mappings_current",
            "ros_gis.sections_current",
            "ros_gis.gate_mapping_history",
            "ros_gis.section_master_history",
            "ros_gis.dataset_versions",
        ):
            assert name in down
        # The pre-existing data tables must survive a rollback.
        upper = down.upper()
        assert "DROP TABLE IF EXISTS ROS_GIS.SECTIONS;" not in upper
        assert "DROP TABLE IF EXISTS ROS_GIS.GATE_MAPPINGS;" not in upper
        assert "DROP COLUMN" not in upper
        assert "DELETE FROM" not in upper or "SCHEMA_MIGRATIONS" in upper


class _StubConn:
    def __init__(self, applied=None, fail_at=None, registry_exists=None):
        self.executed = []
        self.applied = dict(applied or {})  # migration_id -> checksum
        self.fail_at = fail_at
        self.registry_exists = (
            bool(self.applied) if registry_exists is None else registry_exists
        )
        self._tx_depth = 0

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self):
                conn._tx_depth += 1
                return conn

            async def __aexit__(self, *exc):
                conn._tx_depth -= 1
                return False

        return _Tx()

    async def execute(self, sql, *args):
        if self.fail_at is not None and len(self.executed) >= self.fail_at:
            raise ConnectionError("db lost")
        self.executed.append((sql, args, self._tx_depth > 0))
        if "CREATE TABLE IF NOT EXISTS ros_gis.schema_migrations" in sql:
            self.registry_exists = True
        return "OK"

    async def fetchval(self, sql, *args):
        if "to_regclass" in sql:
            return "ros_gis.schema_migrations" if self.registry_exists else None
        raise AssertionError(f"unexpected fetchval: {sql}")

    async def fetchrow(self, sql, *args):
        if "schema_migrations" in sql and args:
            checksum = self.applied.get(args[0])
            return None if checksum is None else {"checksum": checksum}
        return None

    async def fetch(self, sql, *args):
        if "schema_migrations" in sql:
            return [
                {"migration_id": key, "checksum": value, "applied_at": "now"}
                for key, value in sorted(self.applied.items())
            ]
        raise AssertionError(f"unexpected fetch: {sql}")


class TestMigrationRunner:
    @pytest.mark.asyncio
    async def test_apply_runs_up_sql_transactionally_and_registers(self):
        from migrations.migrate import (
            MIGRATIONS_LOCK_ID,
            MIGRATIONS_SCHEMA_DDL,
            MIGRATIONS_REGISTRY_DDL,
            apply_migration,
            migration_checksum,
        )

        conn = _StubConn()
        await apply_migration(conn, "0001_dataset_version_parent")
        sqls = [sql for sql, _, _ in conn.executed]
        assert conn.executed[0] == (
            "SELECT pg_advisory_xact_lock($1)",
            (MIGRATIONS_LOCK_ID,),
            True,
        )
        assert sqls[1:3] == [MIGRATIONS_SCHEMA_DDL, MIGRATIONS_REGISTRY_DDL]
        migration_payloads = [
            s for s in sqls if "CREATE TABLE ros_gis.dataset_versions" in s
        ]
        assert migration_payloads == [UP_SQL.read_text(encoding="utf-8")]
        registered = [
            (sql, args)
            for sql, args, _ in conn.executed
            if "INSERT INTO ros_gis.schema_migrations" in sql
        ]
        assert len(registered) == 1
        assert registered[0][1][1] == migration_checksum("0001_dataset_version_parent")
        assert all(
            in_tx
            for sql, _, in_tx in conn.executed
            if "schema_migrations" not in sql or "INSERT" in sql
        ), "migration statements must run inside one transaction"
        assert MIGRATIONS_REGISTRY_DDL  # exported for shape locks

    @pytest.mark.asyncio
    async def test_apply_is_idempotent_when_checksum_matches(self):
        from migrations.migrate import apply_migration, migration_checksum

        conn = _StubConn(
            applied={
                "0001_dataset_version_parent": migration_checksum(
                    "0001_dataset_version_parent"
                )
            }
        )
        result = await apply_migration(conn, "0001_dataset_version_parent")
        assert result == "already-applied"
        assert not any("dataset_versions" in sql for sql, _, _ in conn.executed)

    @pytest.mark.asyncio
    async def test_apply_refuses_on_checksum_drift(self):
        from migrations.migrate import MigrationError, apply_migration

        conn = _StubConn(applied={"0001_dataset_version_parent": "deadbeef"})
        with pytest.raises(MigrationError, match="checksum"):
            await apply_migration(conn, "0001_dataset_version_parent")

    @pytest.mark.asyncio
    async def test_rollback_runs_down_sql_and_deregisters(self):
        from migrations.migrate import migration_checksum, rollback_migration

        conn = _StubConn(
            applied={
                "0001_dataset_version_parent": migration_checksum(
                    "0001_dataset_version_parent"
                )
            }
        )
        await rollback_migration(conn, "0001_dataset_version_parent")
        sqls = [sql for sql, _, _ in conn.executed]
        assert any("DROP" in s for s in sqls)
        assert any("DELETE FROM ros_gis.schema_migrations" in s for s in sqls)

    @pytest.mark.asyncio
    async def test_rollback_refuses_when_either_direction_drifted(self):
        from migrations.migrate import MigrationError, rollback_migration

        conn = _StubConn(applied={"0001_dataset_version_parent": "deadbeef"})
        with pytest.raises(MigrationError, match="checksum"):
            await rollback_migration(conn, "0001_dataset_version_parent")

    @pytest.mark.asyncio
    async def test_rollback_of_unapplied_migration_refuses(self):
        from migrations.migrate import MigrationError, rollback_migration

        conn = _StubConn()
        with pytest.raises(MigrationError, match="not applied"):
            await rollback_migration(conn, "0001_dataset_version_parent")

    @pytest.mark.asyncio
    async def test_mid_apply_failure_raises_and_never_registers(self):
        from migrations.migrate import apply_migration

        conn = _StubConn(fail_at=3)
        with pytest.raises(ConnectionError):
            await apply_migration(conn, "0001_dataset_version_parent")
        assert not any(
            "INSERT INTO ros_gis.schema_migrations" in sql
            for sql, _, _ in conn.executed
        )

    @pytest.mark.asyncio
    async def test_unknown_migration_id_fails_closed(self):
        from migrations.migrate import MigrationError, apply_migration

        conn = _StubConn()
        with pytest.raises(MigrationError, match="unknown migration"):
            await apply_migration(conn, "9999_does_not_exist")

    @pytest.mark.asyncio
    async def test_status_is_read_only_when_registry_does_not_exist(self):
        from migrations.migrate import migration_status

        conn = _StubConn(registry_exists=False)
        assert await migration_status(conn) == []
        assert conn.executed == []

    def test_connection_kwargs_preserve_reserved_password_characters(self):
        from migrations.migrate import postgres_connection_kwargs

        assert postgres_connection_kwargs(
            "postgresql://operator:p@ss!@db.example:5439/munbon_dev"
        ) == {
            "user": "operator",
            "password": "p@ss!",
            "host": "db.example",
            "port": 5439,
            "database": "munbon_dev",
        }
