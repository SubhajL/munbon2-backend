import subprocess
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = SERVICE_ROOT / "migrations"
UP_SQL = MIGRATIONS / "0003_daily_requirement_producer.up.sql"
DOWN_SQL = MIGRATIONS / "0003_daily_requirement_producer.down.sql"


def test_daily_requirement_producer_migration_is_tracked_and_reversible():
    assert UP_SQL.is_file() and DOWN_SQL.is_file()
    for path in (UP_SQL, DOWN_SQL):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=SERVICE_ROOT,
            capture_output=True,
        )
        assert ignored.returncode != 0


def test_up_adds_append_only_fe_crop_settings_and_database_deduplication():
    up = UP_SQL.read_text(encoding="utf-8")

    assert "CREATE TABLE ros_gis.section_crop_settings" in up
    assert "section_id TEXT NOT NULL" in up
    assert "crop_type TEXT NOT NULL" in up
    assert "planted_area_rai NUMERIC(18, 6) NOT NULL" in up
    assert "expected_harvest_date DATE NOT NULL" in up
    assert "source TEXT NOT NULL" in up
    assert "as_of_date DATE NOT NULL" in up
    assert "section_crop_settings_are_append_only" in up
    assert "BEFORE UPDATE OR DELETE" in up
    assert "uq_water_requirement_runs_identical_nonfailed_input" in up
    assert "WHERE status IN ('calculating', 'published', 'superseded')" in up


def test_down_removes_only_pr_0_3_schema_objects():
    down = DOWN_SQL.read_text(encoding="utf-8")

    assert (
        "DROP INDEX IF EXISTS ros_gis.uq_water_requirement_runs_identical_nonfailed_input"
        in down
    )
    assert "DROP TABLE IF EXISTS ros_gis.section_crop_settings" in down
    assert "water_requirement_runs" not in down.replace(
        "uq_water_requirement_runs_identical_nonfailed_input", ""
    )
    assert "daily_water_requirements" not in down
