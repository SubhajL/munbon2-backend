import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from schemas.planning_depth_roster import PlanningDepthRosterProjection

ROOT = (
    Path(__file__).resolve().parents[4] / "contracts" / "planning-depth-roster" / "v1"
)


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def test_manifest_pins_the_complete_planning_depth_roster_contract_set():
    manifest = _load(ROOT / "manifest.json")

    assert manifest["contract_family"] == "planning-depth-roster"
    assert manifest["contract_version"] == 1
    assert {entry["relative_path"] for entry in manifest["schemas"]} == {
        "roster.schema.json"
    }
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


def test_schema_model_and_serialized_output_agree_on_every_fixture():
    manifest = _load(ROOT / "manifest.json")
    schema = _load(ROOT / "roster.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    assert len(manifest["fixtures"]) == 7
    for fixture in manifest["fixtures"]:
        document = _load(ROOT / fixture["relative_path"])
        assert validator.is_valid(document) is fixture["expected_schema_valid"]
        try:
            validated = PlanningDepthRosterProjection.model_validate(document)
            model_valid = True
        except ValidationError:
            model_valid = False
        assert model_valid is fixture["expected_model_valid"]
        if model_valid:
            assert validator.is_valid(validated.model_dump(mode="json"))


def test_root_model_fields_match_published_schema_properties():
    schema = _load(ROOT / "roster.schema.json")

    assert set(PlanningDepthRosterProjection.model_fields) == set(schema["properties"])
    assert set(PlanningDepthRosterProjection.model_fields) == set(schema["required"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document["sections"].__setitem__(
            -1, copy.deepcopy(document["sections"][0])
        ),
        lambda document: document["sections"][0].update(
            {"section_id": "01-02-01-03", "zone_id": "01-02"}
        ),
        lambda document: document["sections"].__setitem__(
            slice(0, 2), list(reversed(document["sections"][:2]))
        ),
        lambda document: (
            document["sections"][14].update(
                {"area_rai": document["sections"][14]["area_rai"] - 100}
            ),
            document["sections"][15].update(
                {"area_rai": document["sections"][15]["area_rai"] + 100}
            ),
        ),
    ],
)
def test_schema_and_model_reject_membership_or_area_authority_drift(mutate):
    document = _load(ROOT / "roster.active-v5.example.json")
    mutate(document)
    validator = Draft202012Validator(_load(ROOT / "roster.schema.json"))

    assert validator.is_valid(document) is False
    with pytest.raises(ValidationError):
        PlanningDepthRosterProjection.model_validate(document)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document["sections"].pop(),
        lambda document: document["sections"].__setitem__(
            -1, copy.deepcopy(document["sections"][0])
        ),
        lambda document: document["sections"][0].update(
            {"section_id": "01-02-01-03", "zone_id": "01-02"}
        ),
        lambda document: document["sections"][0].update({"area_rai": 0}),
        lambda document: document.update({"total_area_rai": 45203}),
        lambda document: document["sections"].__setitem__(
            slice(0, 2), list(reversed(document["sections"][:2]))
        ),
    ],
)
def test_roster_projection_rejects_incomplete_or_drifted_authority(mutate):
    document = _load(ROOT / "roster.active-v5.example.json")
    mutate(document)

    with pytest.raises(ValidationError):
        PlanningDepthRosterProjection.model_validate(document)
