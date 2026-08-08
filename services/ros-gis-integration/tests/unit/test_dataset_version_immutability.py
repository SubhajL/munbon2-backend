"""
#150 — ros_gis.dataset_versions append-only + immutable identity (migration 0004).

Unlike the history tables hardened by 0001 (fully row-immutable), dataset_versions
is only PARTIALLY immutable under UPDATE: status transitions draft -> active ->
superseded and effective_from/effective_to (and source_description) are set during
the lifecycle. So 0004 installs a trigger that:
  * rejects any non-UPDATE op -- DELETE (row-level) and TRUNCATE (statement-level)
    -- outright (append-only ledger), mirroring 0001's history-table immutability
    and closing the `TRUNCATE ... CASCADE` reset path; and
  * on UPDATE, rejects the change only when an IMMUTABLE column really changes
    (source_hash, dataset_kind, dataset_version_id, created_at) -- COLUMN-SELECTIVE.

These are SQL-shape regression guards. The load-bearing proof — that a stored
provenance pair cannot be orphaned by a real UPDATE/DELETE/TRUNCATE — lives in
tests/integration/test_dataset_version_immutability_postgres.py.
"""
import re
import subprocess
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = SERVICE_ROOT / "migrations"
UP_SQL = MIGRATIONS / "0004_dataset_version_identity_immutable.up.sql"
DOWN_SQL = MIGRATIONS / "0004_dataset_version_identity_immutable.down.sql"

IMMUTABLE_COLUMNS = ("source_hash", "dataset_kind", "dataset_version_id", "created_at")
MUTABLE_COLUMNS = ("status", "effective_from", "effective_to")


class TestMigration0004Files:
    def test_both_directions_exist_and_are_tracked(self):
        assert UP_SQL.is_file() and DOWN_SQL.is_file()
        for path in (UP_SQL, DOWN_SQL):
            # check-ignore alone cannot prove tracking (it returns non-zero for an
            # ordinary untracked-but-not-ignored file, and for fatal git errors);
            # require BOTH "not ignored" (rc==1) AND "tracked" (ls-files rc==0).
            ignored = subprocess.run(
                ["git", "check-ignore", "-q", str(path)],
                cwd=SERVICE_ROOT,
                capture_output=True,
            )
            assert ignored.returncode == 1, f"{path.name} is gitignored (blanket *.sql)"
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(path)],
                cwd=SERVICE_ROOT,
                capture_output=True,
            )
            assert tracked.returncode == 0, f"{path.name} is not tracked by git"


class TestMigration0004Up:
    def _up(self) -> str:
        return UP_SQL.read_text(encoding="utf-8")

    def test_installs_both_immutability_triggers_on_the_parent_table(self):
        up = self._up()
        assert (
            "CREATE FUNCTION ros_gis.reject_dataset_version_identity_change()" in up
        )
        # row-level guard for UPDATE + DELETE
        assert "BEFORE UPDATE OR DELETE ON ros_gis.dataset_versions" in up
        assert "FOR EACH ROW" in up
        # statement-level guard for TRUNCATE (row triggers never fire on TRUNCATE)
        assert "BEFORE TRUNCATE ON ros_gis.dataset_versions" in up
        assert "FOR EACH STATEMENT" in up
        assert "RAISE EXCEPTION" in up

    def test_rejects_every_non_update_op_as_append_only(self):
        up = self._up()
        assert "TG_OP <> 'UPDATE'" in up
        assert "append-only" in up

    def test_guards_every_immutable_column_with_is_distinct_from(self):
        up = self._up()
        for col in IMMUTABLE_COLUMNS:
            assert re.search(
                rf"NEW\.{col}\s+IS DISTINCT FROM\s+OLD\.{col}", up
            ), f"missing IS DISTINCT FROM guard for immutable column {col}"

    def test_update_path_stays_column_selective(self):
        # The UPDATE branch must never reference a legitimately-mutable column, or
        # activation (draft -> active -> superseded, effective_*) would be blocked.
        up = self._up()
        for col in MUTABLE_COLUMNS:
            assert f"NEW.{col}" not in up, f"UPDATE guard wrongly references {col}"

    def test_is_ddl_only_and_rewrites_no_data(self):
        # A trigger DEFINITION naming UPDATE/DELETE/TRUNCATE is fine; an EXECUTED
        # data statement is not. Anchor at line start so an indented statement is
        # still caught; match qualified OR unqualified table names; cover INSERT.
        up = self._up()
        assert re.search(r'(?im)^\s*UPDATE\s+[\w."]+\s+SET\b', up) is None
        assert re.search(r"(?im)^\s*INSERT\s+INTO\b", up) is None
        assert re.search(r"(?im)^\s*DELETE\s+FROM\b", up) is None
        assert re.search(r"(?im)^\s*TRUNCATE\b", up) is None
        assert "DROP TABLE" not in up.upper()


class TestMigration0004Down:
    def _down(self) -> str:
        return DOWN_SQL.read_text(encoding="utf-8")

    def test_drops_both_triggers_and_the_function(self):
        down = self._down()
        assert down.count("DROP TRIGGER IF EXISTS") == 2  # identity + truncate guards
        assert "ros_gis.dataset_versions" in down
        assert (
            "DROP FUNCTION IF EXISTS ros_gis.reject_dataset_version_identity_change"
            in down
        )

    def test_touches_no_table_or_data(self):
        upper = self._down().upper()
        assert "DROP TABLE" not in upper
        assert "DELETE FROM" not in upper  # registry deletion is migrate.py's job

    def test_trigger_drop_is_guarded_against_a_missing_table(self):
        # Out-of-order rollback (0001 before 0004) may have already dropped the
        # table; the guard keeps this down from erroring and stranding the function.
        assert "to_regclass('ros_gis.dataset_versions')" in self._down()
