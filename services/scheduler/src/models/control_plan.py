"""Control-plan draft ORM models (PR 4.3a).

These tables attach to ControlBase ONLY and are created exclusively by the
checksum migration runner (0001_control_plan_drafts). They must never be
imported by models/__init__.py, main.py, or core/database.py — the legacy
create_all path must not see them (tests/unit/test_create_all_isolation.py).
Rows are immutable: DB triggers reject UPDATE and DELETE on all four tables.
"""

from sqlalchemy import (
    CHAR,
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from .control_base import ControlBase

SCHEMA = "scheduler"


class ControlPlanRun(ControlBase):
    __tablename__ = "control_plan_runs"
    __table_args__ = (
        UniqueConstraint("input_content_hash"),
        UniqueConstraint("draft_content_hash"),
        {"schema": SCHEMA},
    )

    plan_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_version = Column(Integer, primary_key=True)
    identity_version = Column(SmallInteger, nullable=False, default=1)
    input_content_hash = Column(CHAR(64), nullable=False)
    draft_content_hash = Column(CHAR(64), nullable=False)
    lifecycle_state = Column(String, nullable=False, default="draft")
    optimizer_status = Column(String, nullable=False)
    prediction_status = Column(String, nullable=False)
    requirement_run_id = Column(UUID(as_uuid=True), nullable=False)
    requirement_version = Column(Integer, nullable=False)
    model_snapshot_id = Column(CHAR(64), nullable=False)
    model_release_id = Column(Text, nullable=False)
    model_release_content_hash = Column(CHAR(64), nullable=False)
    prediction_run_id = Column(CHAR(64), nullable=True)
    prediction_member_summaries = Column(Text, nullable=True)
    horizon_start = Column(DateTime(timezone=True), nullable=False)
    horizon_end = Column(DateTime(timezone=True), nullable=False)
    model_step_seconds = Column(Integer, nullable=False)
    max_intermediate_trims = Column(SmallInteger, nullable=False)
    canonical_input_document_text = Column(Text, nullable=False)
    model_snapshot_document_text = Column(Text, nullable=False)
    optimizer_result_document_text = Column(Text, nullable=False)
    optimizer_result_sha256 = Column(CHAR(64), nullable=False)
    prediction_request_document_text = Column(Text, nullable=True)
    prediction_response_document_text = Column(Text, nullable=True)
    prediction_response_sha256 = Column(CHAR(64), nullable=True)
    # Provenance v2 (PR 4.4b-2): a feasible draft stores a BOUNDED artifact
    # reference (engine pins + artifact sha/size/media + summary/ledger hashes)
    # instead of copying the full prediction response. All NULL on a v1 row.
    provenance_version = Column(SmallInteger, nullable=True)
    prediction_identity_version = Column(SmallInteger, nullable=True)
    engine_id = Column(Text, nullable=True)
    engine_semantic_contract_version = Column(Integer, nullable=True)
    engine_build_digest = Column(CHAR(64), nullable=True)
    engine_descriptor_content_hash = Column(CHAR(64), nullable=True)
    artifact_sha256 = Column(CHAR(64), nullable=True)
    artifact_uncompressed_size_bytes = Column(BigInteger, nullable=True)
    artifact_media_type = Column(Text, nullable=True)
    artifact_encoding = Column(Text, nullable=True)
    artifact_encoding_version = Column(Integer, nullable=True)
    coverage_summary_document_text = Column(Text, nullable=True)
    coverage_summary_sha256 = Column(CHAR(64), nullable=True)
    predicted_delivery_ledger_sha256 = Column(CHAR(64), nullable=True)
    created_by_subject = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ControlPlanRequirement(ControlBase):
    __tablename__ = "control_plan_requirements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("plan_id", "plan_version", "service_date", "section_id"),
        {"schema": SCHEMA},
    )

    plan_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_version = Column(Integer, primary_key=True)
    requirement_id = Column(UUID(as_uuid=True), primary_key=True)
    run_id = Column(UUID(as_uuid=True), nullable=False)
    source_version = Column(Integer, nullable=False)
    service_date = Column(Date, nullable=False)
    section_id = Column(Text, nullable=False)
    zone = Column(SmallInteger, nullable=False)
    required_volume_m3 = Column(Float(53), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    quality = Column(String, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)
    as_of_date = Column(Date, nullable=False)
    source_data_status = Column(String, nullable=False)
    planning_disposition = Column(String, nullable=False)
    delivery_node_id = Column(Text, nullable=True)
    gate_id = Column(Text, nullable=True)
    maximum_delivery_m3s = Column(Float(53), nullable=True)
    approved_excess_m3 = Column(Float(53), nullable=True)
    travel_delay_seconds = Column(Integer, nullable=True)
    minimum_delivery_fraction = Column(Float(53), nullable=True)
    maximum_delivery_fraction = Column(Float(53), nullable=True)
    path_reach_ids_document_text = Column(Text, nullable=True)
    rotation_windows_document_text = Column(Text, nullable=True)
    requirement_document_text = Column(Text, nullable=False)


class GatePlanEventRow(ControlBase):
    __tablename__ = "gate_plan_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("plan_id", "plan_version", "gate_id",
                         "gate_event_sequence"),
        UniqueConstraint("plan_id", "plan_version", "gate_id", "planned_at"),
        {"schema": SCHEMA},
    )

    plan_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_version = Column(Integer, primary_key=True)
    event_sequence = Column(Integer, primary_key=True)
    gate_event_sequence = Column(Integer, nullable=False)
    gate_id = Column(Text, nullable=False)
    event_kind = Column(String, nullable=False)
    planned_at = Column(DateTime(timezone=True), nullable=False)
    target_position_m = Column(Float(53), nullable=False)
    source_flow_m3s = Column(Float(53), nullable=False)
    trim_ordinal = Column(SmallInteger, nullable=True)


class ControlStateTransition(ControlBase):
    __tablename__ = "control_state_transitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        {"schema": SCHEMA},
    )

    plan_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_version = Column(Integer, primary_key=True)
    transition_sequence = Column(Integer, primary_key=True)
    transition_type = Column(String, nullable=False)
    from_state = Column(String, nullable=True)
    to_state = Column(String, nullable=False)
    actor_subject = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    transition_document_text = Column(Text, nullable=True)
    occurred_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ControlPlanCampaignVersion(ControlBase):
    """Immutable campaign_id -> monotonic plan_version mapping (PR 4.4b-4).

    One row per persisted control-plan version. A campaign carries an append-only
    chain of versions under a single stable ``campaign_id``; ``plan_id`` stays a
    fresh per-version uuid (so every version keeps its own immutable run + FKs).
    The composite FK to ``control_plan_runs`` is DEFERRABLE INITIALLY DEFERRED so
    the run row and this mapping row commit atomically. Rows are immutable (a DB
    trigger rejects UPDATE and DELETE)."""

    __tablename__ = "control_plan_campaign_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint("plan_id", "plan_version"),
        {"schema": SCHEMA},
    )

    campaign_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_version = Column(Integer, primary_key=True)
    plan_id = Column(UUID(as_uuid=True), nullable=False)


class SectionDeliveryLedgerEntry(ControlBase):
    """Append-only projection of a feasible draft's prediction (PR 5.1)."""

    __tablename__ = "section_delivery_ledger"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version", "requirement_id"],
            [f"{SCHEMA}.control_plan_requirements.plan_id",
             f"{SCHEMA}.control_plan_requirements.plan_version",
             f"{SCHEMA}.control_plan_requirements.requirement_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("plan_id", "plan_version", "requirement_id",
                         "checkpoint_at"),
        UniqueConstraint("plan_id", "plan_version", "projection_sha256"),
        {"schema": SCHEMA},
    )

    plan_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_version = Column(Integer, primary_key=True)
    requirement_id = Column(UUID(as_uuid=True), primary_key=True)
    checkpoint_index = Column(Integer, primary_key=True)
    ledger_schema_version = Column(SmallInteger, nullable=False, default=1)
    section_id = Column(Text, nullable=False)
    checkpoint_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    required_volume_m3 = Column(Float(53), nullable=False)
    approved_excess_m3 = Column(Float(53), nullable=False)
    lower_delivered_m3 = Column(Float(53), nullable=True)
    nominal_delivered_m3 = Column(Float(53), nullable=True)
    upper_delivered_m3 = Column(Float(53), nullable=True)
    lower_path_in_transit_m3 = Column(Float(53), nullable=True)
    nominal_path_in_transit_m3 = Column(Float(53), nullable=True)
    upper_path_in_transit_m3 = Column(Float(53), nullable=True)
    checkpoint_reasons_document_text = Column(Text, nullable=False)
    projection_document_text = Column(Text, nullable=False)
    projection_sha256 = Column(CHAR(64), nullable=False)
    prediction_run_id = Column(CHAR(64), nullable=False)
    prediction_response_sha256 = Column(CHAR(64), nullable=False)
    projected_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
