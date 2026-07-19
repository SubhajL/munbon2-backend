"""Persistence for immutable control-plan drafts (PR 4.3a).

One draft = one transaction: header, pinned requirements, gate events, and the
initial transition commit together or not at all. Identity is the
content-addressed ``input_content_hash``; a duplicate insert returns the
committed winner only after verifying both content hashes match exactly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.control_plan import (
    canonical_json_text,
    control_plan_draft_hash,
    control_plan_input_hash,
)
from core.control_plan_lifecycle import TERMINAL_STATES
from core.open_loop_execution import (
    ACTIVATION_TRANSITION_TYPE,
    ExpectedScope,
    RecoveryPlan,
    RecoveryReport,
)
from core.predicted_delivery_ledger import (
    LedgerEntry,
    LedgerProjectionError,
    predicted_delivery_ledger_sha256,
    verify_ledger_entry_columns,
)
from models.control_plan import (
    ControlActiveGateAuthority,
    ControlCommandExecutionEvent,
    ControlCommandOutboxRow,
    ControlPlanCampaignVersion,
    ControlPlanRequirement,
    ControlPlanRun,
    ControlStateTransition,
    GatePlanEventRow,
    SectionDeliveryLedgerEntry,
)
from services.clients.control_flow_client import (
    FLOW_PREDICTION_IDENTITY_VERSION_V2,
)


class ControlPlanRepositoryError(Exception):
    """Base repository failure."""


class PlanContentConflictError(ControlPlanRepositoryError):
    """Same content-addressed identity with different stored content."""


class DraftStoreCorruptError(ControlPlanRepositoryError):
    """Stored draft fails its own content-hash verification."""


class TransitionConflictError(ControlPlanRepositoryError):
    """A concurrent writer already claimed this transition sequence."""


class UnknownCampaignError(ControlPlanRepositoryError):
    """A present campaign_id references no existing campaign — fail closed rather
    than auto-create a campaign under a caller-chosen id (maps to 404/422)."""


@dataclass(frozen=True)
class RequirementRecord:
    requirement_id: UUID
    run_id: UUID
    source_version: int
    service_date: date
    section_id: str
    zone: int
    required_volume_m3: float
    window_start: datetime
    window_end: datetime
    quality: str
    published_at: datetime
    as_of_date: date
    source_data_status: str
    planning_disposition: str
    delivery_node_id: Optional[str]
    gate_id: Optional[str]
    maximum_delivery_m3s: Optional[float]
    approved_excess_m3: Optional[float]
    travel_delay_seconds: Optional[int]
    minimum_delivery_fraction: Optional[float]
    maximum_delivery_fraction: Optional[float]
    path_reach_ids_document_text: Optional[str]
    rotation_windows_document_text: Optional[str]
    requirement_document_text: str


@dataclass(frozen=True)
class GateEventRecord:
    event_sequence: int
    gate_event_sequence: int
    gate_id: str
    event_kind: str
    planned_at: datetime
    target_position_m: float
    source_flow_m3s: float
    trim_ordinal: Optional[int]


@dataclass(frozen=True)
class TransitionRecord:
    transition_sequence: int
    transition_type: str
    from_state: Optional[str]
    to_state: str
    actor_subject: str
    reason: Optional[str]
    transition_document_text: Optional[str]
    occurred_at: Optional[datetime] = None


@dataclass(frozen=True)
class OutboxRow:
    """One append-only command-intent outbox row (PR 4.3c-1)."""

    intent_id: UUID
    correlation_id: UUID
    request_id: str
    idempotency_key: str
    canonical_gate_id: str
    event_kind: str
    event_sequence: int
    gate_event_sequence: int
    device_id: str
    adapter_gate_id: str
    capability_release_id: str
    capability_hash: str
    target_position_m: float
    target_level: int
    not_before: datetime
    deadline: datetime
    mode: str
    intent_document_text: str
    intent_content_hash: str
    activation_transition_sequence: int


@dataclass(frozen=True)
class ScopeRow:
    """One (section, gate) authority-mutex row taken by an activation (PR 4.3c-1)."""

    section_id: str
    gate_id: str
    activation_transition_sequence: int


@dataclass(frozen=True)
class ExecutionEventRow:
    """One append-only open-loop execution event (PR 5.2b). ``intent_id`` is None
    for plan-level operator events (held/resumed)."""

    event_id: UUID
    intent_id: Optional[UUID]
    event_type: str
    worker_id: Optional[str]
    detail_document_text: Optional[str]
    occurred_at: datetime


@dataclass(frozen=True)
class OpenLoopContext:
    """Everything a worker tick needs for a plan (PR 5.2b): its full transition
    history (for the derived lifecycle state), its outbox intents ordered by the
    global ``event_sequence``, its execution events, and the authority row's
    ``granted_at`` (None if the plan holds no scope)."""

    transitions: list
    outbox: list
    events: list
    granted_at: Optional[datetime]


class ScopeConflictError(Exception):
    """Another active plan already holds one of the requested (section, gate) scopes."""


def _violated_constraint(error: IntegrityError):
    """The Postgres constraint name behind an IntegrityError.

    SQLAlchemy's asyncpg adapter does NOT copy ``constraint_name`` onto the wrapper
    (``error.orig``); the attribute lives on the underlying asyncpg exception, which
    is the wrapper's ``__cause__``. Checking both keeps the classification robust.
    """
    for candidate in (error.orig, getattr(error.orig, "__cause__", None)):
        name = getattr(candidate, "constraint_name", None)
        if name:
            return name
    return None


@dataclass(frozen=True)
class DraftPlanRecord:
    plan_id: UUID
    plan_version: int
    identity_version: int
    input_content_hash: str
    draft_content_hash: str
    lifecycle_state: str
    optimizer_status: str
    prediction_status: str
    requirement_run_id: UUID
    requirement_version: int
    model_snapshot_id: str
    model_release_id: str
    model_release_content_hash: str
    prediction_run_id: Optional[str]
    prediction_member_summaries: Optional[str]
    horizon_start: datetime
    horizon_end: datetime
    model_step_seconds: int
    max_intermediate_trims: int
    canonical_input_document_text: str
    model_snapshot_document_text: str
    optimizer_result_document_text: str
    optimizer_result_sha256: str
    prediction_request_document_text: Optional[str]
    prediction_response_document_text: Optional[str]
    prediction_response_sha256: Optional[str]
    created_by_subject: str
    requirements: tuple[RequirementRecord, ...]
    events: tuple[GateEventRecord, ...]
    transitions: tuple[TransitionRecord, ...]
    # Provenance v2 (PR 4.4b-2): all None on a v1 row; all present on a v2 row.
    provenance_version: Optional[int] = None
    prediction_identity_version: Optional[int] = None
    engine_id: Optional[str] = None
    engine_semantic_contract_version: Optional[int] = None
    engine_build_digest: Optional[str] = None
    engine_descriptor_content_hash: Optional[str] = None
    artifact_sha256: Optional[str] = None
    artifact_uncompressed_size_bytes: Optional[int] = None
    artifact_media_type: Optional[str] = None
    artifact_encoding: Optional[str] = None
    artifact_encoding_version: Optional[int] = None
    coverage_summary_document_text: Optional[str] = None
    coverage_summary_sha256: Optional[str] = None
    predicted_delivery_ledger_sha256: Optional[str] = None
    ledger_entries: tuple[LedgerEntry, ...] = ()
    created_at: Optional[datetime] = None
    # The stable campaign this version belongs to (PR 4.4b-4). Set by
    # ``allocate_campaign_version`` on a fresh draft and by ``_assemble`` (from the
    # immutable mapping) on every load; a load with no mapping fails closed.
    campaign_id: Optional[UUID] = None


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _campaign_advisory_lock_key(campaign_id: UUID) -> int:
    """A stable SIGNED 64-bit advisory-lock key for a campaign uuid.

    A hash COLLISION only serializes two DISTINCT campaigns on one lock (harmless:
    after acquiring it the ``max(plan_version)`` read still filters by the exact
    campaign_id, so no campaign is ever mis-allocated); it never mis-orders a
    single campaign's own version allocations."""
    digest = hashlib.sha256(str(campaign_id).encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big", signed=True)


# A fixed SIGNED 64-bit key that serializes restart authority-recovery across pods
# (mirrors migrate.MIGRATIONS_LOCK_ID). Distinct from every campaign lock key, so a
# recovery never blocks — or is blocked by — a live version allocation.
RECOVERY_LOCK_ID = int.from_bytes(
    hashlib.sha256(b"scheduler:open-loop-authority-recovery").digest()[:8],
    "big",
    signed=True,
)


PROVENANCE_VERSION_V2 = 2
PROVENANCE_REFERENCE_HASH_PREFIX = "scheduler:control-plan-provenance:v2\n"


def build_provenance_reference_document(
    *,
    prediction_run_id: str,
    prediction_identity_version: int,
    engine_id: str,
    engine_semantic_contract_version: int,
    engine_build_digest: str,
    engine_descriptor_content_hash: str,
    artifact_sha256: str,
    artifact_uncompressed_size_bytes: int,
    artifact_media_type: str,
    artifact_encoding: str,
    artifact_encoding_version: int,
    prediction_member_summaries_sha256: str,
    coverage_summary_sha256: str,
    predicted_delivery_ledger_sha256: str,
) -> dict:
    """The canonical, BOUNDED reference a v2 draft binds into its draft hash: the
    run id + engine pins + artifact metadata + summary/ledger hashes — never the
    trajectory. Recomputed on every v2 read so any column edited independently of
    the hash is caught."""
    return {
        "provenance_version": PROVENANCE_VERSION_V2,
        "prediction_run_id": prediction_run_id,
        "prediction_identity_version": prediction_identity_version,
        "engine": {
            "engine_id": engine_id,
            "semantic_contract_version": engine_semantic_contract_version,
            "build_digest": engine_build_digest,
            "engine_descriptor_content_hash": engine_descriptor_content_hash,
        },
        "artifact": {
            "artifact_sha256": artifact_sha256,
            "uncompressed_size_bytes": artifact_uncompressed_size_bytes,
            "media_type": artifact_media_type,
            "encoding": artifact_encoding,
            "encoding_version": artifact_encoding_version,
        },
        "summaries": {
            "prediction_member_summaries_sha256": (
                prediction_member_summaries_sha256
            ),
            "coverage_summary_sha256": coverage_summary_sha256,
        },
        "predicted_delivery_ledger_sha256": predicted_delivery_ledger_sha256,
    }


def provenance_reference_sha256(document: dict) -> str:
    return hashlib.sha256(
        (PROVENANCE_REFERENCE_HASH_PREFIX + canonical_json_text(document)).encode(
            "utf-8"
        )
    ).hexdigest()


def provenance_reference_document_for_record(record: DraftPlanRecord) -> dict:
    """Reconstruct a stored v2 record's provenance reference from its columns."""
    return build_provenance_reference_document(
        prediction_run_id=record.prediction_run_id,
        prediction_identity_version=record.prediction_identity_version,
        engine_id=record.engine_id,
        engine_semantic_contract_version=record.engine_semantic_contract_version,
        engine_build_digest=record.engine_build_digest,
        engine_descriptor_content_hash=record.engine_descriptor_content_hash,
        artifact_sha256=record.artifact_sha256,
        artifact_uncompressed_size_bytes=record.artifact_uncompressed_size_bytes,
        artifact_media_type=record.artifact_media_type,
        artifact_encoding=record.artifact_encoding,
        artifact_encoding_version=record.artifact_encoding_version,
        prediction_member_summaries_sha256=text_sha256(
            record.prediction_member_summaries
        ),
        coverage_summary_sha256=record.coverage_summary_sha256,
        predicted_delivery_ledger_sha256=record.predicted_delivery_ledger_sha256,
    )


def verify_stored_draft(record: DraftPlanRecord) -> None:
    """Fail closed if any stored canonical document drifted from its hash.

    Dispatches by the row's storage version: a v2 (artifact-reference) row is
    verified WITHOUT the full prediction response (which is NULL); a v1 row (NULL
    provenance_version) keeps the original full-response verification unchanged.
    Any OTHER non-null provenance_version is rejected as corrupt — never silently
    dispatched to the v1 path (which would skip the v2 artifact-reference checks).
    """
    version = getattr(record, "provenance_version", None)
    if version == PROVENANCE_VERSION_V2:
        _verify_stored_draft_v2(record)
    elif version is None:
        _verify_stored_draft_v1(record)
    else:
        raise DraftStoreCorruptError(
            f"stored draft carries unknown provenance_version {version!r}"
        )


def _verify_input_and_optimizer(record: DraftPlanRecord) -> dict:
    """Shared v1/v2 checks: input hash, header pins, optimizer sha."""
    try:
        input_document = json.loads(record.canonical_input_document_text)
    except ValueError as error:
        raise DraftStoreCorruptError(
            f"stored input document is not valid JSON: {error}"
        ) from error
    recomputed_input = control_plan_input_hash(input_document)
    if recomputed_input != record.input_content_hash:
        raise DraftStoreCorruptError(
            "stored input document does not match its content hash"
        )
    # Tie the queryable header pin columns back to the hash-covered input
    # document, so a header pin edited independently of the document is caught.
    pins = input_document.get("snapshot_pins") if isinstance(
        input_document, dict
    ) else None
    if not isinstance(pins, dict) or (
        pins.get("model_snapshot_id") != record.model_snapshot_id
        or pins.get("model_release_id") != record.model_release_id
        or pins.get("model_release_content_hash")
        != record.model_release_content_hash
    ):
        raise DraftStoreCorruptError(
            "stored model pins do not match the hashed input document"
        )
    if text_sha256(record.optimizer_result_document_text) != (
        record.optimizer_result_sha256
    ):
        raise DraftStoreCorruptError(
            "stored optimizer result does not match its hash"
        )
    return input_document


def _draft_hash_over(
    record: DraftPlanRecord,
    input_document: dict,
    prediction_binding: Optional[str],
) -> None:
    draft_document = {
        "input_document": input_document,
        "optimizer_result_document": json.loads(
            record.optimizer_result_document_text
        ),
        "prediction_request_document": (
            None
            if record.prediction_request_document_text is None
            else json.loads(record.prediction_request_document_text)
        ),
        "prediction_response_sha256": prediction_binding,
    }
    if control_plan_draft_hash(draft_document) != record.draft_content_hash:
        raise DraftStoreCorruptError(
            "stored draft content does not match its draft hash"
        )


def _verify_ledger_columns(record: DraftPlanRecord) -> None:
    for entry in record.ledger_entries:
        try:
            verify_ledger_entry_columns(entry)
        except LedgerProjectionError as error:
            raise DraftStoreCorruptError(str(error)) from error


def _verify_stored_draft_v1(record: DraftPlanRecord) -> None:
    input_document = _verify_input_and_optimizer(record)
    if record.prediction_response_document_text is not None:
        if record.prediction_response_sha256 is None or text_sha256(
            record.prediction_response_document_text
        ) != record.prediction_response_sha256:
            raise DraftStoreCorruptError(
                "stored prediction response does not match its hash"
            )
    _draft_hash_over(record, input_document, record.prediction_response_sha256)
    _verify_ledger_columns(record)


def _verify_engine_matches_snapshot(record: DraftPlanRecord) -> None:
    """Fail closed unless a v2 row's stored engine pins equal the prediction_engine
    descriptor embedded in its stored model-snapshot document.

    The scheduler stores the full model-snapshot document (a PR 4.4b-1 schema-v3
    snapshot embeds its prediction_engine verbatim), so the recorded engine columns
    can be cross-checked against the snapshot itself — an engine-B pin set stored on
    an engine-A snapshot is corruption even when internally self-consistent with the
    draft hash."""
    try:
        snapshot = json.loads(record.model_snapshot_document_text)
    except ValueError as error:
        raise DraftStoreCorruptError(
            f"stored model snapshot document is not valid JSON: {error}"
        ) from error
    engine = snapshot.get("prediction_engine") if isinstance(
        snapshot, dict
    ) else None
    if not isinstance(engine, dict):
        raise DraftStoreCorruptError(
            "stored v2 draft's model snapshot carries no embedded "
            "prediction_engine descriptor"
        )
    if (
        record.engine_id != engine.get("engine_id")
        or record.engine_semantic_contract_version
        != engine.get("semantic_contract_version")
        or record.engine_build_digest != engine.get("build_digest")
        or record.engine_descriptor_content_hash != engine.get("content_hash")
    ):
        raise DraftStoreCorruptError(
            "stored engine pins disagree with the model snapshot's embedded "
            "prediction_engine descriptor"
        )


def _verify_stored_draft_v2(record: DraftPlanRecord) -> None:
    """Verify a v2 artifact-reference draft WITHOUT the full response.

    The response copy MUST be absent; the engine pins + artifact metadata +
    bounded summaries + ledger hash re-derive the provenance reference bound into
    the draft hash, and every ledger row must reference this plan's run/artifact.
    """
    input_document = _verify_input_and_optimizer(record)
    if (
        record.prediction_response_document_text is not None
        or record.prediction_response_sha256 is not None
    ):
        raise DraftStoreCorruptError(
            "a v2 artifact-reference draft must not copy the prediction response"
        )
    required = {
        "prediction_run_id": record.prediction_run_id,
        "prediction_identity_version": record.prediction_identity_version,
        "engine_id": record.engine_id,
        "engine_semantic_contract_version": (
            record.engine_semantic_contract_version
        ),
        "engine_build_digest": record.engine_build_digest,
        "engine_descriptor_content_hash": record.engine_descriptor_content_hash,
        "artifact_sha256": record.artifact_sha256,
        "artifact_uncompressed_size_bytes": (
            record.artifact_uncompressed_size_bytes
        ),
        "artifact_media_type": record.artifact_media_type,
        "artifact_encoding": record.artifact_encoding,
        "artifact_encoding_version": record.artifact_encoding_version,
        "prediction_member_summaries": record.prediction_member_summaries,
        "coverage_summary_document_text": record.coverage_summary_document_text,
        "coverage_summary_sha256": record.coverage_summary_sha256,
        "predicted_delivery_ledger_sha256": (
            record.predicted_delivery_ledger_sha256
        ),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise DraftStoreCorruptError(
            f"v2 artifact-reference draft is missing columns: {sorted(missing)}"
        )
    # A v2 provenance row pins Flow's identity-v2 contract: the prediction
    # identity version is exactly 2 (not merely present/truthy).
    if record.prediction_identity_version != FLOW_PREDICTION_IDENTITY_VERSION_V2:
        raise DraftStoreCorruptError(
            "v2 artifact-reference draft prediction_identity_version is not "
            f"{FLOW_PREDICTION_IDENTITY_VERSION_V2}"
        )
    _verify_engine_matches_snapshot(record)
    if text_sha256(record.coverage_summary_document_text) != (
        record.coverage_summary_sha256
    ):
        raise DraftStoreCorruptError(
            "stored coverage summary does not match its hash"
        )
    recomputed_ledger_sha = predicted_delivery_ledger_sha256(
        record.ledger_entries
    )
    if recomputed_ledger_sha != record.predicted_delivery_ledger_sha256:
        raise DraftStoreCorruptError(
            "stored predicted-delivery ledger hash does not match its rows"
        )
    _verify_ledger_columns(record)
    for entry in record.ledger_entries:
        if (
            entry.prediction_run_id != record.prediction_run_id
            or entry.prediction_response_sha256 != record.artifact_sha256
        ):
            raise DraftStoreCorruptError(
                f"ledger row for {entry.requirement_id} references a different "
                "prediction than the v2 artifact reference"
            )
    reference_sha = provenance_reference_sha256(
        provenance_reference_document_for_record(record)
    )
    _draft_hash_over(record, input_document, reference_sha)


def build_draft_hash_document(
    canonical_input_document_text: str,
    optimizer_result_document_text: str,
    prediction_request_document_text: Optional[str],
    prediction_response_sha256: Optional[str],
) -> dict:
    return {
        "input_document": json.loads(canonical_input_document_text),
        "optimizer_result_document": json.loads(optimizer_result_document_text),
        "prediction_request_document": (
            None
            if prediction_request_document_text is None
            else json.loads(prediction_request_document_text)
        ),
        "prediction_response_sha256": prediction_response_sha256,
    }


class PostgresControlPlanRepository:
    """SQLAlchemy/asyncpg twin of the in-memory test fake (interface-pinned)."""

    async def allocate_campaign_version(
        self, session: AsyncSession, campaign_id: Optional[UUID]
    ) -> tuple[UUID, int, UUID]:
        """Allocate the (campaign_id, plan_version, plan_id) for a NEW draft.

        ``campaign_id is None`` -> a brand-new campaign (a fresh uuid, distinct from
        the plan_id) at version 1. A present ``campaign_id`` -> the campaign-scoped
        advisory lock, then ``max(plan_version) + 1``; a present-but-UNKNOWN
        campaign fails closed (never auto-creates a campaign under a caller id).
        ``plan_id`` is a fresh per-version uuid. Must run inside the SAME
        transaction that later inserts the run + mapping row, so the
        ``pg_advisory_xact_lock`` is held across the read->insert window and
        released only at commit (a failed compute/txn consumes NO version).

        ISOLATION: this allocate path MUST run under READ COMMITTED (the engine
        default here; PR 4.4b-3 introduced REPEATABLE READ only for the separate
        bounded PROJECTION reads, never for this write transaction). Under READ
        COMMITTED, a racer B that blocked on the advisory lock reads the LATEST
        committed ``max(plan_version)`` once A commits and so takes the next
        version; under REPEATABLE READ B's snapshot would predate A's commit and it
        would re-read the stale max and mint a DUPLICATE version. The
        PRIMARY KEY (campaign_id, plan_version) is the hard backstop that still
        refuses a duplicate even if the isolation assumption is ever violated."""
        if campaign_id is None:
            return uuid4(), 1, uuid4()
        # Serialize concurrent version allocations for THIS campaign so two racers
        # can never read the same max(plan_version) and mint a duplicate version.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _campaign_advisory_lock_key(campaign_id)},
        )
        max_version = await session.scalar(
            select(func.max(ControlPlanCampaignVersion.plan_version)).where(
                ControlPlanCampaignVersion.campaign_id == campaign_id
            )
        )
        if max_version is None:
            raise UnknownCampaignError(
                f"campaign {campaign_id} does not exist; a present campaign_id "
                "must reference an existing campaign"
            )
        return campaign_id, int(max_version) + 1, uuid4()

    async def find_by_input_hash(
        self, session: AsyncSession, input_content_hash: str
    ) -> Optional[DraftPlanRecord]:
        run = await session.scalar(
            select(ControlPlanRun).where(
                ControlPlanRun.input_content_hash == input_content_hash
            )
        )
        if run is None:
            return None
        return await self._assemble(session, run)

    async def load_draft_plan(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> Optional[DraftPlanRecord]:
        run = await session.get(ControlPlanRun, (plan_id, plan_version))
        if run is None:
            return None
        return await self._assemble(session, run)

    async def store_draft_plan(
        self, session: AsyncSession, record: DraftPlanRecord
    ) -> tuple[DraftPlanRecord, bool]:
        header = {
            "plan_id": record.plan_id,
            "plan_version": record.plan_version,
            "identity_version": record.identity_version,
            "input_content_hash": record.input_content_hash,
            "draft_content_hash": record.draft_content_hash,
            "lifecycle_state": record.lifecycle_state,
            "optimizer_status": record.optimizer_status,
            "prediction_status": record.prediction_status,
            "requirement_run_id": record.requirement_run_id,
            "requirement_version": record.requirement_version,
            "model_snapshot_id": record.model_snapshot_id,
            "model_release_id": record.model_release_id,
            "model_release_content_hash": record.model_release_content_hash,
            "prediction_run_id": record.prediction_run_id,
            "prediction_member_summaries": record.prediction_member_summaries,
            "horizon_start": record.horizon_start,
            "horizon_end": record.horizon_end,
            "model_step_seconds": record.model_step_seconds,
            "max_intermediate_trims": record.max_intermediate_trims,
            "canonical_input_document_text": (
                record.canonical_input_document_text
            ),
            "model_snapshot_document_text": record.model_snapshot_document_text,
            "optimizer_result_document_text": (
                record.optimizer_result_document_text
            ),
            "optimizer_result_sha256": record.optimizer_result_sha256,
            "prediction_request_document_text": (
                record.prediction_request_document_text
            ),
            "prediction_response_document_text": (
                record.prediction_response_document_text
            ),
            "prediction_response_sha256": record.prediction_response_sha256,
            "provenance_version": record.provenance_version,
            "prediction_identity_version": record.prediction_identity_version,
            "engine_id": record.engine_id,
            "engine_semantic_contract_version": (
                record.engine_semantic_contract_version
            ),
            "engine_build_digest": record.engine_build_digest,
            "engine_descriptor_content_hash": (
                record.engine_descriptor_content_hash
            ),
            "artifact_sha256": record.artifact_sha256,
            "artifact_uncompressed_size_bytes": (
                record.artifact_uncompressed_size_bytes
            ),
            "artifact_media_type": record.artifact_media_type,
            "artifact_encoding": record.artifact_encoding,
            "artifact_encoding_version": record.artifact_encoding_version,
            "coverage_summary_document_text": (
                record.coverage_summary_document_text
            ),
            "coverage_summary_sha256": record.coverage_summary_sha256,
            "predicted_delivery_ledger_sha256": (
                record.predicted_delivery_ledger_sha256
            ),
            "created_by_subject": record.created_by_subject,
            "created_at": record.created_at,
        }
        # Verify the record's own content hashes before writing so a builder bug
        # can never persist an internally-inconsistent immutable row.
        verify_stored_draft(record)
        # The session may already be in SQLAlchemy's autobegin state from an
        # earlier SELECT; commit/rollback the ambient transaction instead of
        # session.begin() so header and children still land atomically.
        try:
            insert_result = await session.execute(
                pg_insert(ControlPlanRun)
                .values(**header)
                .on_conflict_do_nothing()
            )
            if insert_result.rowcount == 1:
                for requirement in record.requirements:
                    await session.execute(
                        pg_insert(ControlPlanRequirement).values(
                            plan_id=record.plan_id,
                            plan_version=record.plan_version,
                            **requirement.__dict__,
                        )
                    )
                for event in record.events:
                    await session.execute(
                        pg_insert(GatePlanEventRow).values(
                            plan_id=record.plan_id,
                            plan_version=record.plan_version,
                            **event.__dict__,
                        )
                    )
                for transition in record.transitions:
                    await session.execute(
                        pg_insert(ControlStateTransition).values(
                            plan_id=record.plan_id,
                            plan_version=record.plan_version,
                            **transition.__dict__,
                        )
                    )
                for entry in record.ledger_entries:
                    await session.execute(
                        pg_insert(SectionDeliveryLedgerEntry).values(
                            **_ledger_row_values(record, entry)
                        )
                    )
                # The immutable campaign->version mapping row lands in the SAME
                # transaction as the run (its deferred FK is checked at commit), so
                # a version number is consumed ONLY when the run itself commits.
                await session.execute(
                    pg_insert(ControlPlanCampaignVersion).values(
                        campaign_id=record.campaign_id,
                        plan_version=record.plan_version,
                        plan_id=record.plan_id,
                    )
                )
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
        if insert_result.rowcount == 1:
            # The winning writer already holds the complete, self-consistent
            # record with explicit timestamps — return it directly rather than
            # re-reading, so a post-commit read failure can never turn a
            # committed draft into a spurious error.
            return record, False
        winner = await self.find_by_input_hash(
            session, record.input_content_hash
        )
        if winner is None:
            raise PlanContentConflictError(
                "insert conflicted but no row carries this input hash; a "
                "different draft already claims one of its unique keys"
            )
        # Compare canonical INPUT only, matching the sequential replay path:
        # a time-bounded solver may return a different-but-valid plan, so the
        # loser must replay the winner rather than 409 on output divergence.
        if winner.canonical_input_document_text != (
            record.canonical_input_document_text
        ):
            raise PlanContentConflictError(
                "an identical input hash is stored with different content"
            )
        return winner, True

    async def append_state_transition(
        self,
        session: AsyncSession,
        plan_id: UUID,
        plan_version: int,
        transition: "TransitionRecord",
    ) -> None:
        """Append one immutable lifecycle transition. The (plan, version,
        sequence) primary key is the concurrency backstop: a racer that computed
        the same next sequence loses with a conflict, never a double-append."""
        try:
            await session.execute(
                pg_insert(ControlStateTransition).values(
                    plan_id=plan_id,
                    plan_version=plan_version,
                    **transition.__dict__,
                )
            )
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            # Only a sequence-PK UNIQUE violation (23505) is a concurrency
            # conflict → 409. A CHECK (23514) / FK (23503) violation means the
            # service let an illegal transition through — a bug, not a race, so
            # re-raise it rather than mislabel it as concurrency.
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise TransitionConflictError(
                    "a concurrent lifecycle action already advanced this plan"
                ) from error
            raise
        except BaseException:
            await session.rollback()
            raise

    async def insert_activation(
        self,
        session: AsyncSession,
        *,
        plan_id: UUID,
        plan_version: int,
        transition: "TransitionRecord",
        outbox_rows: "list[OutboxRow]",
        scope_rows: "list[ScopeRow]",
    ) -> None:
        """Atomically append the shadow_activated transition, insert the
        command-intent outbox rows, and take the one-per-scope authority mutex — all
        in ONE txn. The transition (plan, version, sequence) PK is the lifecycle
        concurrency backstop (409); the mutex (section, gate) PK is the one-per-scope
        lock — a conflict there means another active plan already owns the scope
        (409). Scope rows insert in deterministic (section, gate) order so concurrent
        activations over intersecting scopes cannot deadlock.

        Takes the global RECOVERY_LOCK_ID advisory lock FIRST (as does every other
        mutex writer and restart recovery) so a boot-time reconcile can never read
        the transition truth and the mutex across a concurrent activation/release —
        i.e. it can never resurrect or drop an authority row mid-flight."""
        try:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": RECOVERY_LOCK_ID},
            )
            await session.execute(
                pg_insert(ControlStateTransition).values(
                    plan_id=plan_id, plan_version=plan_version, **transition.__dict__
                )
            )
            for row in outbox_rows:
                await session.execute(
                    pg_insert(ControlCommandOutboxRow).values(
                        plan_id=plan_id, plan_version=plan_version, **row.__dict__
                    )
                )
            for scope in sorted(scope_rows, key=lambda s: (s.section_id, s.gate_id)):
                await session.execute(
                    pg_insert(ControlActiveGateAuthority).values(
                        plan_id=plan_id, plan_version=plan_version, **scope.__dict__
                    )
                )
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            if _violated_constraint(error) == "control_active_gate_authority_pkey":
                raise ScopeConflictError(
                    "another active plan already controls one of these gates"
                ) from error
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise TransitionConflictError(
                    "a concurrent lifecycle action already advanced this plan"
                ) from error
            raise
        except BaseException:
            await session.rollback()
            raise

    async def append_transition_and_release_scope(
        self,
        session: AsyncSession,
        *,
        plan_id: UUID,
        plan_version: int,
        transition: "TransitionRecord",
    ) -> None:
        """Atomically append a terminal transition FROM shadow_active (emergency
        invalidate) AND release this plan's authority-mutex rows, so leaving
        shadow_active never orphans the scope.

        Takes the global RECOVERY_LOCK_ID advisory lock FIRST (same lock activation
        and restart recovery take) so a concurrent boot-time reconcile cannot
        observe this release half-applied and resurrect the freed authority row."""
        await self._release_scope_on_transition(
            session, plan_id, plan_version, transition
        )

    async def _release_scope_on_transition(
        self,
        session: AsyncSession,
        plan_id: UUID,
        plan_version: int,
        transition: "TransitionRecord",
        *,
        pre_insert_rows: "tuple[ExecutionEventRow, ...]" = (),
    ) -> None:
        """The shared atomic core of every exit from shadow_active: under
        RECOVERY_LOCK_ID, insert any ``pre_insert_rows`` (execution events), append the
        terminal transition, and delete the authority mutex — committing once. A 23505
        (transition PK, or a terminal-event partial-index conflict from a concurrent
        claim) becomes TransitionConflictError. Used by the emergency-invalidate
        release path and the missed-deadline cascade so neither forks the algorithm."""
        try:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": RECOVERY_LOCK_ID},
            )
            for row in pre_insert_rows:
                await session.execute(
                    pg_insert(ControlCommandExecutionEvent).values(
                        plan_id=plan_id, plan_version=plan_version, **row.__dict__
                    )
                )
            await session.execute(
                pg_insert(ControlStateTransition).values(
                    plan_id=plan_id, plan_version=plan_version, **transition.__dict__
                )
            )
            await session.execute(
                delete(ControlActiveGateAuthority).where(
                    ControlActiveGateAuthority.plan_id == plan_id,
                    ControlActiveGateAuthority.plan_version == plan_version,
                )
            )
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise TransitionConflictError(
                    "a concurrent lifecycle action already advanced this plan"
                ) from error
            raise
        except BaseException:
            await session.rollback()
            raise

    async def load_command_outbox(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> list:
        rows = await session.scalars(
            select(ControlCommandOutboxRow)
            .where(
                ControlCommandOutboxRow.plan_id == plan_id,
                ControlCommandOutboxRow.plan_version == plan_version,
            )
            .order_by(ControlCommandOutboxRow.event_sequence)
        )
        return list(rows)

    async def load_active_scopes(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> list:
        rows = await session.scalars(
            select(ControlActiveGateAuthority).where(
                ControlActiveGateAuthority.plan_id == plan_id,
                ControlActiveGateAuthority.plan_version == plan_version,
            )
        )
        return list(rows)

    async def acquire_recovery_lock(self, session: AsyncSession) -> None:
        """First statement of the recovery txn: the fixed global advisory lock that
        EVERY mutex writer (``insert_activation`` / ``append_transition_and_release_
        scope``) also takes. While recovery holds it no activation or release can
        commit, so ``load_recovery_plans`` reads the transition truth and the mutex
        with zero concurrent mutation — closing the stale-snapshot resurrection race.
        Held until the recovery txn commits (in ``reconcile_active_gate_authority``).
        """
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": RECOVERY_LOCK_ID}
        )

    async def load_recovery_plans(self, session: AsyncSession) -> "list[RecoveryPlan]":
        """Bounded scan for restart recovery (PR 5.2a). Loads the plans recovery must
        classify: those that are PLAUSIBLY-ACTIVE (carry a ``shadow_activated``
        transition and NO terminal ``to_state``) PLUS the holders of every current
        mutex row (so terminal orphans are classified for deletion). Each is returned
        with its FULL transition history and scheduled ``(section_id, gate_id)`` scope
        pairs. The set is bounded by live plans + mutex size, not by all history.
        MUST run after ``acquire_recovery_lock`` in the same txn."""
        activated = {
            (row.plan_id, row.plan_version)
            for row in await session.execute(
                select(
                    ControlStateTransition.plan_id,
                    ControlStateTransition.plan_version,
                )
                .where(
                    ControlStateTransition.transition_type
                    == ACTIVATION_TRANSITION_TYPE
                )
                .distinct()
            )
        }
        if not activated:
            return []
        terminated = {
            (row.plan_id, row.plan_version)
            for row in await session.execute(
                select(
                    ControlStateTransition.plan_id,
                    ControlStateTransition.plan_version,
                )
                .where(ControlStateTransition.to_state.in_(sorted(TERMINAL_STATES)))
                .distinct()
            )
        }
        holders = {
            (row.plan_id, row.plan_version)
            for row in await session.execute(
                select(
                    ControlActiveGateAuthority.plan_id,
                    ControlActiveGateAuthority.plan_version,
                ).distinct()
            )
        }
        # Plausibly-active plans (for rebuild) + every current mutex holder (so a
        # terminal orphan is loaded and classified for deletion).
        candidates = sorted((activated - terminated) | holders)
        if not candidates:
            return []
        key_tuple = tuple_(
            ControlStateTransition.plan_id, ControlStateTransition.plan_version
        )
        transition_rows = await session.scalars(
            select(ControlStateTransition)
            .where(key_tuple.in_(candidates))
            .order_by(
                ControlStateTransition.plan_id,
                ControlStateTransition.plan_version,
                ControlStateTransition.transition_sequence,
            )
        )
        transitions_by_key: dict = {}
        for row in transition_rows:
            transitions_by_key.setdefault(
                (row.plan_id, row.plan_version), []
            ).append(row)
        requirement_key_tuple = tuple_(
            ControlPlanRequirement.plan_id, ControlPlanRequirement.plan_version
        )
        scope_rows = await session.execute(
            select(
                ControlPlanRequirement.plan_id,
                ControlPlanRequirement.plan_version,
                ControlPlanRequirement.section_id,
                ControlPlanRequirement.gate_id,
            ).where(
                requirement_key_tuple.in_(candidates),
                ControlPlanRequirement.planning_disposition == "scheduled",
            )
        )
        scopes_by_key: dict = {}
        for row in scope_rows:
            scopes_by_key.setdefault((row.plan_id, row.plan_version), set()).add(
                (row.section_id, row.gate_id)
            )
        return [
            RecoveryPlan(
                plan_id=plan_id,
                plan_version=plan_version,
                transitions=transitions_by_key.get((plan_id, plan_version), []),
                scope_pairs=frozenset(
                    scopes_by_key.get((plan_id, plan_version), set())
                ),
            )
            for (plan_id, plan_version) in candidates
        ]

    async def reconcile_active_gate_authority(
        self,
        session: AsyncSession,
        *,
        expected: "set[ExpectedScope]",
        terminal_keys: "set[tuple[UUID, int]]",
    ) -> "RecoveryReport":
        """Self-heal the MUTABLE authority mutex to equal the append-only truth
        (PR 5.2a). Runs inside the recovery txn AFTER ``acquire_recovery_lock``, so
        no mutex writer can interleave. DELETE terminal orphans FIRST (one batched
        statement) so a scope can transfer from a terminal holder to an active plan
        in the SAME pass, THEN INSERT any missing expected row with ``ON CONFLICT DO
        NOTHING``. Deletes only rows whose holder is POSITIVELY terminal (never a
        live ``shadow_active`` row); the (section, gate) PK makes each pair identify
        exactly one row. Idempotent — a no-op when the mutex already matches."""
        try:
            current = list(
                await session.scalars(select(ControlActiveGateAuthority))
            )
            orphan_pairs = [
                (row.section_id, row.gate_id)
                for row in current
                if (row.plan_id, row.plan_version) in terminal_keys
            ]
            deleted = 0
            if orphan_pairs:
                result = await session.execute(
                    delete(ControlActiveGateAuthority).where(
                        tuple_(
                            ControlActiveGateAuthority.section_id,
                            ControlActiveGateAuthority.gate_id,
                        ).in_(orphan_pairs)
                    )
                )
                deleted = result.rowcount or 0
            occupied = {
                (row.section_id, row.gate_id) for row in current
            } - set(orphan_pairs)
            inserted = 0
            for scope in sorted(
                expected, key=lambda s: (s.section_id, s.gate_id)
            ):
                if (scope.section_id, scope.gate_id) in occupied:
                    continue
                result = await session.execute(
                    pg_insert(ControlActiveGateAuthority)
                    .values(
                        section_id=scope.section_id,
                        gate_id=scope.gate_id,
                        plan_id=scope.plan_id,
                        plan_version=scope.plan_version,
                        activation_transition_sequence=(
                            scope.activation_transition_sequence
                        ),
                    )
                    .on_conflict_do_nothing(
                        index_elements=["section_id", "gate_id"]
                    )
                )
                inserted += result.rowcount or 0
            await session.commit()
            return RecoveryReport(
                inserted=inserted, deleted=deleted, checked=len(current)
            )
        except BaseException:
            await session.rollback()
            raise

    async def load_open_loop_context(
        self, session: AsyncSession, plan_id: UUID, plan_version: int
    ) -> "OpenLoopContext":
        """Load the plan slice a worker tick needs (PR 5.2b): full transition history,
        outbox intents ordered by the global ``event_sequence``, execution events, and
        the authority row's ``granted_at``."""
        transitions = list(
            await session.scalars(
                select(ControlStateTransition)
                .where(
                    ControlStateTransition.plan_id == plan_id,
                    ControlStateTransition.plan_version == plan_version,
                )
                .order_by(ControlStateTransition.transition_sequence)
            )
        )
        outbox = list(
            await session.scalars(
                select(ControlCommandOutboxRow)
                .where(
                    ControlCommandOutboxRow.plan_id == plan_id,
                    ControlCommandOutboxRow.plan_version == plan_version,
                )
                .order_by(ControlCommandOutboxRow.event_sequence)
            )
        )
        events = list(
            await session.scalars(
                select(ControlCommandExecutionEvent).where(
                    ControlCommandExecutionEvent.plan_id == plan_id,
                    ControlCommandExecutionEvent.plan_version == plan_version,
                )
            )
        )
        granted_at = await session.scalar(
            select(ControlActiveGateAuthority.granted_at)
            .where(
                ControlActiveGateAuthority.plan_id == plan_id,
                ControlActiveGateAuthority.plan_version == plan_version,
            )
            .limit(1)
        )
        return OpenLoopContext(
            transitions=transitions,
            outbox=outbox,
            events=events,
            granted_at=granted_at,
        )

    async def append_execution_events(
        self,
        session: AsyncSession,
        plan_id: UUID,
        plan_version: int,
        rows: "list[ExecutionEventRow]",
        *,
        ignore_conflicts: bool = False,
    ) -> "list[UUID]":
        """Append execution events in ONE multi-row insert (PR 5.2b). With
        ``ignore_conflicts`` a row whose intent already holds a terminal event is
        skipped via ON CONFLICT DO NOTHING on the one-terminal-per-intent partial
        index — so claim is idempotent AND a claim that races a committed invalidate
        simply no-ops (never a contradictory pair). Returns the intent_ids ACTUALLY
        inserted (via RETURNING), so the caller reports only intents it truly claimed —
        never merely attempted. Plan-level rows (intent_id NULL) return no id."""
        if not rows:
            return []
        try:
            statement = pg_insert(ControlCommandExecutionEvent).values(
                [
                    {"plan_id": plan_id, "plan_version": plan_version, **row.__dict__}
                    for row in rows
                ]
            )
            if ignore_conflicts:
                statement = statement.on_conflict_do_nothing(
                    index_elements=["intent_id"],
                    index_where=text(
                        "event_type IN ('claimed', 'missed', 'invalidated')"
                    ),
                )
            statement = statement.returning(ControlCommandExecutionEvent.intent_id)
            result = await session.execute(statement)
            inserted = [iid for iid in result.scalars().all() if iid is not None]
            await session.commit()
            return inserted
        except BaseException:
            await session.rollback()
            raise

    async def record_missed_and_invalidate(
        self,
        session: AsyncSession,
        plan_id: UUID,
        plan_version: int,
        *,
        event_rows: "list[ExecutionEventRow]",
        transition: "TransitionRecord",
    ) -> None:
        """Atomically record a missed-deadline break (PR 5.2b): append the missed +
        invalidated execution events, append the ``invalidated`` lifecycle transition,
        and release the authority mutex — all in ONE txn under RECOVERY_LOCK_ID via the
        SHARED release core (no forked algorithm). A released scope can never be
        resurrected; the transition PK (or a terminal-event partial-index conflict from
        a concurrent claim) surfaces as TransitionConflictError."""
        await self._release_scope_on_transition(
            session,
            plan_id,
            plan_version,
            transition,
            pre_insert_rows=tuple(event_rows),
        )

    async def _assemble(
        self, session: AsyncSession, run: ControlPlanRun
    ) -> DraftPlanRecord:
        # Every persisted run has exactly one immutable campaign mapping row
        # (backfilled for legacy rows, inserted atomically for fresh drafts). A
        # missing mapping is corruption, not a legitimate state -> fail closed.
        campaign_id = await session.scalar(
            select(ControlPlanCampaignVersion.campaign_id).where(
                ControlPlanCampaignVersion.plan_id == run.plan_id,
                ControlPlanCampaignVersion.plan_version == run.plan_version,
            )
        )
        if campaign_id is None:
            raise DraftStoreCorruptError(
                f"control plan {run.plan_id} v{run.plan_version} has no campaign "
                "mapping row"
            )
        requirement_rows = (
            await session.scalars(
                select(ControlPlanRequirement)
                .where(
                    ControlPlanRequirement.plan_id == run.plan_id,
                    ControlPlanRequirement.plan_version == run.plan_version,
                )
                .order_by(ControlPlanRequirement.requirement_id)
            )
        ).all()
        event_rows = (
            await session.scalars(
                select(GatePlanEventRow)
                .where(
                    GatePlanEventRow.plan_id == run.plan_id,
                    GatePlanEventRow.plan_version == run.plan_version,
                )
                .order_by(GatePlanEventRow.event_sequence)
            )
        ).all()
        transition_rows = (
            await session.scalars(
                select(ControlStateTransition)
                .where(
                    ControlStateTransition.plan_id == run.plan_id,
                    ControlStateTransition.plan_version == run.plan_version,
                )
                .order_by(ControlStateTransition.transition_sequence)
            )
        ).all()
        ledger_rows = (
            await session.scalars(
                select(SectionDeliveryLedgerEntry)
                .where(
                    SectionDeliveryLedgerEntry.plan_id == run.plan_id,
                    SectionDeliveryLedgerEntry.plan_version == run.plan_version,
                )
                .order_by(
                    SectionDeliveryLedgerEntry.requirement_id,
                    SectionDeliveryLedgerEntry.checkpoint_index,
                )
            )
        ).all()
        record = DraftPlanRecord(
            plan_id=run.plan_id,
            plan_version=run.plan_version,
            campaign_id=campaign_id,
            identity_version=run.identity_version,
            input_content_hash=run.input_content_hash,
            draft_content_hash=run.draft_content_hash,
            lifecycle_state=run.lifecycle_state,
            optimizer_status=run.optimizer_status,
            prediction_status=run.prediction_status,
            requirement_run_id=run.requirement_run_id,
            requirement_version=run.requirement_version,
            model_snapshot_id=run.model_snapshot_id,
            model_release_id=run.model_release_id,
            model_release_content_hash=run.model_release_content_hash,
            prediction_run_id=run.prediction_run_id,
            prediction_member_summaries=run.prediction_member_summaries,
            horizon_start=run.horizon_start,
            horizon_end=run.horizon_end,
            model_step_seconds=run.model_step_seconds,
            max_intermediate_trims=run.max_intermediate_trims,
            canonical_input_document_text=run.canonical_input_document_text,
            model_snapshot_document_text=run.model_snapshot_document_text,
            optimizer_result_document_text=(
                run.optimizer_result_document_text
            ),
            optimizer_result_sha256=run.optimizer_result_sha256,
            prediction_request_document_text=(
                run.prediction_request_document_text
            ),
            prediction_response_document_text=(
                run.prediction_response_document_text
            ),
            prediction_response_sha256=run.prediction_response_sha256,
            provenance_version=run.provenance_version,
            prediction_identity_version=run.prediction_identity_version,
            engine_id=run.engine_id,
            engine_semantic_contract_version=(
                run.engine_semantic_contract_version
            ),
            engine_build_digest=run.engine_build_digest,
            engine_descriptor_content_hash=run.engine_descriptor_content_hash,
            artifact_sha256=run.artifact_sha256,
            artifact_uncompressed_size_bytes=(
                run.artifact_uncompressed_size_bytes
            ),
            artifact_media_type=run.artifact_media_type,
            artifact_encoding=run.artifact_encoding,
            artifact_encoding_version=run.artifact_encoding_version,
            coverage_summary_document_text=run.coverage_summary_document_text,
            coverage_summary_sha256=run.coverage_summary_sha256,
            predicted_delivery_ledger_sha256=(
                run.predicted_delivery_ledger_sha256
            ),
            created_by_subject=run.created_by_subject,
            requirements=tuple(
                RequirementRecord(
                    requirement_id=row.requirement_id,
                    run_id=row.run_id,
                    source_version=row.source_version,
                    service_date=row.service_date,
                    section_id=row.section_id,
                    zone=row.zone,
                    required_volume_m3=row.required_volume_m3,
                    window_start=row.window_start,
                    window_end=row.window_end,
                    quality=row.quality,
                    published_at=row.published_at,
                    as_of_date=row.as_of_date,
                    source_data_status=row.source_data_status,
                    planning_disposition=row.planning_disposition,
                    delivery_node_id=row.delivery_node_id,
                    gate_id=row.gate_id,
                    maximum_delivery_m3s=row.maximum_delivery_m3s,
                    approved_excess_m3=row.approved_excess_m3,
                    travel_delay_seconds=row.travel_delay_seconds,
                    minimum_delivery_fraction=row.minimum_delivery_fraction,
                    maximum_delivery_fraction=row.maximum_delivery_fraction,
                    path_reach_ids_document_text=(
                        row.path_reach_ids_document_text
                    ),
                    rotation_windows_document_text=(
                        row.rotation_windows_document_text
                    ),
                    requirement_document_text=row.requirement_document_text,
                )
                for row in requirement_rows
            ),
            events=tuple(
                GateEventRecord(
                    event_sequence=row.event_sequence,
                    gate_event_sequence=row.gate_event_sequence,
                    gate_id=row.gate_id,
                    event_kind=row.event_kind,
                    planned_at=row.planned_at,
                    target_position_m=row.target_position_m,
                    source_flow_m3s=row.source_flow_m3s,
                    trim_ordinal=row.trim_ordinal,
                )
                for row in event_rows
            ),
            transitions=tuple(
                TransitionRecord(
                    transition_sequence=row.transition_sequence,
                    transition_type=row.transition_type,
                    from_state=row.from_state,
                    to_state=row.to_state,
                    actor_subject=row.actor_subject,
                    reason=row.reason,
                    transition_document_text=row.transition_document_text,
                    occurred_at=row.occurred_at,
                )
                for row in transition_rows
            ),
            ledger_entries=tuple(
                LedgerEntry(
                    requirement_id=str(row.requirement_id),
                    section_id=row.section_id,
                    checkpoint_index=row.checkpoint_index,
                    checkpoint_at=row.checkpoint_at,
                    status=row.status,
                    required_volume_m3=row.required_volume_m3,
                    approved_excess_m3=row.approved_excess_m3,
                    lower_delivered_m3=row.lower_delivered_m3,
                    nominal_delivered_m3=row.nominal_delivered_m3,
                    upper_delivered_m3=row.upper_delivered_m3,
                    lower_path_in_transit_m3=row.lower_path_in_transit_m3,
                    nominal_path_in_transit_m3=row.nominal_path_in_transit_m3,
                    upper_path_in_transit_m3=row.upper_path_in_transit_m3,
                    checkpoint_reasons=tuple(
                        json.loads(row.checkpoint_reasons_document_text)
                    ),
                    prediction_run_id=row.prediction_run_id,
                    prediction_response_sha256=row.prediction_response_sha256,
                    projection_sha256=row.projection_sha256,
                    projection_document_text=row.projection_document_text,
                )
                for row in ledger_rows
            ),
            created_at=run.created_at,
        )
        verify_stored_draft(record)
        return record


def _ledger_row_values(
    record: DraftPlanRecord, entry: LedgerEntry
) -> dict:
    return {
        "plan_id": record.plan_id,
        "plan_version": record.plan_version,
        "requirement_id": UUID(entry.requirement_id),
        "checkpoint_index": entry.checkpoint_index,
        "section_id": entry.section_id,
        "checkpoint_at": entry.checkpoint_at,
        "status": entry.status,
        "required_volume_m3": entry.required_volume_m3,
        "approved_excess_m3": entry.approved_excess_m3,
        "lower_delivered_m3": entry.lower_delivered_m3,
        "nominal_delivered_m3": entry.nominal_delivered_m3,
        "upper_delivered_m3": entry.upper_delivered_m3,
        "lower_path_in_transit_m3": entry.lower_path_in_transit_m3,
        "nominal_path_in_transit_m3": entry.nominal_path_in_transit_m3,
        "upper_path_in_transit_m3": entry.upper_path_in_transit_m3,
        "checkpoint_reasons_document_text": json.dumps(
            list(entry.checkpoint_reasons), separators=(",", ":")
        ),
        "projection_document_text": entry.projection_document_text,
        "projection_sha256": entry.projection_sha256,
        # The entry's OWN lineage (equal to the record's for a v1 draft; the
        # artifact sha256 for a v2 draft, whose header prediction_response_sha256
        # column is NULL) — the value that the row's content hash covers.
        "prediction_run_id": entry.prediction_run_id,
        "prediction_response_sha256": entry.prediction_response_sha256,
        "projected_at": record.created_at,
    }


def with_created_at(
    record: DraftPlanRecord, created_at: datetime
) -> DraftPlanRecord:
    return replace(record, created_at=created_at)
