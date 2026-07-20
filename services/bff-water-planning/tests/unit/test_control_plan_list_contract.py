"""BFF side of the shared v1 control-plan list-page contract (PR 4.4a-3).

The scheduler validates the SAME fixture against its own ControlPlanListPage; if
either side drifts from `contracts/control-plans/v1/`, that side's test fails.
A shared fixture that BOTH strict models accept is the drift trip-wire.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.control_plan import (
    ControlPlanListPageProjection,
    ControlPlanSummaryProjection,
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


def test_bff_runtime_rejects_the_retired_v1_list_fixture():
    fixture = _load(_FIXTURE)
    assert fixture["projection_schema_version"] == 1
    with pytest.raises(ValidationError):
        ControlPlanListPageProjection.model_validate(fixture)


def test_bff_mirror_schema_and_fixture_agree_on_the_exact_field_set():
    schema = _load(_SCHEMA)
    schema_fields = set(schema["$defs"]["control_plan_summary"]["properties"])
    model_fields = set(ControlPlanSummaryProjection.model_fields)
    fixture_fields = set(_load(_FIXTURE)["items"][0])
    assert schema_fields == model_fields == fixture_fields
