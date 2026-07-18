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
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.control_plan import (
    control_plan_draft_hash,
    control_plan_input_hash,
)
from models.control_plan import (
    ControlPlanRequirement,
    ControlPlanRun,
    ControlStateTransition,
    GatePlanEventRow,
)


class ControlPlanRepositoryError(Exception):
    """Base repository failure."""


class PlanContentConflictError(ControlPlanRepositoryError):
    """Same content-addressed identity with different stored content."""


class DraftStoreCorruptError(ControlPlanRepositoryError):
    """Stored draft fails its own content-hash verification."""


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
    created_at: Optional[datetime] = None


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_stored_draft(record: DraftPlanRecord) -> None:
    """Fail closed if any stored canonical document drifted from its hash."""
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
    if record.prediction_response_document_text is not None:
        if record.prediction_response_sha256 is None or text_sha256(
            record.prediction_response_document_text
        ) != record.prediction_response_sha256:
            raise DraftStoreCorruptError(
                "stored prediction response does not match its hash"
            )
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
        "prediction_response_sha256": record.prediction_response_sha256,
    }
    if control_plan_draft_hash(draft_document) != record.draft_content_hash:
        raise DraftStoreCorruptError(
            "stored draft content does not match its draft hash"
        )


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

    async def _assemble(
        self, session: AsyncSession, run: ControlPlanRun
    ) -> DraftPlanRecord:
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
        record = DraftPlanRecord(
            plan_id=run.plan_id,
            plan_version=run.plan_version,
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
            created_at=run.created_at,
        )
        verify_stored_draft(record)
        return record


def with_created_at(
    record: DraftPlanRecord, created_at: datetime
) -> DraftPlanRecord:
    return replace(record, created_at=created_at)
