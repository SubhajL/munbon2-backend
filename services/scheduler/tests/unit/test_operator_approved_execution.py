import json
from pathlib import Path

import pytest

from core.operator_approved_execution import (
    ExecutionPromotionError,
    promote_command_intent,
)
from schemas.machine_boundary import CommandIntent


def _intent():
    for parent in Path(__file__).resolve().parents:
        fixture = (
            parent
            / "contracts/machine-boundary/v1/fixtures/valid/command-intent.shadow.valid.json"
        )
        if fixture.is_file():
            return CommandIntent.model_validate(json.loads(fixture.read_text()))
    raise AssertionError("command intent fixture not found")


def test_promotion_changes_only_mode_and_binds_original_and_execution_hashes():
    original = _intent()
    promotion = promote_command_intent(original)
    assert (
        original.model_dump() | {"mode": "operator_approved"}
        == promotion.intent.model_dump()
    )
    assert (
        promotion.original_intent_content_hash
        != promotion.execution_intent_content_hash
    )
    assert promotion.intent.mode == "operator_approved"


def test_promotion_refuses_an_intent_that_is_not_the_frozen_shadow_document():
    with pytest.raises(ExecutionPromotionError, match="shadow"):
        promote_command_intent(
            _intent().model_copy(update={"mode": "operator_approved"})
        )
