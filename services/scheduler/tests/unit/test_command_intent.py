"""Per-event CommandIntent compilation (PR 4.3c-1).

One 6.0 CommandIntent per gate_plan_event, binding the device/level/capability_hash
from the 6.1a snapshot (exact membership) and the v2 lineage from the record.
Content-addressed ids are keyed on the GLOBAL event_sequence (not the per-gate
gate_event_sequence) so a multi-gate plan never collides.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from core.command_intent import (
    NonActivatablePlanError,
    command_intent_content_hash,
    compile_command_intents,
)
from core.device_capabilities import empty_device_capability_snapshot
from schemas.machine_boundary import DeviceCapabilitySnapshot

_HEX = "a1" * 32  # a valid 64-hex sha256 placeholder
_PLAN = UUID("11111111-1111-1111-1111-111111111111")
_CAMPAIGN = UUID("22222222-2222-2222-2222-222222222222")
_REQ_RUN = UUID("33333333-3333-3333-3333-333333333333")
_T0 = datetime(2026, 7, 20, 6, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 7, 20, 8, 30, 0, tzinfo=timezone.utc)
_HORIZON_END = datetime(2026, 7, 26, 6, 0, 0, tzinfo=timezone.utc)


def _snapshot() -> DeviceCapabilitySnapshot:
    data = {
        "schema_version": 1,
        "capability_release_id": "cap-x",
        "capabilities": {
            "M(0,0;1,0)": {
                "device_id": "rtu-a",
                "adapter_gate_id": "ch1",
                "targets": [
                    {"target_position_m": 0.45, "target_level": 3},
                    {"target_position_m": 0, "target_level": 0},
                ],
            },
            "M(1,1;2,2)": {
                "device_id": "rtu-b",
                "adapter_gate_id": "ch2",
                "targets": [{"target_position_m": 0.45, "target_level": 3}],
            },
        },
    }
    from core.canonical_json import canonicalize, sha256_hex

    data["capability_hash"] = sha256_hex(
        "munbon:device-capability-snapshot:v1\n" + canonicalize(data)
    )
    return DeviceCapabilitySnapshot(**data)


def _event(event_sequence, gate_id, event_kind, planned_at, position, gate_seq):
    return SimpleNamespace(
        event_sequence=event_sequence,
        gate_id=gate_id,
        event_kind=event_kind,
        planned_at=planned_at,
        target_position_m=position,
        gate_event_sequence=gate_seq,
    )


def _record(events, *, identity_version=2):
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
        prediction_identity_version=identity_version,
        engine_descriptor_content_hash=_HEX,
        artifact_sha256=_HEX,
        horizon_end=_HORIZON_END,
        events=events,
    )


def _compile(record):
    return compile_command_intents(
        record,
        _snapshot(),
        activation_sequence=4,
        request_id="req-123",
        requirement_set_sha256=_HEX,
    )


def test_one_intent_per_event_in_event_sequence_order():
    events = [
        _event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1),
        _event(2, "M(0,0;1,0)", "close", _T1, 0, 2),
    ]
    intents = _compile(_record(events))
    assert [i.event_sequence for i in intents] == [1, 2]
    assert intents[0].event_kind == "open" and intents[0].target_position_m == 0.45
    assert intents[1].event_kind == "close" and intents[1].target_position_m == 0
    assert intents[0].target_level == 3 and intents[1].target_level == 0
    assert intents[0].device_id == "rtu-a" and intents[0].adapter_gate_id == "ch1"
    assert all(i.mode == "shadow" for i in intents)


def test_ids_are_keyed_on_global_event_sequence_not_per_gate_counter():
    # Two gates, each with gate_event_sequence 1 — a per-gate key would collide.
    events = [
        _event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1),
        _event(2, "M(1,1;2,2)", "open", _T1, 0.45, 1),
    ]
    intents = _compile(_record(events))
    assert intents[0].intent_id != intents[1].intent_id
    assert intents[0].idempotency_key != intents[1].idempotency_key
    assert intents[0].idempotency_key.endswith(".1")
    assert intents[1].idempotency_key.endswith(".2")


def test_ids_are_deterministic_for_replay():
    events = [_event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1)]
    a = _compile(_record(events))[0]
    b = _compile(_record(events))[0]
    assert a.intent_id == b.intent_id
    assert a.correlation_id == b.correlation_id
    assert command_intent_content_hash(a) == command_intent_content_hash(b)


def test_all_intents_of_one_activation_share_a_correlation_id():
    events = [
        _event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1),
        _event(2, "M(0,0;1,0)", "close", _T1, 0, 2),
    ]
    intents = _compile(_record(events))
    assert intents[0].correlation_id == intents[1].correlation_id


def test_lineage_is_the_v2_provenance_and_timestamps_end_in_z():
    events = [_event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1)]
    intent = _compile(_record(events))[0]
    assert intent.lineage.campaign_id == str(_CAMPAIGN)
    assert intent.lineage.prediction_identity_version == 2
    assert intent.lineage.artifact_sha256 == _HEX
    assert intent.not_before == "2026-07-20T06:00:00Z"
    assert intent.deadline == "2026-07-26T06:00:00Z"


def test_content_hash_is_a_stable_independent_oracle():
    events = [_event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1)]
    intent = _compile(_record(events))[0]
    import hashlib

    from core.canonical_json import canonicalize

    expected = hashlib.sha256(
        canonicalize(intent.model_dump()).encode("utf-8")
    ).hexdigest()
    assert command_intent_content_hash(intent) == expected


def test_non_v2_plan_is_not_activatable():
    events = [_event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1)]
    with pytest.raises(NonActivatablePlanError):
        _compile(_record(events, identity_version=None))


def test_a_lineage_field_violating_the_contract_fails_closed_not_500():
    # A stored model_release_id with a space violates the ReleaseId pattern; the
    # pydantic ValidationError must be caught as NonActivatablePlanError (409), not
    # leak as an opaque 500.
    events = [_event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1)]
    record = _record(events)
    record.model_release_id = "not a valid id"
    with pytest.raises(NonActivatablePlanError):
        _compile(record)


def test_a_non_member_position_fails_closed():
    from core.device_capabilities import CapabilityMembershipError

    events = [_event(1, "M(0,0;1,0)", "open", _T0, 0.5, 1)]  # 0.5 is not a target
    with pytest.raises(CapabilityMembershipError):
        _compile(_record(events))


def test_empty_snapshot_makes_every_gate_a_non_member():
    from core.device_capabilities import CapabilityMembershipError

    events = [_event(1, "M(0,0;1,0)", "open", _T0, 0.45, 1)]
    with pytest.raises(CapabilityMembershipError):
        compile_command_intents(
            _record(events),
            empty_device_capability_snapshot(),
            activation_sequence=4,
            request_id="req-123",
            requirement_set_sha256=_HEX,
        )
