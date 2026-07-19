"""Fail-closed device-capability snapshot loader + exact membership (PR 4.3c-1).

The scheduler consumes the exact artifact the 6.1a SCADA service serves: a full
``device-capability-snapshot`` (schema_version + capability_hash + capabilities
map keyed by canonical_gate_id). 6.2 later re-fetches it over HTTP with a service
token; here it is loaded once from an operator-configured path.

FAIL-CLOSED: an unset/blank path yields the empty dark default (ZERO
machine-capable gates, so nothing is ever activatable); an unreadable, malformed,
schema-violating, or hash-mismatched file raises ``DeviceCapabilityConfigError``.
The snapshot's declared ``capability_hash`` is INDEPENDENTLY recomputed (RFC-8785
JCS, cross-language-identical to the TypeScript producer) and must match — a
tampered/drifted snapshot never grants authority.

Membership is EXACT: a gate event's continuous optimizer position must equal a
discrete capability target (compared by canonical number string, not float ==);
continuous->discrete quantization is 6.1b's responsibility, so a non-member fails
closed rather than commanding an unachievable position.
"""

from __future__ import annotations

import json
from typing import NamedTuple, Optional

from pydantic import ValidationError

from core.canonical_json import canonicalize, sha256_hex
from schemas.machine_boundary import DeviceCapabilitySnapshot

CAPABILITY_HASH_DOMAIN_PREFIX = "munbon:device-capability-snapshot:v1\n"
EMPTY_RELEASE_ID = "__empty__"
_ENV_PATH_KEY = "SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH"


class DeviceCapabilityConfigError(Exception):
    """The configured device-capability snapshot cannot be trusted (fail closed)."""


class CapabilityMembershipError(Exception):
    """A gate/position is not an exact member of the capability snapshot."""


class CapabilityBinding(NamedTuple):
    device_id: str
    adapter_gate_id: str
    target_level: int
    capability_release_id: str
    capability_hash: str


def _content_hash(schema_version: int, capability_release_id: str, capabilities) -> str:
    """The FROZEN (6.0) content hash over the snapshot WITHOUT its capability_hash."""
    return sha256_hex(
        CAPABILITY_HASH_DOMAIN_PREFIX
        + canonicalize(
            {
                "schema_version": schema_version,
                "capability_release_id": capability_release_id,
                "capabilities": capabilities,
            }
        )
    )


def empty_device_capability_snapshot() -> DeviceCapabilitySnapshot:
    """The dark default: zero machine-capable gates."""
    capability_hash = _content_hash(1, EMPTY_RELEASE_ID, {})
    return DeviceCapabilitySnapshot(
        schema_version=1,
        capability_release_id=EMPTY_RELEASE_ID,
        capability_hash=capability_hash,
        capabilities={},
    )


def load_device_capability_snapshot(env) -> DeviceCapabilitySnapshot:
    path = env.get(_ENV_PATH_KEY)
    path = path.strip() if isinstance(path, str) else None
    if not path:
        return empty_device_capability_snapshot()

    try:
        raw = open(path, "r", encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as error:
        # UnicodeDecodeError (a ValueError, not OSError) is how a non-UTF-8/binary
        # file surfaces; both are fail-closed config errors, never a raw traceback.
        raise DeviceCapabilityConfigError(
            f"{_ENV_PATH_KEY} is set but the snapshot cannot be read: {error}"
        ) from error

    try:
        data = json.loads(raw)
    except ValueError as error:
        raise DeviceCapabilityConfigError(
            f"device-capability snapshot is not valid JSON: {error}"
        ) from error
    if not isinstance(data, dict):
        raise DeviceCapabilityConfigError("device-capability snapshot must be an object")

    try:
        snapshot = DeviceCapabilitySnapshot(**data)
    except (ValidationError, TypeError) as error:
        raise DeviceCapabilityConfigError(
            f"device-capability snapshot violates the v1 contract: {error}"
        ) from error

    expected = _content_hash(
        snapshot.schema_version,
        snapshot.capability_release_id,
        data["capabilities"],
    )
    if snapshot.capability_hash != expected:
        raise DeviceCapabilityConfigError(
            "device-capability snapshot capability_hash does not match its content"
        )
    return snapshot


def capability_member(
    snapshot: DeviceCapabilitySnapshot,
    canonical_gate_id: str,
    position_m: float,
) -> CapabilityBinding:
    """Return the device binding for an EXACT (gate, position) capability member.

    Raises ``CapabilityMembershipError`` for an unknown gate or a position that is
    not an exact target of that gate. Positions are compared by canonical number
    string so an optimizer near-miss (0.450000001 vs 0.45) is a non-member.
    """
    capability = snapshot.capabilities.get(canonical_gate_id)
    if capability is None:
        raise CapabilityMembershipError(
            f"gate {canonical_gate_id!r} is not a machine-capable gate"
        )
    wanted = canonicalize(position_m)
    match: Optional[int] = None
    for target in capability.targets:
        if canonicalize(target.target_position_m) == wanted:
            match = target.target_level
            break
    if match is None:
        raise CapabilityMembershipError(
            f"position {position_m!r} is not a capability target of gate "
            f"{canonical_gate_id!r}"
        )
    return CapabilityBinding(
        device_id=capability.device_id,
        adapter_gate_id=capability.adapter_gate_id,
        target_level=match,
        capability_release_id=snapshot.capability_release_id,
        capability_hash=snapshot.capability_hash,
    )
