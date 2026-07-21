import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator

from schemas.machine_execution import ExecutionReceipt


def _root():
    for parent in Path(__file__).resolve().parents:
        root = parent / "contracts/machine-execution/v1"
        if root.is_dir():
            return root
    raise AssertionError("machine execution contract not found")


def test_execution_receipt_example_matches_json_schema_and_python_runtime_model():
    root = _root()
    schema = json.loads((root / "execution-receipt.schema.json").read_text())
    example = json.loads((root / "execution-receipt.example.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
    assert ExecutionReceipt.model_validate(example).model_dump(mode="json") == example


def test_machine_execution_manifest_pins_the_complete_contract_set():
    root = _root()
    manifest = json.loads((root / "manifest.json").read_text())
    records = []
    for entry in manifest["schemas"] + manifest["fixtures"]:
        digest = hashlib.sha256(
            (root / entry["relative_path"]).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        assert digest == entry["sha256"]
        record = {"relative_path": entry["relative_path"], "sha256": digest}
        if "schema" in entry:
            record.update(
                schema=entry["schema"], expected_valid=entry["expected_valid"]
            )
        records.append(record)
    canonical_records = sorted(
        json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records
    )
    content = "munbon:machine-execution-contract-set:v1\n" + "".join(
        line + "\n" for line in canonical_records
    )
    assert (
        hashlib.sha256(content.encode()).hexdigest() == manifest["contract_set_sha256"]
    )


def test_success_requires_matching_fresh_readback_in_the_runtime_model():
    example = json.loads((_root() / "execution-receipt.example.json").read_text())
    with pytest.raises(ValidationError, match="matching fresh readback"):
        ExecutionReceipt.model_validate(example | {"readback_quality": "offline"})
