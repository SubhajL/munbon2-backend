import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from schemas.planning_depth import (
    EffectivePrincipalProjection,
    PlanningDepthActiveSubmission,
    PlanningDepthSubmissionReceipt,
    PlanningDepthSubmissionRequest,
)
from services.planning_depth_submission import canonicalize_planning_depth_request

ROOT = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "planning-depth-submissions"
    / "v1"
)
MODELS = {
    "effective-principal.schema.json": EffectivePrincipalProjection,
    "submission-request.schema.json": PlanningDepthSubmissionRequest,
    "submission-receipt.schema.json": PlanningDepthSubmissionReceipt,
    "active-submission.schema.json": PlanningDepthActiveSubmission,
}


def _load(path):
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(
            AssertionError(f"non-standard JSON constant {token!r}")
        ),
    )


def _sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _contract_set_sha256(manifest):
    records = []
    for group in ("schemas", "fixtures"):
        for entry in manifest[group]:
            record = {key: entry[key] for key in entry if key != "sha256"}
            record["sha256"] = _sha256(ROOT / entry["relative_path"])
            records.append(record)
    encoded = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_manifest_pins_the_complete_planning_depth_contract_set():
    manifest = _load(ROOT / "manifest.json")

    assert manifest["contract_family"] == "planning-depth-submissions"
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


def test_schemas_models_and_serialized_outputs_agree_on_every_fixture():
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
        assert validator.is_valid(document) is fixture["expected_schema_valid"]
        try:
            validated = MODELS[fixture["schema"]].model_validate(document)
            model_valid = True
        except ValidationError:
            model_valid = False
        assert model_valid is fixture["expected_model_valid"]
        if model_valid:
            assert validator.is_valid(validated.model_dump(mode="json"))
        expected_hash = fixture.get("canonical_request_sha256")
        if expected_hash is not None:
            assert (
                canonicalize_planning_depth_request(validated).sha256 == expected_hash
            )


def test_cross_language_vectors_pin_decimals_and_maximum_expansion():
    request = _load(ROOT / "submission-request.decimals.example.json")
    active = _load(ROOT / "active-submission.max-41.example.json")

    assert {level["planning_depth_mm"] for level in request["levels"]}.issuperset(
        {0, 0.1, 20.5}
    )
    assert len(active["levels"]) == 41
    assert [item["section_id"] for item in active["levels"]] == sorted(
        item["section_id"] for item in active["levels"]
    )


def test_root_model_fields_match_published_schema_properties():
    for schema_name, model in MODELS.items():
        schema = _load(ROOT / schema_name)
        assert set(model.model_fields) == set(schema["properties"])
        assert set(model.model_fields) == set(schema["required"])
