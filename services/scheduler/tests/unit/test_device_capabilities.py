"""Fail-closed device-capability snapshot loader + membership (PR 4.3c-1).

The scheduler consumes the exact artifact 6.1a serves (a full
device-capability-snapshot with its content hash). Loading is FAIL-CLOSED: an
unset path yields the empty dark default (zero machine-capable gates); an
unreadable / malformed / schema-violating / hash-mismatched file THROWS.
Membership is EXACT (continuous->discrete quantization is 6.1b) so a non-member
optimizer position can never be commanded.
"""

import json

import pytest

from core.device_capabilities import (
    CapabilityMembershipError,
    DeviceCapabilityConfigError,
    capability_member,
    empty_device_capability_snapshot,
    load_device_capability_snapshot,
)

_EMPTY_HASH = "6ec86898f64a3ff50038727c976a036db033685bce861c2ba160ea0a2d32798b"


def _valid_snapshot() -> dict:
    snapshot = {
        "schema_version": 1,
        "capability_release_id": "cap-2026-07-19",
        "capabilities": {
            "M(0,0;1,0)": {
                "device_id": "scada-rtu-07",
                "adapter_gate_id": "ch3",
                "targets": [
                    {"target_position_m": 0.45, "target_level": 3},
                    {"target_position_m": 0, "target_level": 0},
                ],
            }
        },
    }
    from core.canonical_json import canonicalize, sha256_hex

    snapshot["capability_hash"] = sha256_hex(
        "munbon:device-capability-snapshot:v1\n" + canonicalize(snapshot)
    )
    return snapshot


def _write(tmp_path, data) -> str:
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data), "utf-8")
    return str(path)


def test_empty_default_when_path_unset_has_zero_gates_and_the_pinned_hash():
    snap = load_device_capability_snapshot({})
    assert snap.capabilities == {}
    assert snap.capability_release_id == "__empty__"
    assert snap.capability_hash == _EMPTY_HASH


def test_blank_path_also_yields_the_empty_default():
    snap = load_device_capability_snapshot(
        {"SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": "   "}
    )
    assert snap.capabilities == {}


def test_empty_default_helper_matches_the_pinned_cross_language_hash():
    assert empty_device_capability_snapshot().capability_hash == _EMPTY_HASH


def test_loads_and_validates_a_snapshot(tmp_path):
    snap = load_device_capability_snapshot(
        {"SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": _write(tmp_path, _valid_snapshot())}
    )
    assert set(snap.capabilities) == {"M(0,0;1,0)"}
    assert snap.capabilities["M(0,0;1,0)"].device_id == "scada-rtu-07"


def test_throws_when_the_path_is_set_but_missing(tmp_path):
    with pytest.raises(DeviceCapabilityConfigError):
        load_device_capability_snapshot(
            {"SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": str(tmp_path / "nope.json")}
        )


def test_throws_on_a_non_utf8_file(tmp_path):
    # A binary/mis-encoded file raises UnicodeDecodeError (a ValueError, not OSError);
    # it must fail closed as a config error, not a raw traceback at startup.
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    with pytest.raises(DeviceCapabilityConfigError):
        load_device_capability_snapshot(
            {"SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": str(path)}
        )


def test_throws_on_malformed_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", "utf-8")
    with pytest.raises(DeviceCapabilityConfigError):
        load_device_capability_snapshot(
            {"SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": str(path)}
        )


def test_throws_on_a_schema_violation(tmp_path):
    bad = _valid_snapshot()
    bad["capabilities"]["M(0,0;1,0)"]["targets"][0]["target_level"] = 65536
    with pytest.raises(DeviceCapabilityConfigError):
        load_device_capability_snapshot(
            {"SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": _write(tmp_path, bad)}
        )


def test_throws_when_declared_hash_does_not_match_recomputed(tmp_path):
    tampered = _valid_snapshot()
    tampered["capability_hash"] = "0" * 64
    with pytest.raises(DeviceCapabilityConfigError, match="hash"):
        load_device_capability_snapshot(
            {"SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH": _write(tmp_path, tampered)}
        )


def test_capability_member_returns_the_device_binding_for_an_exact_target():
    snap = empty_device_capability_snapshot()
    snap = _load_from_dict(_valid_snapshot())
    binding = capability_member(snap, "M(0,0;1,0)", 0.45)
    assert binding.device_id == "scada-rtu-07"
    assert binding.adapter_gate_id == "ch3"
    assert binding.target_level == 3
    assert binding.capability_release_id == "cap-2026-07-19"


def test_capability_member_rejects_an_unknown_gate():
    snap = _load_from_dict(_valid_snapshot())
    with pytest.raises(CapabilityMembershipError, match="gate"):
        capability_member(snap, "M(9,9;9,9)", 0.45)


def test_capability_member_rejects_a_non_member_position_including_a_near_miss():
    snap = _load_from_dict(_valid_snapshot())
    with pytest.raises(CapabilityMembershipError):
        capability_member(snap, "M(0,0;1,0)", 0.450000001)


def _load_from_dict(data):
    from schemas.machine_boundary import DeviceCapabilitySnapshot

    return DeviceCapabilitySnapshot(**data)
