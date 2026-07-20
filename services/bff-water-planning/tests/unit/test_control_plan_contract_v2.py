"""BFF acceptance suite for the same immutable control-plan v2 contract set."""

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from schemas.control_plan import (
    ControlPlanLedgerProjection,
    ControlPlanLifecycleHistory,
    ControlPlanListPageProjection,
    ControlPlanPredictionCoverage,
    ControlPlanProjection,
)

ROOT = Path(__file__).resolve().parents[4] / "contracts" / "control-plans" / "v2"
MODELS = {
    "control-plan-list-page.schema.json": ControlPlanListPageProjection,
    "control-plan-detail.schema.json": ControlPlanProjection,
    "control-plan-prediction-coverage.schema.json": ControlPlanPredictionCoverage,
    "control-plan-ledger.schema.json": ControlPlanLedgerProjection,
    "control-plan-lifecycle-history.schema.json": ControlPlanLifecycleHistory,
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_bff_models_and_json_schemas_agree_on_every_v2_fixture():
    manifest = _load(ROOT / "manifest.json")
    for fixture in manifest["fixtures"]:
        document = _load(ROOT / fixture["relative_path"])
        model = MODELS[fixture["schema"]]
        if fixture["expected_valid"]:
            model.model_validate(document)
        else:
            try:
                model.model_validate(document)
            except ValidationError:
                continue
            raise AssertionError(
                f"BFF mirror accepted invalid fixture {fixture['relative_path']}"
            )


def test_bff_manifest_hashes_match_the_bytes_it_validates():
    manifest = _load(ROOT / "manifest.json")
    for entry in manifest["schemas"] + manifest["fixtures"]:
        assert entry["sha256"] == _sha256(ROOT / entry["relative_path"])
