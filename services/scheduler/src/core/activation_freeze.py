"""Activation freeze (PR 4.3c-1) — the recomputable proof of a shadow activation.

Mirrors the 4.3b approval freeze (``core.control_plan_lifecycle``): a v2 document
wraps a recomputable ``activation_freeze`` beside its non-recomputable
``authorization_evidence``. The freeze pins the plan + capability identity and the
ordered ``intent_content_hash`` list, and records ``machine_authority_granted=true``
(this is the transition where authority is actually granted, unlike the approval
freeze which pins it ``false``). ``verify_activation_freeze`` rebuilds the freeze
from the immutable rows + the configured snapshot and requires exact equality, so a
drifted snapshot or a tampered document fails closed.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from core.canonical_json import canonicalize, sha256_hex
from core.command_intent import command_intent_content_hash, compile_command_intents

ACTIVATION_FREEZE_SCHEMA_VERSION = 1
ACTIVATION_DOCUMENT_SCHEMA_VERSION = 2


class ActivationFreezeMismatchError(Exception):
    """A frozen activation document no longer matches the immutable plan."""


def _intent_set_sha256(hashes: Sequence[str]) -> str:
    # Order-independent set hash over the per-intent content hashes.
    return sha256_hex(canonicalize(sorted(hashes)))


def build_activation_freeze(
    record: Any,
    *,
    snapshot: Any,
    intents: Sequence[Any],
    requirement_set_sha256: str,
    approval_transition_sequence: int,
) -> dict:
    hashes = [command_intent_content_hash(intent) for intent in intents]
    return {
        "schema_version": ACTIVATION_FREEZE_SCHEMA_VERSION,
        "activation_mode": "shadow",
        "machine_authority_granted": True,
        "plan": {
            "plan_id": str(record.plan_id),
            "plan_version": record.plan_version,
            "campaign_id": str(record.campaign_id),
            "draft_content_hash": record.draft_content_hash,
        },
        "capability": {
            "capability_release_id": snapshot.capability_release_id,
            "capability_hash": snapshot.capability_hash,
        },
        "requirements": {"requirement_set_sha256": requirement_set_sha256},
        "approval": {"approval_transition_sequence": approval_transition_sequence},
        "intents": {
            "count": len(hashes),
            "intent_content_hashes": hashes,
            "intent_set_sha256": _intent_set_sha256(hashes),
        },
    }


def build_activation_document(
    activation_freeze: Mapping[str, Any],
    authorization_evidence: Mapping[str, Any],
) -> dict:
    """Wrap the recomputable freeze and the non-recomputable evidence in a v2 doc.

    Evidence lives in its OWN key (never inside the freeze) so verification can
    recompute the freeze from immutable rows while ignoring the evidence.
    """
    return {
        "schema_version": ACTIVATION_DOCUMENT_SCHEMA_VERSION,
        "activation_freeze": dict(activation_freeze),
        "authorization_evidence": dict(authorization_evidence),
    }


def activation_document_text(document: Mapping[str, Any]) -> str:
    return canonicalize(document)


def verify_activation_freeze(
    document_text: str,
    record: Any,
    snapshot: Any,
    *,
    requirement_set_sha256: str,
    approval_transition_sequence: int,
    activation_sequence: int,
    request_id: str,
) -> None:
    """Recompute the freeze from immutable rows + the snapshot; require equality."""
    try:
        stored = json.loads(document_text)
    except ValueError as error:
        raise ActivationFreezeMismatchError(
            f"activation document is not valid JSON: {error}"
        ) from error
    stored_freeze = (
        stored["activation_freeze"]
        if isinstance(stored, Mapping) and "activation_freeze" in stored
        else stored
    )
    intents = compile_command_intents(
        record,
        snapshot,
        activation_sequence=activation_sequence,
        request_id=request_id,
        requirement_set_sha256=requirement_set_sha256,
    )
    expected = build_activation_freeze(
        record,
        snapshot=snapshot,
        intents=intents,
        requirement_set_sha256=requirement_set_sha256,
        approval_transition_sequence=approval_transition_sequence,
    )
    if canonicalize(stored_freeze) != canonicalize(expected):
        raise ActivationFreezeMismatchError(
            "frozen activation no longer matches the immutable plan + capabilities"
        )
