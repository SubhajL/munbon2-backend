"""Scheduler acceptance suite for the immutable control-plan evidence v1 contract."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from schemas.control_plan import (
    ControlPlanExecutionStateResponse,
    ControlPlanIntentTimelineResponse,
    ControlPlanReadbackObservationsResponse,
    HoldEventOut,
    IntentTimelineEntryOut,
    ReadbackObservationOut,
)

ROOT = (
    Path(__file__).resolve().parents[4] / "contracts" / "control-plan-evidence" / "v1"
)
LEGACY_ROOT = Path(__file__).resolve().parents[4] / "contracts" / "control-plans" / "v1"
MODELS = {
    "intent-timeline.schema.json": ControlPlanIntentTimelineResponse,
    "readback-observations.schema.json": ControlPlanReadbackObservationsResponse,
    "execution-state.schema.json": ControlPlanExecutionStateResponse,
}
NESTED_MODELS = {
    "intent-timeline.schema.json": {"intent": IntentTimelineEntryOut},
    "readback-observations.schema.json": {"observation": ReadbackObservationOut},
    "execution-state.schema.json": {"hold_event": HoldEventOut},
}


def _load(path: Path):
    def reject_constant(token: str):
        raise AssertionError(f"non-standard JSON constant {token!r} in {path}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_constant,
    )


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


def test_scheduler_manifest_pins_the_complete_evidence_contract_set():
    manifest = _load(ROOT / "manifest.json")
    assert manifest["contract_family"] == "control-plan-evidence"
    assert manifest["contract_version"] == 1
    assert {entry["relative_path"] for entry in manifest["schemas"]} == set(MODELS)
    listed = {
        entry["relative_path"] for entry in manifest["schemas"] + manifest["fixtures"]
    }
    on_disk = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.json")
        if path.name != "manifest.json"
    }
    assert listed == on_disk
    for entry in manifest["schemas"] + manifest["fixtures"]:
        assert entry["sha256"] == _sha256(ROOT / entry["relative_path"])
    assert manifest["contract_set_sha256"] == _contract_set_sha256(manifest)


def test_scheduler_models_and_json_schemas_agree_on_every_evidence_fixture():
    manifest = _load(ROOT / "manifest.json")
    schemas = {name: _load(ROOT / name) for name in MODELS}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    for fixture in manifest["fixtures"]:
        document = _load(ROOT / fixture["relative_path"])
        validator = Draft202012Validator(
            schemas[fixture["schema"]],
            format_checker=FormatChecker(),
        )
        schema_valid = validator.is_valid(document)
        try:
            validated = MODELS[fixture["schema"]].model_validate(document)
            model_valid = True
        except ValidationError:
            model_valid = False
        assert schema_valid is fixture["expected_valid"], fixture["relative_path"]
        assert model_valid is fixture["expected_valid"], fixture["relative_path"]
        if model_valid:
            assert validator.is_valid(validated.model_dump(mode="json"))


def test_scheduler_model_fields_match_every_evidence_schema_object():
    for schema_name, model in MODELS.items():
        schema = _load(ROOT / schema_name)
        assert set(model.model_fields) == set(schema["properties"])
        assert set(model.model_fields) == set(schema["required"])
        for definition_name, nested_model in NESTED_MODELS[schema_name].items():
            definition = schema["$defs"][definition_name]
            assert set(nested_model.model_fields) == set(definition["properties"])
            assert set(nested_model.model_fields) == set(definition["required"])


def test_evidence_examples_preserve_the_existing_runtime_fixture_bytes():
    for name in (
        "intent-timeline.example.json",
        "readback-observations.example.json",
        "execution-state.example.json",
    ):
        assert (ROOT / name).read_bytes() == (LEGACY_ROOT / name).read_bytes()
