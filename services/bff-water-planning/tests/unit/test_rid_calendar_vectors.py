"""Python conformance against the shared RID calendar contract bytes."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from core.rid_calendar import (
    CONTRACT_SET_SHA256,
    CropActivityState,
    crop_activity,
    irrigation_week,
    irrigation_week_span,
    irrigation_year,
)

ROOT = Path(__file__).resolve().parents[4] / "contracts" / "rid-calendar" / "v1"
SCHEMAS = {
    "crop-activity.schema.json",
    "irrigation-week.schema.json",
}
GROUPS = ("schemas", "fixtures", "documents")
REQUIRED_IRRIGATION_DATES = {
    "1900-11-01",
    "2024-02-29",
    "2024-10-31",
    "2024-11-01",
    "2025-10-31",
    "2025-11-01",
    "2401-10-31",
}
REQUIRED_CROP_NOTES = {
    "day before planting",
    "planting day",
    "expected harvest day",
    "day after expected harvest",
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


def _entries(manifest):
    return [entry for group in GROUPS for entry in manifest[group]]


def _contract_set_sha256(manifest):
    records = []
    for group in GROUPS:
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


def _manifest():
    return _load(ROOT / "manifest.json")


def _vectors(name, schema_name):
    document = _load(ROOT / name)
    schema = _load(ROOT / schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    return document["vectors"]


def test_manifest_pins_every_file_in_the_rid_calendar_contract_set():
    manifest = _manifest()

    assert manifest["contract_family"] == "rid-calendar"
    assert manifest["contract_version"] == 1
    assert {entry["relative_path"] for entry in manifest["schemas"]} == SCHEMAS

    listed = {entry["relative_path"] for entry in _entries(manifest)}
    on_disk = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    assert listed == on_disk
    for entry in _entries(manifest):
        assert _sha256(ROOT / entry["relative_path"]) == entry["sha256"]
    assert _contract_set_sha256(manifest) == manifest["contract_set_sha256"]


def test_implementation_pins_the_contract_set_hash_it_was_written_against():
    assert CONTRACT_SET_SHA256 == _manifest()["contract_set_sha256"]


def test_contract_retains_named_boundary_witnesses():
    irrigation_vectors = _vectors(
        "irrigation-week.vectors.json",
        "irrigation-week.schema.json",
    )
    crop_vectors = _vectors(
        "crop-activity.vectors.json",
        "crop-activity.schema.json",
    )

    assert REQUIRED_IRRIGATION_DATES <= {
        vector["date"] for vector in irrigation_vectors
    }
    assert REQUIRED_CROP_NOTES <= {vector["note"] for vector in crop_vectors}


@pytest.mark.parametrize(
    "state, crop_week",
    [
        ("active", None),
        ("not_planted", 1),
        ("harvested", 1),
    ],
)
def test_crop_activity_schema_rejects_inconsistent_state_and_week(
    state,
    crop_week,
):
    document = _load(ROOT / "crop-activity.vectors.json")
    document["vectors"][0]["state"] = state
    document["vectors"][0]["crop_week"] = crop_week
    schema = _load(ROOT / "crop-activity.schema.json")

    with pytest.raises(ValidationError):
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(document)


def test_python_matches_every_irrigation_week_vector():
    vectors = _vectors(
        "irrigation-week.vectors.json",
        "irrigation-week.schema.json",
    )
    for vector in vectors:
        day = date.fromisoformat(vector["date"])
        expected_year = vector["irrigation_year"]
        identity = irrigation_week(day)
        span = irrigation_week_span(identity)

        assert (
            identity.irrigation_year.ce,
            identity.irrigation_year.be,
            identity.irrigation_week,
            identity.key,
        ) == (
            expected_year["ce"],
            expected_year["be"],
            vector["irrigation_week"],
            vector["week_key"],
        )
        assert irrigation_year(day) == identity.irrigation_year
        assert (span.start.isoformat(), span.end.isoformat()) == (
            vector["week_start"],
            vector["week_end"],
        )
        assert (span.end - span.start).days + 1 == vector["week_length_days"]


def test_python_matches_every_crop_activity_vector():
    vectors = _vectors(
        "crop-activity.vectors.json",
        "crop-activity.schema.json",
    )
    for vector in vectors:
        observed = crop_activity(
            date.fromisoformat(vector["planting_date"]),
            date.fromisoformat(vector["expected_harvest_date"]),
            date.fromisoformat(vector["on"]),
        )
        assert (observed.state, observed.crop_week) == (
            CropActivityState(vector["state"]),
            vector["crop_week"],
        )
