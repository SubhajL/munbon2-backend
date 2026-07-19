"""Activation freeze — the recomputable proof of what an activation granted (4.3c-1).

Mirrors the 4.3b approval freeze: a v2 document wraps a recomputable
``activation_freeze`` (plan + capability identity + the ordered intent content
hashes, with ``machine_authority_granted=true``) beside its non-recomputable
``authorization_evidence``. Verification rebuilds the freeze from the immutable
rows + the configured snapshot and requires exact equality.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from core.activation_freeze import (
    ActivationFreezeMismatchError,
    build_activation_document,
    build_activation_freeze,
    activation_document_text,
    verify_activation_freeze,
)
from core.command_intent import compile_command_intents
from schemas.machine_boundary import DeviceCapabilitySnapshot

_HEX = "a1" * 32
_PLAN = UUID("11111111-1111-1111-1111-111111111111")
_CAMPAIGN = UUID("22222222-2222-2222-2222-222222222222")
_REQ_RUN = UUID("33333333-3333-3333-3333-333333333333")
_T0 = datetime(2026, 7, 20, 6, 0, 0, tzinfo=timezone.utc)
_HORIZON_END = datetime(2026, 7, 26, 6, 0, 0, tzinfo=timezone.utc)


def _snapshot() -> DeviceCapabilitySnapshot:
    data = {
        "schema_version": 1,
        "capability_release_id": "cap-x",
        "capabilities": {
            "M(0,0;1,0)": {
                "device_id": "rtu-a",
                "adapter_gate_id": "ch1",
                "targets": [{"target_position_m": 0.45, "target_level": 3}],
            }
        },
    }
    from core.canonical_json import canonicalize, sha256_hex

    data["capability_hash"] = sha256_hex(
        "munbon:device-capability-snapshot:v1\n" + canonicalize(data)
    )
    return DeviceCapabilitySnapshot(**data)


def _record():
    event = SimpleNamespace(
        event_sequence=1,
        gate_id="M(0,0;1,0)",
        event_kind="open",
        planned_at=_T0,
        target_position_m=0.45,
        gate_event_sequence=1,
    )
    return SimpleNamespace(
        plan_id=_PLAN,
        plan_version=2,
        campaign_id=_CAMPAIGN,
        input_content_hash=_HEX,
        draft_content_hash=_HEX,
        requirement_run_id=_REQ_RUN,
        requirement_version=1,
        model_snapshot_id=_HEX,
        model_release_id="release-v1",
        model_release_content_hash=_HEX,
        prediction_run_id=_HEX,
        prediction_identity_version=2,
        engine_descriptor_content_hash=_HEX,
        artifact_sha256=_HEX,
        horizon_end=_HORIZON_END,
        events=[event],
    )


def _intents(record, snapshot):
    return compile_command_intents(
        record,
        snapshot,
        activation_sequence=4,
        request_id="req-1",
        requirement_set_sha256=_HEX,
    )


def _freeze(record, snapshot):
    return build_activation_freeze(
        record,
        snapshot=snapshot,
        intents=_intents(record, snapshot),
        requirement_set_sha256=_HEX,
        approval_transition_sequence=3,
    )


def test_freeze_grants_machine_authority_and_pins_capability_and_intents():
    freeze = _freeze(_record(), _snapshot())
    assert freeze["machine_authority_granted"] is True
    assert freeze["activation_mode"] == "shadow"
    assert freeze["capability"]["capability_release_id"] == "cap-x"
    assert freeze["intents"]["count"] == 1
    assert len(freeze["intents"]["intent_content_hashes"]) == 1


def test_freeze_is_deterministic():
    assert _freeze(_record(), _snapshot()) == _freeze(_record(), _snapshot())


def test_document_keeps_evidence_separate_from_the_freeze():
    freeze = _freeze(_record(), _snapshot())
    doc = build_activation_document(freeze, {"claim_policy_mode": "strict"})
    assert doc["schema_version"] == 2
    assert doc["activation_freeze"] == freeze
    assert doc["authorization_evidence"] == {"claim_policy_mode": "strict"}


def test_verify_recomputes_from_rows_and_accepts_a_matching_document():
    record, snapshot = _record(), _snapshot()
    doc = build_activation_document(_freeze(record, snapshot), {})
    verify_activation_freeze(
        activation_document_text(doc),
        record,
        snapshot,
        requirement_set_sha256=_HEX,
        approval_transition_sequence=3,
        activation_sequence=4,
        request_id="req-1",
    )


def test_verify_rejects_a_tampered_capability_hash():
    record, snapshot = _record(), _snapshot()
    freeze = _freeze(record, snapshot)
    freeze["capability"]["capability_hash"] = "0" * 64
    doc = build_activation_document(freeze, {})
    with pytest.raises(ActivationFreezeMismatchError):
        verify_activation_freeze(
            activation_document_text(doc),
            record,
            snapshot,
            requirement_set_sha256=_HEX,
            approval_transition_sequence=3,
            activation_sequence=4,
            request_id="req-1",
        )
