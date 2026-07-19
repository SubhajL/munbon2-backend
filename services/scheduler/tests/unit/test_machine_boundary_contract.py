"""PR 6.0 — the Python half of the cross-language machine-boundary contract gate.

The two RUNTIME validators are pydantic (the scheduler, which will EMIT intents in
4.3c) and Ajv 2020 (SCADA, which will VALIDATE them in 6.2). Both use
engine-independent patterns (printable-ASCII ids, finite-bounded numbers,
mathematical-integer semantics, range-enforced UTC), so they agree on every input,
not just the fixtures. This suite adds jsonschema (Draft202012 + FormatChecker) as
a third structural check and cross-checks it against the pydantic mirror on the
shared manifest fixture vector. (Note: Python `re` treats `$` as "end or before a
final newline", so the jsonschema engine alone would accept a trailing-newline
value on variable-length string fields that both runtime validators reject — an
artifact of the test-only jsonschema engine, not of the contract or the runtime
validators; fixed-length fields are guarded by min/maxLength.)

Both this suite and the SCADA `machine-boundary-contract.spec.ts` read the IDENTICAL
bytes, derive their accept/reject vector SOLELY from `manifest.json`, and pin the
same `contract_set_sha256` (a canonical-JSON digest that binds each record's
relative_path, schema, expected_valid, and file sha256).
"""

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from schemas.machine_boundary import (
    MACHINE_BOUNDARY_CONTRACT_SET_SHA256,
    MACHINE_BOUNDARY_SCHEMA_VERSION,
    MODEL_BY_SCHEMA,
    CommandLineage,
    DeviceCapability,
    DeviceTargetCapability,
)

_SET_PREFIX = b"munbon:machine-boundary-contract-set:v1\n"


def _contracts_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "contracts" / "machine-boundary" / "v1"
        if (candidate / "manifest.json").is_file():
            return candidate
    raise AssertionError("contracts/machine-boundary/v1/manifest.json not found")


ROOT = _contracts_root()


def _load_json_strict(path: Path):
    def _reject(token: str):  # NaN / Infinity / -Infinity
        raise AssertionError(f"non-standard JSON constant {token!r} in {path}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject)


def _file_sha256_norm(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _manifest():
    return _load_json_strict(ROOT / "manifest.json")


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _recompute_contract_set(manifest) -> str:
    records = []
    for s in manifest["schemas"]:
        records.append(
            {
                "relative_path": s["relative_path"],
                "sha256": _file_sha256_norm(ROOT / s["relative_path"]),
            }
        )
    for f in manifest["fixtures"]:
        records.append(
            {
                "relative_path": f["relative_path"],
                "schema": f["schema"],
                "expected_valid": f["expected_valid"],
                "sha256": _file_sha256_norm(ROOT / f["relative_path"]),
            }
        )
    acc = bytearray(_SET_PREFIX)
    for line in sorted(_canon(r) for r in records):
        acc += (line + "\n").encode("utf-8")
    return hashlib.sha256(bytes(acc)).hexdigest()


def _validator_for(schema_name: str) -> Draft202012Validator:
    schema = _load_json_strict(ROOT / schema_name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _pydantic_valid(schema_name: str, doc) -> bool:
    try:
        MODEL_BY_SCHEMA[schema_name].model_validate(doc)
        return True
    except ValidationError:
        return False


def test_manifest_pins_machine_boundary_v1_content_set():
    manifest = _manifest()
    assert manifest["contract_version"] == 1
    assert manifest["contract_family"] == "machine-boundary"
    for entry in manifest["schemas"] + manifest["fixtures"]:
        assert entry["sha256"] == _file_sha256_norm(
            ROOT / entry["relative_path"]
        ), entry["relative_path"]
    recomputed = _recompute_contract_set(manifest)
    assert recomputed == manifest["contract_set_sha256"]
    assert recomputed == MACHINE_BOUNDARY_CONTRACT_SET_SHA256


def test_manifest_roster_matches_disk():
    listed = {
        e["relative_path"] for e in _manifest()["schemas"] + _manifest()["fixtures"]
    }
    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*.json")
        if p.relative_to(ROOT).as_posix() != "manifest.json"
    }
    assert on_disk == listed


@pytest.mark.parametrize(
    "fixture", _manifest()["fixtures"], ids=lambda f: f["relative_path"]
)
def test_jsonschema_fixture_matches_manifest_expectation(fixture):
    validator = _validator_for(fixture["schema"])
    doc = _load_json_strict(ROOT / fixture["relative_path"])
    assert validator.is_valid(doc) is fixture["expected_valid"]


@pytest.mark.parametrize(
    "fixture", _manifest()["fixtures"], ids=lambda f: f["relative_path"]
)
def test_pydantic_fixture_matches_manifest_expectation(fixture):
    doc = _load_json_strict(ROOT / fixture["relative_path"])
    assert _pydantic_valid(fixture["schema"], doc) is fixture["expected_valid"]


def _schema_props(schema_name: str):
    schema = _load_json_strict(ROOT / schema_name)
    return set(schema["properties"]), set(schema["required"])


def test_root_models_match_schema_property_and_required_sets():
    for schema_name, model in MODEL_BY_SCHEMA.items():
        props, required = _schema_props(schema_name)
        fields = set(model.model_fields)
        assert fields == props, schema_name
        assert fields == required, schema_name  # every field is required in v1


def test_nested_models_match_schema_defs():
    ci = _load_json_strict(ROOT / "command-intent.schema.json")
    lineage_def = ci["$defs"]["lineage"]
    assert set(CommandLineage.model_fields) == set(lineage_def["properties"])
    assert set(CommandLineage.model_fields) == set(lineage_def["required"])

    dcs = _load_json_strict(ROOT / "device-capability-snapshot.schema.json")
    cap_def = dcs["$defs"]["capability"]
    tgt_def = dcs["$defs"]["target"]
    assert set(DeviceCapability.model_fields) == set(cap_def["properties"])
    assert set(DeviceCapability.model_fields) == set(cap_def["required"])
    assert set(DeviceTargetCapability.model_fields) == set(tgt_def["properties"])
    assert set(DeviceTargetCapability.model_fields) == set(tgt_def["required"])


def test_schema_versions_and_ids_are_v1():
    assert MACHINE_BOUNDARY_SCHEMA_VERSION == 1
    for schema_name in MODEL_BY_SCHEMA:
        schema = _load_json_strict(ROOT / schema_name)
        assert schema["$id"].startswith(
            "https://munbon.internal/contracts/machine-boundary/v1/"
        )
        assert schema["properties"]["schema_version"]["const"] == 1
