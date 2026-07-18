"""Drift lock: the ControlBase ORM must mirror the migration DDL (0001 + 0002)."""

import re
from pathlib import Path

import models.control_plan  # noqa: F401  (registers control tables)
from models.control_base import ControlBase

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
UP_FILES = sorted(MIGRATIONS_DIR.glob("*.up.sql"))
DOWN_FILES = sorted(MIGRATIONS_DIR.glob("*.down.sql"))
ALL_UP = "\n".join(path.read_text() for path in UP_FILES)
ALL_DOWN = "\n".join(path.read_text() for path in DOWN_FILES)


def _ddl_block(table_name: str) -> str:
    pattern = re.compile(
        rf"CREATE TABLE scheduler\.{table_name} \((?s:.*?)\n\);",
    )
    match = pattern.search(ALL_UP)
    assert match, f"no up.sql creates scheduler.{table_name}"
    return match.group(0)


def _code_lines(sql: str) -> str:
    return "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )


class TestMigrationPairShape:
    def test_pairs_exist_and_are_nonempty(self):
        assert UP_FILES and DOWN_FILES
        assert len(UP_FILES) == len(DOWN_FILES)
        assert ALL_UP.strip() and ALL_DOWN.strip()

    def test_up_creates_every_orm_table_and_down_drops_it(self):
        for qualified in ControlBase.metadata.tables:
            table_name = qualified.split(".", 1)[1]
            assert f"CREATE TABLE scheduler.{table_name} (" in ALL_UP
            assert f"DROP TABLE scheduler.{table_name};" in ALL_DOWN

    def test_migrations_create_no_extra_tables(self):
        created = set(re.findall(r"CREATE TABLE scheduler\.(\w+)", ALL_UP))
        orm_tables = {
            name.split(".", 1)[1] for name in ControlBase.metadata.tables
        }
        assert created == orm_tables

    def test_every_orm_column_appears_in_its_table_ddl(self):
        for qualified, table in ControlBase.metadata.tables.items():
            block = _ddl_block(qualified.split(".", 1)[1])
            for column in table.columns:
                assert re.search(
                    rf"^\s+{re.escape(column.name)} ", block, re.MULTILINE
                ), f"{qualified}.{column.name} missing from up.sql"

    def test_ddl_declares_no_columns_missing_from_orm(self):
        for qualified, table in ControlBase.metadata.tables.items():
            block = _ddl_block(qualified.split(".", 1)[1])
            body = block.split("(", 1)[1]
            declared = {
                match.group(1)
                for match in re.finditer(
                    r"^\s{4}(\w+) (?:UUID|INTEGER|SMALLINT|TEXT|CHAR|DATE|"
                    r"TIMESTAMPTZ|DOUBLE)",
                    body,
                    re.MULTILINE,
                )
            }
            orm_columns = {column.name for column in table.columns}
            assert declared == orm_columns, (
                f"{qualified}: DDL columns {sorted(declared)} != ORM "
                f"{sorted(orm_columns)}"
            )

    def test_no_jsonb_anywhere_in_any_pair(self):
        assert "jsonb" not in _code_lines(ALL_UP).lower()
        assert "jsonb" not in _code_lines(ALL_DOWN).lower()

    def test_immutability_triggers_cover_all_control_tables(self):
        for qualified in ControlBase.metadata.tables:
            table_name = qualified.split(".", 1)[1]
            assert re.search(
                rf"BEFORE UPDATE OR DELETE ON scheduler\.{table_name}\b",
                ALL_UP,
            ), f"{table_name} lacks an immutability trigger"
