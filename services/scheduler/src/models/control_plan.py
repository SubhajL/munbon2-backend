"""Control-plan draft ORM models (PR 4.3a).

These tables attach to ControlBase ONLY and are created exclusively by the
checksum migration runner (0001 onward). They must never be imported by
models/__init__.py, main.py, or core/database.py — the legacy create_all path
must not see them (tests/unit/test_create_all_isolation.py). Every table is
append-only (DB triggers reject UPDATE and DELETE) EXCEPT
control_active_gate_authority (PR 4.3c-1), a mutable materialized
current-authority index that is INSERTed on activation and DELETEd on exit.
"""

from sqlalchemy import (
    CHAR,
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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


class ControlCommandOutboxRow(ControlBase):
    """Append-only shadow command-intent outbox (PR 4.3c-1).

    One row per compiled CommandIntent; written atomically with the
    ``shadow_activated`` transition. Rows are immutable (DB trigger). 6.2 reads
    these and produces validation receipts; nothing here dispatches or actuates.
    """

    __tablename__ = "control_command_outbox"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("idempotency_key"),
        UniqueConstraint("plan_id", "plan_version", "event_sequence"),
        {"schema": SCHEMA},
    )

    intent_id = Column(UUID(as_uuid=True), primary_key=True)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    request_id = Column(Text, nullable=False)
    idempotency_key = Column(Text, nullable=False)
    canonical_gate_id = Column(Text, nullable=False)
    event_kind = Column(String, nullable=False)
    event_sequence = Column(Integer, nullable=False)
    gate_event_sequence = Column(Integer, nullable=False)
    device_id = Column(Text, nullable=False)
    adapter_gate_id = Column(Text, nullable=False)
    capability_release_id = Column(Text, nullable=False)
    capability_hash = Column(CHAR(64), nullable=False)
    target_position_m = Column(Float(53), nullable=False)
    target_level = Column(Integer, nullable=False)
    not_before = Column(DateTime(timezone=True), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=False)
    mode = Column(String, nullable=False)
    intent_document_text = Column(Text, nullable=False)
    intent_content_hash = Column(CHAR(64), nullable=False)
    plan_id = Column(UUID(as_uuid=True), nullable=False)
    plan_version = Column(Integer, nullable=False)
    activation_transition_sequence = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ControlActiveGateAuthority(ControlBase):
    """MUTABLE one-per-scope authority mutex (PR 4.3c-1).

    A materialized current-authority index (NOT the audit authority — the
    append-only transitions remain that). The (section_id, gate_id) PK is the
    DB-level one-per-scope lock. Rows are INSERTed on activation and DELETEd when
    the holder leaves shadow_active, so — uniquely among control tables — this
    table has NO immutability trigger (see the drift test's documented exemption).
    """

    __tablename__ = "control_active_gate_authority"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        {"schema": SCHEMA},
    )

    section_id = Column(Text, primary_key=True)
    gate_id = Column(Text, primary_key=True)
    plan_id = Column(UUID(as_uuid=True), nullable=False)
    plan_version = Column(Integer, nullable=False)
    activation_transition_sequence = Column(Integer, nullable=False)
    granted_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ControlCommandExecutionEvent(ControlBase):
    """Append-only open-loop execution audit log (PR 5.2b).

    One row per execution-state change of a command-intent (``claimed`` / ``missed``
    / ``invalidated``) plus plan-level operator events (``held`` / ``resumed``,
    ``intent_id`` NULL). Rows are immutable (DB trigger). The per-intent execution
    state is DERIVED from these events; the plan lifecycle stays event-sourced in
    ``control_state_transitions``. Nothing here dispatches or actuates.
    """

    __tablename__ = "control_command_execution_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        # No FK on intent_id to control_command_outbox: kept additively independent
        # of the 0007 migration; the partial unique index below backstops claims.
        # At most ONE terminal event per intent (claimed | missed | invalidated) so a
        # concurrent claim + invalidate for the same intent can never both land;
        # plan-level held/resumed (intent_id NULL) are excluded and may repeat.
        Index(
            "control_command_execution_events_one_terminal_per_intent",
            "intent_id",
            unique=True,
            postgresql_where=text(
                "event_type IN ('claimed', 'missed', 'invalidated')"
            ),
        ),
        {"schema": SCHEMA},
    )

    event_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_id = Column(UUID(as_uuid=True), nullable=False)
    plan_version = Column(Integer, nullable=False)
    intent_id = Column(UUID(as_uuid=True), nullable=True)
    event_type = Column(String, nullable=False)
    worker_id = Column(Text, nullable=True)
    detail_document_text = Column(Text, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ControlCommandValidationReceipt(ControlBase):
    """Append-only durable ValidationReceipt store (PR 6.3a).

    One row per command-intent (``intent_id`` PK) recording the SCADA 6.0
    ValidationReceipt the shadow dispatcher got back from the machine-boundary
    validate endpoint — so an at-least-once dispatch is an exactly-once persisted
    effect (a retried dispatch replays SCADA's byte-identical receipt and the second
    INSERT ... ON CONFLICT (intent_id) DO NOTHING no-ops). Rows are immutable (DB
    trigger). Nothing here dispatches or actuates — this is the durable audit of a
    validation-only round-trip.
    """

    __tablename__ = "control_command_validation_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        # Second exactly-once backstop mirroring the 0007 outbox + the SCADA receipt
        # store: the same idempotency_key can never file two receipts.
        UniqueConstraint(
            "idempotency_key",
            name="control_command_validation_receipts_idem",
        ),
        {"schema": SCHEMA},
    )

    intent_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_id = Column(UUID(as_uuid=True), nullable=False)
    plan_version = Column(Integer, nullable=False)
    receipt_id = Column(UUID(as_uuid=True), nullable=False)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    request_id = Column(Text, nullable=False)
    idempotency_key = Column(Text, nullable=False)
    intent_content_hash = Column(CHAR(64), nullable=False)
    capability_hash = Column(CHAR(64), nullable=False)
    status = Column(Text, nullable=False)
    reason_code = Column(Text, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=False)
    receipt_document_text = Column(Text, nullable=False)
    receipt_content_sha256 = Column(CHAR(64), nullable=False)
    dispatch_worker_id = Column(Text, nullable=True)
    dispatched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ControlGateReadbackObservation(ControlBase):
    """Append-only shadow readback-reconciliation audit (PR 6.3b).

    One row per (plan, gate) reconcile: the observed vs expected(baseline) level, the reading
    quality, the verdict (ok/mismatch/unavailable), and the mode it ran in. The hold-on-drift
    decision (a plan-level ``held`` execution event) is recorded in 0009; this is its evidence.
    Rows are immutable (DB trigger). Nothing here actuates.
    """

    __tablename__ = "control_gate_readback_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_version"],
            [f"{SCHEMA}.control_plan_runs.plan_id",
             f"{SCHEMA}.control_plan_runs.plan_version"],
            ondelete="RESTRICT",
        ),
        {"schema": SCHEMA},
    )

    observation_id = Column(UUID(as_uuid=True), primary_key=True)
    plan_id = Column(UUID(as_uuid=True), nullable=False)
    plan_version = Column(Integer, nullable=False)
    canonical_gate_id = Column(Text, nullable=False)
    observed_level = Column(Integer, nullable=True)
    expected_level = Column(Integer, nullable=False)
    quality = Column(Text, nullable=False)
    verdict = Column(Text, nullable=False)
    reconciliation_mode = Column(Text, nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
