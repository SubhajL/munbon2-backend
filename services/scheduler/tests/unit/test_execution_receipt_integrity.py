import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from core.canonical_json import canonicalize
from repositories.control_plan_repository import (
    ExecutionReceiptCorruptError,
    text_sha256,
    verify_stored_execution_receipt,
)


def _example():
    for parent in Path(__file__).resolve().parents:
        path = parent / "contracts/machine-execution/v1/execution-receipt.example.json"
        if path.is_file():
            return json.loads(path.read_text())
    raise AssertionError("execution receipt example missing")


def _row(**over):
    body = _example()
    text = json.dumps(body)
    values = dict(
        intent_id=UUID(body["intent_id"]),
        grant_id=UUID(body["grant_id"]),
        authority_not_after=datetime.fromisoformat(
            body["authority_not_after"].replace("Z", "+00:00")
        ),
        receipt_id=UUID(body["receipt_id"]),
        idempotency_key=body["idempotency_key"],
        original_intent_content_hash=body["original_intent_content_hash"],
        execution_intent_content_hash=body["execution_intent_content_hash"],
        capability_hash=body["capability_hash"],
        purpose=body["purpose"],
        status=body["status"],
        reason_code=body["reason_code"],
        target_level=body["target_level"],
        observed_level=body["observed_level"],
        readback_quality=body["readback_quality"],
        writes_document_text=canonicalize(body["writes"]),
        executed_at=datetime.fromisoformat(body["executed_at"].replace("Z", "+00:00")),
        receipt_document_text=text,
        receipt_content_sha256=text_sha256(text),
    )
    values.update(over)
    return SimpleNamespace(**values)


def test_execution_receipt_integrity_binds_document_hash_and_every_typed_replica():
    verify_stored_execution_receipt(_row())
    with pytest.raises(ExecutionReceiptCorruptError, match="typed replica"):
        verify_stored_execution_receipt(_row(status="readback_mismatch"))
    with pytest.raises(ExecutionReceiptCorruptError, match="hash"):
        verify_stored_execution_receipt(_row(receipt_content_sha256="f" * 64))
