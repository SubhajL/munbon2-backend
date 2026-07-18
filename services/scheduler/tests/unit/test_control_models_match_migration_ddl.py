"""Drift lock: the ControlBase ORM must mirror the 0001 migration DDL."""

import re
from pathlib import Path

import models.control_plan  # noqa: F401  (registers control tables)
from models.control_base import ControlBase

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
UP_SQL = (MIGRATIONS_DIR / "0001_control_plan_drafts.up.sql").read_text()
DOWN_SQL = (MIGRATIONS_DIR / "0001_control_plan_drafts.down.sql").read_text()


def _ddl_block(table_name: str) -> str:
    pattern = re.compile(
        rf"CREATE TABLE scheduler\.{table_name} \((?s:.*?)\n\);",
    )
    match = pattern.search(UP_SQL)
    assert match, f"up.sql does not create scheduler.{table_name}"
    return match.group(0)


class TestMigrationPairShape:
    def test_pair_exists_and_is_nonempty(self):
        assert UP_SQL.strip() and DOWN_SQL.strip()

    def test_up_creates_every_orm_table_and_down_drops_it(self):
        for qualified in ControlBase.metadata.tables:
            table_name = qualified.split(".", 1)[1]
            assert f"CREATE TABLE scheduler.{table_name} (" in UP_SQL
            assert f"DROP TABLE scheduler.{table_name};" in DOWN_SQL

    def test_up_creates_no_extra_tables(self):
        created = set(re.findall(r"CREATE TABLE scheduler\.(\w+)", UP_SQL))
        orm_tables = {name.split(".", 1)[1] for name in ControlBase.metadata.tables}
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

    def test_no_jsonb_anywhere_in_the_pair(self):
        for sql in (UP_SQL, DOWN_SQL):
            code = "\n".join(
                line for line in sql.splitlines()
                if not line.lstrip().startswith("--")
            )
            assert "jsonb" not in code.lower()

    def test_immutability_triggers_cover_all_four_tables(self):
        for qualified in ControlBase.metadata.tables:
            table_name = qualified.split(".", 1)[1]
            assert re.search(
                rf"BEFORE UPDATE OR DELETE ON scheduler\.{table_name}\b",
                UP_SQL,
            ), f"{table_name} lacks an immutability trigger"
