"""Acceptance gate for the immutable control-commissioning v1 contract."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = (
    Path(__file__).resolve().parents[4] / "contracts" / "control-commissioning" / "v1"
)
SCHEMA = "commandability-approval.schema.json"
FIXTURES = {
    "fixtures/valid/commandability-approval.not-approved.valid.json": True,
    "fixtures/invalid/commandability-approval.approved-without-attestation.invalid.json": False,
    "fixtures/invalid/commandability-approval.extra-field.invalid.json": False,
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _contract_set_sha256(manifest: dict) -> str:
    records = [
        {
            "relative_path": SCHEMA,
            "sha256": _sha256(ROOT / SCHEMA),
        }
    ]
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


def test_control_commissioning_manifest_pins_the_complete_v1_contract_set():
    manifest = _load(ROOT / "manifest.json")

    assert {
        "family": manifest["contract_family"],
        "version": manifest["contract_version"],
        "schemas": manifest["schemas"],
        "fixtures": {
            entry["relative_path"]: entry["expected_valid"]
            for entry in manifest["fixtures"]
        },
    } == {
        "family": "control-commissioning",
        "version": 1,
        "schemas": [{"relative_path": SCHEMA, "sha256": _sha256(ROOT / SCHEMA)}],
        "fixtures": FIXTURES,
    }
    for entry in manifest["fixtures"]:
        assert entry["schema"] == SCHEMA
        assert entry["sha256"] == _sha256(ROOT / entry["relative_path"])
    assert manifest["contract_set_sha256"] == _contract_set_sha256(manifest)


def test_every_control_commissioning_fixture_has_the_declared_validity():
    schema = _load(ROOT / SCHEMA)
    validator = Draft202012Validator(schema)

    for relative_path, expected_valid in FIXTURES.items():
        errors = list(validator.iter_errors(_load(ROOT / relative_path)))
        assert (errors == []) is expected_valid


def test_committed_example_is_loudly_nonapproved_and_content_addressed():
    document = _load(
        ROOT / "fixtures/valid/commandability-approval.not-approved.valid.json"
    )
    payload = dict(document)
    declared_hash = payload.pop("content_hash")
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")

    assert {
        "state": document["approval_state"],
        "attestation": document["approval"],
        "reference": document["base_model_release"]["release_id"],
        "content_hash_matches": declared_hash == hashlib.sha256(encoded).hexdigest(),
    } == {
        "state": "not_approved",
        "attestation": None,
        "reference": "DO-NOT-DEPLOY-NOT-APPROVED",
        "content_hash_matches": True,
    }
