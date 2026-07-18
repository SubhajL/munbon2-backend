"""BFF side of the shared v1 control-plan list-page contract (PR 4.4a-3).

The scheduler validates the SAME fixture against its own ControlPlanListPage; if
either side drifts from `contracts/control-plans/v1/`, that side's test fails.
A shared fixture that BOTH strict models accept is the drift trip-wire.
"""

import json
from pathlib import Path

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


def test_bff_accepts_the_same_v1_list_fixture():
    page = ControlPlanListPageProjection.model_validate(_load(_FIXTURE))
    assert page.projection_schema_version == 1
    assert len(page.items) == 2
    assert page.items[0].approval_trust is True
    assert page.items[1].optimizer_status == "infeasible"
    assert page.items[1].prediction_run_id is None


def test_bff_mirror_schema_and_fixture_agree_on_the_exact_field_set():
    schema = _load(_SCHEMA)
    schema_fields = set(schema["$defs"]["control_plan_summary"]["properties"])
    model_fields = set(ControlPlanSummaryProjection.model_fields)
    fixture_fields = set(_load(_FIXTURE)["items"][0])
    assert schema_fields == model_fields == fixture_fields
