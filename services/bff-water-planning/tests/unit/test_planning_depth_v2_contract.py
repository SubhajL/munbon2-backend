import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from schemas.planning_depth import PlanningDepthSubmissionRequest
from schemas.planning_depth_v2 import (
    PlanningDepthActiveSubmissionV2,
    PlanningDepthSubmissionReceiptV2,
    PlanningDepthSubmissionRequestV2,
)
from services.planning_depth_submission import canonicalize_planning_depth_request

REPO_ROOT = Path(__file__).resolve().parents[4]
ROOT = REPO_ROOT / "contracts" / "planning-depth-submissions" / "v2"
V1_ROOT = REPO_ROOT / "contracts" / "planning-depth-submissions" / "v1"
MODELS = {
    "submission-request.schema.json": PlanningDepthSubmissionRequestV2,
    "submission-receipt.schema.json": PlanningDepthSubmissionReceiptV2,
    "active-submission.schema.json": PlanningDepthActiveSubmissionV2,
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


def test_v2_manifest_pins_complete_contract_set():
    manifest = _load(ROOT / "manifest.json")

    assert (
        manifest["contract_family"],
        manifest["contract_version"],
        {entry["relative_path"] for entry in manifest["schemas"]},
    ) == ("planning-depth-submissions", 2, set(MODELS))
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


def test_v2_schemas_models_and_serialized_outputs_agree_on_every_fixture():
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


def test_v2_root_model_fields_match_published_schema_properties():
    for schema_name, model in MODELS.items():
        schema = _load(ROOT / schema_name)
        assert set(model.model_fields) == set(schema["properties"])
        assert set(model.model_fields) == set(schema["required"])


def test_v1_contract_and_canonical_hash_remain_unchanged():
    manifest = _load(V1_ROOT / "manifest.json")
    request = PlanningDepthSubmissionRequest.model_validate(
        _load(V1_ROOT / "submission-request.decimals.example.json")
    )

    assert manifest["contract_set_sha256"] == (
        "f05abc57d16c92b61edf2bb2cdc5e39b33acf22e264b7a59d3670617dbba9d2f"
    )
    assert canonicalize_planning_depth_request(request).sha256 == (
        "77bf9bbe610663575f310baf52e8c96b4a2c9f551b36055198b9487ea8253077"
    )
