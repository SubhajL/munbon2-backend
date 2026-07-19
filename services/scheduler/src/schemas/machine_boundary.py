"""Strict Python mirrors of the shared machine-boundary v1 contracts (PR 6.0).

These pydantic models mirror `contracts/machine-boundary/v1/*.schema.json` field
for field so a drift between the JSON Schema (validated by jsonschema here and by
Ajv in the TypeScript SCADA service) and the Python model fails a test. TEST /
library surface only in PR 6.0: NOT imported by main.py, routes, repositories, or
schemas/__init__.py; emits no intents. 4.3c compiles intents into `CommandIntent`;
6.2 consumes it + produces `ValidationReceipt`; 6.1a produces
`DeviceCapabilitySnapshot`.

Cross-language parity: identifiers are printable ASCII (`[!-~]+`, no Unicode
`\\S`), numbers are finitely bounded, integers use mathematical-integer semantics
(a whole-number float is accepted), and timestamps enforce field ranges — so
Python and Ajv agree on every input, not just the fixtures. Deadline ordering,
capability freshness, quantizer membership, and full calendar validation (leap
day) are runtime semantics owned by 4.3c/6.1a/6.2.
"""

from __future__ import annotations

import math
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

MACHINE_BOUNDARY_SCHEMA_VERSION = 1
# Must equal contracts/machine-boundary/v1/manifest.json:contract_set_sha256. Both
# this module and the TypeScript SCADA mirror pin it so a schema/fixture/expected
# change without a coordinated version bump fails both suites.
MACHINE_BOUNDARY_CONTRACT_SET_SHA256 = (
    "155606e21b0e15dc674a4fb3e5a9e2f40b94d6e1078ae09c973944731f3db0e4"
)


def _strict_int(value: Any) -> Any:
    # Mathematical-integer semantics matching JSON Schema `type: integer`: accept a
    # JSON integer or a whole-number float (1.0 -> 1); reject bool, str, and a
    # non-integral float (3.5).
    if isinstance(value, bool):
        raise ValueError("expected a JSON integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError("expected a JSON integer")


def _strict_number(value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a JSON number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("number must be finite")
    return value


_UUID_RE = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_SHA256_RE = r"^[0-9a-f]{64}$"
_REQUEST_ID_RE = r"^[A-Za-z0-9._-]{1,128}$"
_ID_TOKEN_RE = r"^[!-~]+$"  # printable ASCII, engine-independent (no Unicode \S)
_UTC_RE = (
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]{1,6})?Z$"
)

Uuid = Annotated[str, StringConstraints(min_length=36, max_length=36, pattern=_UUID_RE)]
Sha256 = Annotated[
    str, StringConstraints(min_length=64, max_length=64, pattern=_SHA256_RE)
]
RequestId = Annotated[str, StringConstraints(pattern=_REQUEST_ID_RE)]
IdToken = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=_ID_TOKEN_RE)
]
ReleaseId = Annotated[
    str, StringConstraints(min_length=1, max_length=256, pattern=_ID_TOKEN_RE)
]
UtcInstant = Annotated[
    str, StringConstraints(min_length=20, max_length=27, pattern=_UTC_RE)
]
PositiveInt = Annotated[int, BeforeValidator(_strict_int), Field(ge=1)]
TargetLevel = Annotated[int, BeforeValidator(_strict_int), Field(ge=0, le=65535)]
PositionM = Annotated[float, BeforeValidator(_strict_number), Field(ge=0, le=1000)]

EventKind = Literal["open", "trim", "close"]
CommandMode = Literal["shadow", "operator_approved"]
ValidationStatus = Literal["validation_accepted", "validation_rejected"]
ValidationRejectionReason = Literal[
    "schema_invalid",
    "capability_mismatch",
    "target_invalid",
    "not_before_violation",
    "deadline_expired",
    "lineage_mismatch",
    "freshness_failed",
    "idempotency_conflict",
]


class _MachineBoundaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class DeviceTargetCapability(_MachineBoundaryModel):
    target_position_m: PositionM
    target_level: TargetLevel


class DeviceCapability(_MachineBoundaryModel):
    device_id: IdToken
    adapter_gate_id: IdToken
    targets: Annotated[List[DeviceTargetCapability], Field(min_length=1)]

    @field_validator("targets")
    @classmethod
    def _targets_unique(cls, value: List[DeviceTargetCapability]):
        seen = set()
        for target in value:
            key = (target.target_position_m, target.target_level)
            if key in seen:
                raise ValueError("targets must be unique (schema uniqueItems)")
            seen.add(key)
        return value


class DeviceCapabilitySnapshot(_MachineBoundaryModel):
    schema_version: Literal[1]
    capability_release_id: IdToken
    capability_hash: Sha256
    # A map keyed by canonical_gate_id -> capability: one gate maps to at most one
    # device (structural uniqueness). Empty map is the valid dark default.
    capabilities: Dict[IdToken, DeviceCapability]


class CommandLineage(_MachineBoundaryModel):
    campaign_id: Uuid
    plan_id: Uuid
    plan_version: PositiveInt
    input_content_hash: Sha256
    draft_content_hash: Sha256
    requirement_run_id: Uuid
    requirement_version: PositiveInt
    requirement_set_sha256: Sha256
    model_snapshot_id: Sha256
    model_release_id: ReleaseId
    model_release_content_hash: Sha256
    prediction_run_id: Sha256
    prediction_identity_version: Literal[2]
    engine_descriptor_content_hash: Sha256
    artifact_sha256: Sha256


class CommandIntent(_MachineBoundaryModel):
    schema_version: Literal[1]
    intent_id: Uuid
    correlation_id: Uuid
    request_id: RequestId
    idempotency_key: IdToken
    canonical_gate_id: IdToken
    event_kind: EventKind
    event_sequence: PositiveInt
    gate_event_sequence: PositiveInt
    device_id: IdToken
    adapter_gate_id: IdToken
    capability_release_id: IdToken
    capability_hash: Sha256
    target_position_m: PositionM
    target_level: TargetLevel
    not_before: UtcInstant
    deadline: UtcInstant
    mode: CommandMode
    lineage: CommandLineage

    @model_validator(mode="after")
    def _event_position_invariant(self) -> "CommandIntent":
        # Mirror gate_plan_events: close -> position 0; open/trim -> position > 0.
        if self.event_kind == "close" and self.target_position_m != 0:
            raise ValueError("a close intent requires target_position_m == 0")
        if self.event_kind in ("open", "trim") and not self.target_position_m > 0:
            raise ValueError("an open/trim intent requires target_position_m > 0")
        return self


class ValidationReceipt(_MachineBoundaryModel):
    schema_version: Literal[1]
    receipt_id: Uuid
    intent_id: Uuid
    correlation_id: Uuid
    request_id: RequestId
    idempotency_key: IdToken
    intent_content_hash: Sha256
    capability_hash: Sha256
    status: ValidationStatus
    validated_at: UtcInstant
    reason_code: Optional[ValidationRejectionReason]

    @model_validator(mode="after")
    def _reason_matches_status(self) -> "ValidationReceipt":
        if self.status == "validation_accepted" and self.reason_code is not None:
            raise ValueError("an accepted receipt must carry a null reason_code")
        if self.status == "validation_rejected" and self.reason_code is None:
            raise ValueError("a rejected receipt must carry a reason_code")
        return self


# manifest schema filename -> mirror model (the contract test binds these).
MODEL_BY_SCHEMA = {
    "command-intent.schema.json": CommandIntent,
    "validation-receipt.schema.json": ValidationReceipt,
    "device-capability-snapshot.schema.json": DeviceCapabilitySnapshot,
}
