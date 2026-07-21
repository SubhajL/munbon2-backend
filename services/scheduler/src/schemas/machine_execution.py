from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.machine_boundary import IdToken, Sha256, Uuid, UtcInstant

ExecutionStatus = Literal[
    "execution_succeeded",
    "execution_rejected",
    "execution_failed",
    "readback_mismatch",
    "execution_in_doubt",
]


class ExecutionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["writeHoldingRegister", "writeCoil"]
    point: str = Field(min_length=1, max_length=64)
    address: int = Field(ge=0, le=65535)
    value: int = Field(ge=0, le=65535)


class ExecutionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    receipt_id: Uuid
    intent_id: Uuid
    idempotency_key: IdToken
    grant_id: Uuid
    authority_not_after: UtcInstant
    original_intent_content_hash: Sha256
    execution_intent_content_hash: Sha256
    capability_hash: Sha256
    purpose: Literal["operator_approved", "fail_safe_close"]
    status: ExecutionStatus
    reason_code: Optional[
        Literal[
            "machine_commands_disabled",
            "authority_binding_mismatch",
            "idempotency_conflict",
            "capability_mismatch",
            "target_invalid",
            "lineage_mismatch",
            "not_yet_due",
            "deadline_expired",
            "freshness_failed",
            "write_failed",
            "readback_mismatch",
            "readback_unavailable",
            "prior_attempt_in_doubt",
        ]
    ]
    target_level: int = Field(ge=0, le=65535)
    observed_level: Optional[int] = Field(default=None, ge=0, le=65535)
    readback_quality: Literal[
        "ok", "stale", "offline", "decode_error", "modbus_exception", "unavailable"
    ]
    writes: List[ExecutionWrite] = Field(max_length=8)
    executed_at: UtcInstant

    @model_validator(mode="after")
    def reason_matches_status(self):
        if self.status == "execution_succeeded" and self.reason_code is not None:
            raise ValueError("successful execution cannot carry a reason")
        if self.status == "execution_succeeded" and (
            self.readback_quality != "ok" or self.observed_level != self.target_level
        ):
            raise ValueError("successful execution requires matching fresh readback")
        if self.status != "execution_succeeded" and not self.reason_code:
            raise ValueError("non-success execution must carry a reason")
        return self
