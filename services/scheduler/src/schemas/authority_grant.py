"""Strict request/response schemas for the authority-grant surface (PR 7.1a).

Every inbound model is extra=forbid with strict scalars; ``to_candidate``
projects the parsed request into the pure ``AuthorityGrantCandidate`` the core
validation consumes (plain dicts, never pydantic models). Responses expose the
DERIVED status and the ordered event ledger — never a mutable status column.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
)
from typing_extensions import Annotated

from core.authority_grant import AuthorityGrantCandidate
from schemas.machine_boundary import Sha256


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("must be timezone-aware")
    return value


def _strict_int(value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected a JSON integer")
    return value


def _strict_number(value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a JSON number")
    return value


NonBlank = Annotated[
    str, Field(min_length=1, max_length=200), AfterValidator(_non_blank)
]
# Release ids follow the machine-boundary ReleaseId contract cap (256), NOT the
# generic 200 cap — a stored plan with a 201-256 char release id must be grantable.
ReleaseIdStr = Annotated[
    str, Field(min_length=1, max_length=256), AfterValidator(_non_blank)
]
BoundedReason = Annotated[
    str, Field(min_length=1, max_length=500), AfterValidator(_non_blank)
]
BoundedRef = Annotated[
    str, Field(min_length=1, max_length=200), AfterValidator(_non_blank)
]
AwareDatetime = Annotated[datetime, AfterValidator(_aware)]
SchemaVersion1 = Annotated[Literal[1], BeforeValidator(_strict_int)]
PositiveInt = Annotated[int, BeforeValidator(_strict_int), Field(gt=0)]
TrimCount = Annotated[int, BeforeValidator(_strict_int), Field(ge=0, le=2)]
NonNegativeNumber = Annotated[
    float,
    BeforeValidator(_strict_number),
    Field(ge=0, allow_inf_nan=False),
]
PositiveNumber = Annotated[
    float,
    BeforeValidator(_strict_number),
    Field(gt=0, allow_inf_nan=False),
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class CommandabilityEvidenceIn(_StrictModel):
    schema_version: SchemaVersion1
    model_release_id: ReleaseIdStr
    model_release_content_hash: Sha256
    engine_descriptor_content_hash: Sha256
    commandable: StrictBool
    approval_refs: List[BoundedRef] = Field(min_length=1, max_length=20)


class GatePathIn(_StrictModel):
    section_id: NonBlank
    canonical_gate_id: NonBlank
    path_reach_ids: List[NonBlank] = Field(max_length=50)


class GrantScopeIn(_StrictModel):
    schema_version: SchemaVersion1
    gate_paths: List[GatePathIn] = Field(min_length=1, max_length=100)


class InitializationIn(_StrictModel):
    kind: Literal["dry"]


class EvidenceManifestIn(_StrictModel):
    schema_version: SchemaVersion1
    refs: List[BoundedRef] = Field(min_length=1, max_length=20)


class AuthorityGrantRequest(_StrictModel):
    plan_id: UUID
    plan_version: PositiveInt
    model_release_id: ReleaseIdStr
    model_release_content_hash: Sha256
    engine_descriptor_content_hash: Sha256
    commandability_evidence: CommandabilityEvidenceIn
    capability_release_id: ReleaseIdStr
    capability_hash: Sha256
    scope: GrantScopeIn
    flow_lower_exclusive_m3s: NonNegativeNumber
    flow_upper_inclusive_m3s: PositiveNumber
    initialization: InitializationIn
    maximum_continuous_open_seconds: PositiveInt
    maximum_intermediate_trims: TrimCount
    shadow_evidence_sha256: Sha256
    hold_drill_evidence_sha256: Sha256
    rollback_drill_evidence_sha256: Sha256
    evidence_manifest: EvidenceManifestIn
    expires_at: AwareDatetime
    reason: BoundedReason

    def to_candidate(self) -> AuthorityGrantCandidate:
        return AuthorityGrantCandidate(
            plan_id=self.plan_id,
            plan_version=self.plan_version,
            model_release_id=self.model_release_id,
            model_release_content_hash=self.model_release_content_hash,
            engine_descriptor_content_hash=self.engine_descriptor_content_hash,
            commandability_evidence=self.commandability_evidence.model_dump(),
            capability_release_id=self.capability_release_id,
            capability_hash=self.capability_hash,
            scope=self.scope.model_dump(),
            flow_lower_exclusive_m3s=self.flow_lower_exclusive_m3s,
            flow_upper_inclusive_m3s=self.flow_upper_inclusive_m3s,
            initialization=self.initialization.model_dump(),
            maximum_continuous_open_seconds=self.maximum_continuous_open_seconds,
            maximum_intermediate_trims=self.maximum_intermediate_trims,
            shadow_evidence_sha256=self.shadow_evidence_sha256,
            hold_drill_evidence_sha256=self.hold_drill_evidence_sha256,
            rollback_drill_evidence_sha256=self.rollback_drill_evidence_sha256,
            evidence_manifest=self.evidence_manifest.model_dump(),
            expires_at=self.expires_at,
        )


class AuthorityGrantRenewalRequest(_StrictModel):
    new_expires_at: AwareDatetime
    shadow_evidence_sha256: Sha256
    hold_drill_evidence_sha256: Sha256
    rollback_drill_evidence_sha256: Sha256
    evidence_manifest: EvidenceManifestIn
    reason: BoundedReason


class AuthorityGrantRevocationRequest(_StrictModel):
    reason: BoundedReason


class AuthorityGrantEventOut(_StrictModel):
    event_sequence: int
    event_type: Literal["granted", "renewed", "revoked"]
    effective_expires_at: Optional[datetime]
    actor_subject: str
    reason: str
    occurred_at: datetime


class AuthorityGrantResponse(_StrictModel):
    grant_id: UUID
    plan_id: UUID
    plan_version: int
    status: Literal["active", "expired", "revoked"]
    effective_expires_at: datetime
    model_release_id: str
    model_release_content_hash: str
    engine_descriptor_content_hash: str
    capability_release_id: str
    capability_hash: str
    scope: GrantScopeIn
    flow_lower_exclusive_m3s: float
    flow_upper_inclusive_m3s: float
    initialization: InitializationIn
    maximum_continuous_open_seconds: int
    maximum_intermediate_trims: int
    grant_content_sha256: str
    created_by_subject: str
    events: List[AuthorityGrantEventOut]


class AuthorityGrantReviewResponse(_StrictModel):
    would_grant_content_sha256: Sha256


AuthorityBlocker = Literal[
    "plan_not_shadow_active",
    "noncommandable_release",
    "capability_unconfigured",
    "capability_stale",
    "scope_unapproved_gate",
    "receipt_coverage_incomplete",
    "plan_envelope_empty",
    "grant_already_exists",
]


class AuthorityApplicabilityResponse(_StrictModel):
    plan_id: UUID
    plan_version: int
    evaluated_at: datetime
    lifecycle_state: str
    model_release_id: str
    model_release_content_hash: Sha256
    engine_descriptor_content_hash: Sha256
    model_release_commandable: bool
    capability_release_id: str
    capability_hash: Sha256
    capability_configured: bool
    capability_matches_outbox: bool
    scope: GrantScopeIn
    flow_lower_exclusive_m3s: float
    flow_upper_inclusive_m3s: float
    initialization: InitializationIn
    maximum_continuous_open_seconds: int
    maximum_intermediate_trims: int
    outbox_intent_count: int
    accepted_receipt_intent_count: int
    matching_receipt_intent_count: int
    receipt_coverage_complete: bool
    existing_grant_status: Optional[Literal["active", "expired", "revoked"]]
    existing_grant_id: Optional[UUID]
    blockers: List[AuthorityBlocker]
    can_grant: bool


def build_grant_response(view) -> AuthorityGrantResponse:
    """Project an AuthorityGrantView into the bounded response model."""
    grant = view.grant
    return AuthorityGrantResponse(
        grant_id=grant.grant_id,
        plan_id=grant.plan_id,
        plan_version=grant.plan_version,
        status=view.status,
        effective_expires_at=view.effective_expires_at,
        model_release_id=grant.model_release_id,
        model_release_content_hash=grant.model_release_content_hash,
        engine_descriptor_content_hash=grant.engine_descriptor_content_hash,
        capability_release_id=grant.capability_release_id,
        capability_hash=grant.capability_hash,
        scope=GrantScopeIn(**json.loads(grant.scope_document_text)),
        flow_lower_exclusive_m3s=grant.flow_lower_exclusive_m3s,
        flow_upper_inclusive_m3s=grant.flow_upper_inclusive_m3s,
        initialization=InitializationIn(
            **json.loads(grant.initialization_document_text)
        ),
        maximum_continuous_open_seconds=grant.maximum_continuous_open_seconds,
        maximum_intermediate_trims=grant.maximum_intermediate_trims,
        grant_content_sha256=grant.grant_content_sha256,
        created_by_subject=grant.created_by_subject,
        events=[
            AuthorityGrantEventOut(
                event_sequence=event.event_sequence,
                event_type=event.event_type,
                effective_expires_at=event.effective_expires_at,
                actor_subject=event.actor_subject,
                reason=event.reason,
                occurred_at=event.occurred_at,
            )
            for event in view.events
        ],
    )
