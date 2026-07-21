"""Pure promotion of an immutable shadow intent into an execution request."""

from __future__ import annotations

from dataclasses import dataclass

from core.command_intent import command_intent_content_hash
from schemas.machine_boundary import CommandIntent


class ExecutionPromotionError(Exception):
    """The stored document is not eligible for deterministic promotion."""


@dataclass(frozen=True)
class PromotedCommandIntent:
    intent: CommandIntent
    original_intent_content_hash: str
    execution_intent_content_hash: str


def promote_command_intent(intent: CommandIntent) -> PromotedCommandIntent:
    """Change exactly ``mode`` from shadow to operator_approved and bind both hashes."""
    if intent.mode != "shadow":
        raise ExecutionPromotionError("only a frozen shadow intent can be promoted")
    promoted = intent.model_copy(update={"mode": "operator_approved"})
    before = intent.model_dump()
    after = promoted.model_dump()
    if before | {"mode": "operator_approved"} != after:
        raise ExecutionPromotionError("promotion changed fields other than mode")
    return PromotedCommandIntent(
        intent=promoted,
        original_intent_content_hash=command_intent_content_hash(intent),
        execution_intent_content_hash=command_intent_content_hash(promoted),
    )
