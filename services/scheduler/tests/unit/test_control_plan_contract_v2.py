"""Scheduler acceptance suite for the immutable control-plan v2 contract set."""

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from schemas.control_plan import (
    ControlPlanLedgerResponse,
    ControlPlanLifecycleHistoryResponse,
    ControlPlanListPage,
    ControlPlanPredictionCoverageResponse,
    DraftControlPlanResponse,
)

ROOT = Path(__file__).resolve().parents[4] / "contracts" / "control-plans" / "v2"
MODELS = {
    "control-plan-list-page.schema.json": ControlPlanListPage,
    "control-plan-detail.schema.json": DraftControlPlanResponse,
    "control-plan-prediction-coverage.schema.json": ControlPlanPredictionCoverageResponse,
    "control-plan-ledger.schema.json": ControlPlanLedgerResponse,
    "control-plan-lifecycle-history.schema.json": ControlPlanLifecycleHistoryResponse,
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _contract_set_sha256(manifest: dict) -> str:
    records = []
    for entry in manifest["schemas"]:
        records.append(
            {
                "relative_path": entry["relative_path"],
                "sha256": _sha256(ROOT / entry["relative_path"]),
            }
        )
    for entry in manifest["fixtures"]:
        records.append(
            {
                "relative_path": entry["relative_path"],
                "schema": entry["schema"],
                "expected_valid": entry["expected_valid"],
                "sha256": _sha256(ROOT / entry["relative_path"]),
            }
        )
    encoded = json.dumps(
        records, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_scheduler_control_plan_v2_manifest_pins_the_complete_contract_set():
    manifest = _load(ROOT / "manifest.json")
    assert manifest["contract_family"] == "control-plans"
    assert manifest["contract_version"] == 2
    assert {entry["relative_path"] for entry in manifest["schemas"]} == set(MODELS)
    for entry in manifest["schemas"] + manifest["fixtures"]:
        assert entry["sha256"] == _sha256(ROOT / entry["relative_path"])
    assert manifest["contract_set_sha256"] == _contract_set_sha256(manifest)


def test_scheduler_models_and_json_schemas_agree_on_every_v2_fixture():
    manifest = _load(ROOT / "manifest.json")
    schemas = {name: _load(ROOT / name) for name in MODELS}
    for fixture in manifest["fixtures"]:
        document = _load(ROOT / fixture["relative_path"])
        schema_errors = list(
            Draft202012Validator(schemas[fixture["schema"]]).iter_errors(document)
        )
        model = MODELS[fixture["schema"]]
        if fixture["expected_valid"]:
            assert schema_errors == []
            model.model_validate(document)
        else:
            assert schema_errors
            with pytest.raises(ValidationError):
                model.model_validate(document)
