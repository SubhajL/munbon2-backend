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


def _added_columns(table_name: str) -> set:
    """Columns introduced by a later additive `ALTER TABLE ... ADD COLUMN` — the
    ORM must mirror these too, even though they are not in the CREATE TABLE block."""
    added: set = set()
    for statement in re.findall(
        rf"ALTER TABLE scheduler\.{table_name}\b(?s:.*?);", ALL_UP
    ):
        added.update(re.findall(r"\bADD COLUMN (\w+)\b", statement))
    return added


def _declared_columns(qualified: str, table) -> set:
    """Every column the migrations declare for a table: CREATE-block columns plus
    additive ALTER ADD COLUMNs."""
    table_name = qualified.split(".", 1)[1]
    block = _ddl_block(table_name)
    body = block.split("(", 1)[1]
    from_create = {
        match.group(1)
        for match in re.finditer(
            r"^\s{4}(\w+) (?:UUID|INTEGER|SMALLINT|BIGINT|TEXT|CHAR|DATE|"
            r"TIMESTAMPTZ|DOUBLE|BOOLEAN)",
            body,
            re.MULTILINE,
        )
    }
    return from_create | _added_columns(table_name)


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
        orm_tables = {name.split(".", 1)[1] for name in ControlBase.metadata.tables}
        assert created == orm_tables

    def test_every_orm_column_appears_in_its_table_ddl(self):
        for qualified, table in ControlBase.metadata.tables.items():
            table_name = qualified.split(".", 1)[1]
            block = _ddl_block(table_name)
            added = _added_columns(table_name)
            for column in table.columns:
                in_create = re.search(
                    rf"^\s+{re.escape(column.name)} ", block, re.MULTILINE
                )
                assert in_create or column.name in added, (
                    f"{qualified}.{column.name} missing from up.sql "
                    "(neither CREATE TABLE nor ALTER ADD COLUMN)"
                )

    def test_ddl_declares_no_columns_missing_from_orm(self):
        for qualified, table in ControlBase.metadata.tables.items():
            declared = _declared_columns(qualified, table)
            orm_columns = {column.name for column in table.columns}
            assert declared == orm_columns, (
                f"{qualified}: DDL columns {sorted(declared)} != ORM "
                f"{sorted(orm_columns)}"
            )

    def test_no_jsonb_anywhere_in_any_pair(self):
        assert "jsonb" not in _code_lines(ALL_UP).lower()
        assert "jsonb" not in _code_lines(ALL_DOWN).lower()

    def test_immutability_triggers_cover_all_control_tables(self):
        # control_active_gate_authority is a MUTABLE materialized current-authority
        # index (PR 4.3c-1): rows are INSERTed on activation and DELETEd on exit, so
        # it deliberately carries NO immutability trigger. Every OTHER control table
        # is append-only and must.
        mutable_current_state = {"control_active_gate_authority"}
        for qualified in ControlBase.metadata.tables:
            table_name = qualified.split(".", 1)[1]
            if table_name in mutable_current_state:
                assert not re.search(
                    rf"BEFORE UPDATE OR DELETE ON scheduler\.{table_name}\b",
                    ALL_UP,
                ), f"{table_name} is the mutable mutex and must NOT be immutable"
                continue
            assert re.search(
                rf"BEFORE UPDATE OR DELETE ON scheduler\.{table_name}\b",
                ALL_UP,
            ), f"{table_name} lacks an immutability trigger"


def test_migration_0010_reason_vocab_matches_the_frozen_contract():
    """L6: the DB reason_code CHECK vocabulary must equal the Python ValidationRejectionReason
    Literal, so a future edit to one is caught by a test, not a runtime INSERT failure.
    """
    from typing import get_args

    from schemas.machine_boundary import ValidationRejectionReason

    contract = set(get_args(ValidationRejectionReason))
    sql = (MIGRATIONS_DIR / "0010_shadow_dispatch_receipts.up.sql").read_text()
    match = re.search(r"reason_code IN \(([^)]*)\)", sql, re.S)
    assert match, "0010 up.sql has no reason_code IN (...) vocabulary CHECK"
    vocab = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    assert vocab == contract, f"DB vocab {sorted(vocab)} != contract {sorted(contract)}"


def test_migration_0011_verdict_and_mode_vocab_match_the_constants():
    """L6/L3: the 0011 verdict + mode CHECK vocab must equal the Python constants so a drift is
    caught by a test, not a runtime INSERT failure."""
    from core.readback_reconciliation import (
        VERDICT_MISMATCH,
        VERDICT_OK,
        VERDICT_UNAVAILABLE,
    )
    from services.readback_reconciliation_service import MODE_ENFORCE, MODE_OBSERVE

    sql = (MIGRATIONS_DIR / "0011_gate_readback_observations.up.sql").read_text()
    verdict = re.search(r"verdict IN \(([^)]*)\)", sql)
    mode = re.search(r"reconciliation_mode IN \(([^)]*)\)", sql)
    assert verdict and mode
    assert set(re.findall(r"'([a-z_]+)'", verdict.group(1))) == {
        VERDICT_OK,
        VERDICT_MISMATCH,
        VERDICT_UNAVAILABLE,
    }
    assert set(re.findall(r"'([a-z_]+)'", mode.group(1))) == {
        MODE_OBSERVE,
        MODE_ENFORCE,
    }
