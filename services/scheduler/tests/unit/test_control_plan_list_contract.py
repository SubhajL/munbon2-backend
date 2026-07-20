"""Scheduler side of the shared v1 control-plan list-page contract (PR 4.4a-3).

The BFF validates the SAME fixture against its own mirror; if either side's model
drifts from `contracts/control-plans/v1/`, that side's test fails. This test also
pins the three descriptions of the summary shape to each other (the scheduler
model, the JSON Schema, and the fixture) so a field added on only one of them is
caught.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.control_plan import (
    PROJECTION_SCHEMA_VERSION,
    ControlPlanListPage,
    ControlPlanSummaryOut,
)

_CONTRACT_DIR = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "control-plans"
    / "v1"
)
_FIXTURE = _CONTRACT_DIR / "control-plan-list-page.example.json"
_SCHEMA = _CONTRACT_DIR / "control-plan-list-page.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_scheduler_runtime_rejects_the_retired_v1_list_fixture():
    fixture = _load(_FIXTURE)
    assert fixture["projection_schema_version"] == 1
    with pytest.raises(ValidationError):
        ControlPlanListPage.model_validate(fixture)


def test_summary_model_schema_and_fixture_agree_on_the_exact_field_set():
    schema = _load(_SCHEMA)
    schema_fields = set(
        schema["$defs"]["control_plan_summary"]["properties"]
    )
    model_fields = set(ControlPlanSummaryOut.model_fields)
    fixture_fields = set(_load(_FIXTURE)["items"][0])
    assert schema_fields == model_fields == fixture_fields


def test_contract_forbids_any_large_document_field():
    schema = _load(_SCHEMA)
    summary = schema["$defs"]["control_plan_summary"]
    assert summary["additionalProperties"] is False
    for forbidden in (
        "optimizer_result",
        "requirements",
        "events",
        "transitions",
        "ledger",
        "entries",
        "trajectory",
    ):
        assert forbidden not in summary["properties"]


def test_v1_contract_stays_immutable_after_runtime_moves_to_v2():
    schema = _load(_SCHEMA)
    assert schema["properties"]["projection_schema_version"]["const"] == 1
    assert PROJECTION_SCHEMA_VERSION == 2


def test_list_page_rejects_unknown_projection_version():
    # projection_schema_version is pinned to the current version (Literal), so a
    # future/upstream v2 shape fails closed here (and the BFF mirror 502s) rather
    # than round-tripping an unknown-shape page silently.
    page = _load(_FIXTURE)
    page["projection_schema_version"] = PROJECTION_SCHEMA_VERSION + 1
    with pytest.raises(ValidationError):
        ControlPlanListPage.model_validate(page)
