-- 0001_control_plan_drafts (PR 4.3a)
-- First control-domain migration: immutable draft control-plan storage.
-- Canonical documents are TEXT, never JSONB (jsonb normalizes -0.0 and key
-- order, which would corrupt content-addressed identity).

CREATE TABLE scheduler.control_plan_runs (
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    identity_version SMALLINT NOT NULL DEFAULT 1,
    input_content_hash CHAR(64) NOT NULL,
    draft_content_hash CHAR(64) NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'draft',
    optimizer_status TEXT NOT NULL,
    prediction_status TEXT NOT NULL,
    requirement_run_id UUID NOT NULL,
    requirement_version INTEGER NOT NULL,
    model_snapshot_id CHAR(64) NOT NULL,
    model_release_id TEXT NOT NULL,
    model_release_content_hash CHAR(64) NOT NULL,
    prediction_run_id CHAR(64),
    prediction_member_summaries TEXT,
    horizon_start TIMESTAMPTZ NOT NULL,
    horizon_end TIMESTAMPTZ NOT NULL,
    model_step_seconds INTEGER NOT NULL,
    max_intermediate_trims SMALLINT NOT NULL,
    canonical_input_document_text TEXT NOT NULL,
    model_snapshot_document_text TEXT NOT NULL,
    optimizer_result_document_text TEXT NOT NULL,
    optimizer_result_sha256 CHAR(64) NOT NULL,
    prediction_request_document_text TEXT,
    prediction_response_document_text TEXT,
    prediction_response_sha256 CHAR(64),
    created_by_subject TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_plan_runs_pkey PRIMARY KEY (plan_id, plan_version),
    CONSTRAINT control_plan_runs_input_hash_key UNIQUE (input_content_hash),
    CONSTRAINT control_plan_runs_draft_hash_key UNIQUE (draft_content_hash),
    CONSTRAINT control_plan_runs_version_positive CHECK (plan_version > 0),
    CONSTRAINT control_plan_runs_requirement_version_positive
        CHECK (requirement_version > 0),
    CONSTRAINT control_plan_runs_identity_version_positive
        CHECK (identity_version > 0),
    CONSTRAINT control_plan_runs_input_hash_shape
        CHECK (input_content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT control_plan_runs_draft_hash_shape
        CHECK (draft_content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT control_plan_runs_snapshot_shape
        CHECK (model_snapshot_id ~ '^[0-9a-f]{64}$'),
    CONSTRAINT control_plan_runs_release_hash_shape
        CHECK (model_release_content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT control_plan_runs_prediction_run_shape
        CHECK (prediction_run_id IS NULL
               OR prediction_run_id ~ '^[0-9a-f]{64}$'),
    CONSTRAINT control_plan_runs_prediction_response_shape
        CHECK (prediction_response_sha256 IS NULL
               OR prediction_response_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT control_plan_runs_optimizer_result_shape
        CHECK (optimizer_result_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT control_plan_runs_release_id_nonempty
        CHECK (length(model_release_id) > 0),
    CONSTRAINT control_plan_runs_subject_nonempty
        CHECK (length(created_by_subject) > 0),
    CONSTRAINT control_plan_runs_horizon_ordered
        CHECK (horizon_end > horizon_start),
    CONSTRAINT control_plan_runs_step_positive CHECK (model_step_seconds > 0),
    CONSTRAINT control_plan_runs_trims_bounded
        CHECK (max_intermediate_trims BETWEEN 0 AND 2),
    CONSTRAINT control_plan_runs_lifecycle_draft
        CHECK (lifecycle_state = 'draft'),
    CONSTRAINT control_plan_runs_optimizer_status
        CHECK (optimizer_status IN ('feasible', 'infeasible')),
    CONSTRAINT control_plan_runs_prediction_status
        CHECK (prediction_status IN ('not_requested', 'completed',
                                     'infeasible')),
    CONSTRAINT control_plan_runs_infeasible_has_no_prediction
        CHECK (optimizer_status <> 'infeasible'
               OR (prediction_status = 'not_requested'
                   AND prediction_run_id IS NULL
                   AND prediction_member_summaries IS NULL
                   AND prediction_request_document_text IS NULL
                   AND prediction_response_document_text IS NULL
                   AND prediction_response_sha256 IS NULL)),
    CONSTRAINT control_plan_runs_feasible_has_prediction
        CHECK (optimizer_status <> 'feasible'
               OR (prediction_status IN ('completed', 'infeasible')
                   AND prediction_run_id IS NOT NULL
                   AND prediction_member_summaries IS NOT NULL
                   AND prediction_request_document_text IS NOT NULL
                   AND prediction_response_document_text IS NOT NULL
                   AND prediction_response_sha256 IS NOT NULL))
);

CREATE TABLE scheduler.control_plan_requirements (
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    requirement_id UUID NOT NULL,
    run_id UUID NOT NULL,
    source_version INTEGER NOT NULL,
    service_date DATE NOT NULL,
    section_id TEXT NOT NULL,
    zone SMALLINT NOT NULL,
    required_volume_m3 DOUBLE PRECISION NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    quality TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    as_of_date DATE NOT NULL,
    source_data_status TEXT NOT NULL,
    planning_disposition TEXT NOT NULL,
    delivery_node_id TEXT,
    gate_id TEXT,
    maximum_delivery_m3s DOUBLE PRECISION,
    approved_excess_m3 DOUBLE PRECISION,
    travel_delay_seconds INTEGER,
    minimum_delivery_fraction DOUBLE PRECISION,
    maximum_delivery_fraction DOUBLE PRECISION,
    path_reach_ids_document_text TEXT,
    rotation_windows_document_text TEXT,
    requirement_document_text TEXT NOT NULL,
    CONSTRAINT control_plan_requirements_pkey
        PRIMARY KEY (plan_id, plan_version, requirement_id),
    CONSTRAINT control_plan_requirements_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    CONSTRAINT control_plan_requirements_section_key
        UNIQUE (plan_id, plan_version, service_date, section_id),
    CONSTRAINT control_plan_requirements_zone_range
        CHECK (zone BETWEEN 1 AND 6),
    CONSTRAINT control_plan_requirements_source_version_positive
        CHECK (source_version > 0),
    CONSTRAINT control_plan_requirements_volume_nonnegative
        CHECK (required_volume_m3 >= 0),
    CONSTRAINT control_plan_requirements_window_ordered
        CHECK (window_end > window_start),
    CONSTRAINT control_plan_requirements_quality
        CHECK (quality IN ('estimated', 'forecast')),
    CONSTRAINT control_plan_requirements_source_status
        CHECK (source_data_status = 'published'),
    CONSTRAINT control_plan_requirements_disposition
        CHECK (planning_disposition IN ('scheduled', 'no_delivery_required')),
    CONSTRAINT control_plan_requirements_scheduled_fields
        CHECK (planning_disposition <> 'scheduled'
               OR (delivery_node_id IS NOT NULL
                   AND gate_id IS NOT NULL
                   AND maximum_delivery_m3s IS NOT NULL
                   AND approved_excess_m3 IS NOT NULL
                   AND travel_delay_seconds IS NOT NULL
                   AND minimum_delivery_fraction IS NOT NULL
                   AND maximum_delivery_fraction IS NOT NULL
                   AND path_reach_ids_document_text IS NOT NULL
                   AND rotation_windows_document_text IS NOT NULL)),
    CONSTRAINT control_plan_requirements_zero_volume_disposition
        CHECK ((required_volume_m3 > 0
                AND planning_disposition = 'scheduled')
               OR (required_volume_m3 = 0
                   AND planning_disposition = 'no_delivery_required')),
    CONSTRAINT control_plan_requirements_delivery_positive
        CHECK (maximum_delivery_m3s IS NULL OR maximum_delivery_m3s > 0),
    CONSTRAINT control_plan_requirements_excess_nonnegative
        CHECK (approved_excess_m3 IS NULL OR approved_excess_m3 >= 0),
    CONSTRAINT control_plan_requirements_delay_nonnegative
        CHECK (travel_delay_seconds IS NULL OR travel_delay_seconds >= 0),
    CONSTRAINT control_plan_requirements_fractions_ordered
        CHECK (minimum_delivery_fraction IS NULL
               OR (minimum_delivery_fraction > 0
                   AND minimum_delivery_fraction <= maximum_delivery_fraction
                   AND maximum_delivery_fraction <= 1))
);

CREATE TABLE scheduler.gate_plan_events (
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    event_sequence INTEGER NOT NULL,
    gate_event_sequence INTEGER NOT NULL,
    gate_id TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    planned_at TIMESTAMPTZ NOT NULL,
    target_position_m DOUBLE PRECISION NOT NULL,
    source_flow_m3s DOUBLE PRECISION NOT NULL,
    trim_ordinal SMALLINT,
    CONSTRAINT gate_plan_events_pkey
        PRIMARY KEY (plan_id, plan_version, event_sequence),
    CONSTRAINT gate_plan_events_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    CONSTRAINT gate_plan_events_gate_sequence_key
        UNIQUE (plan_id, plan_version, gate_id, gate_event_sequence),
    CONSTRAINT gate_plan_events_gate_time_key
        UNIQUE (plan_id, plan_version, gate_id, planned_at),
    CONSTRAINT gate_plan_events_sequence_positive
        CHECK (event_sequence > 0 AND gate_event_sequence > 0),
    CONSTRAINT gate_plan_events_kind
        CHECK (event_kind IN ('open', 'trim', 'close')),
    CONSTRAINT gate_plan_events_open_trim_positive
        CHECK (event_kind = 'close'
               OR (target_position_m > 0 AND source_flow_m3s > 0)),
    CONSTRAINT gate_plan_events_close_zero
        CHECK (event_kind <> 'close'
               OR (target_position_m = 0 AND source_flow_m3s = 0)),
    CONSTRAINT gate_plan_events_trim_ordinal
        CHECK ((event_kind = 'trim' AND trim_ordinal > 0)
               OR (event_kind <> 'trim' AND trim_ordinal IS NULL))
);

CREATE TABLE scheduler.control_state_transitions (
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    transition_sequence INTEGER NOT NULL,
    transition_type TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    actor_subject TEXT NOT NULL,
    reason TEXT,
    transition_document_text TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_state_transitions_pkey
        PRIMARY KEY (plan_id, plan_version, transition_sequence),
    CONSTRAINT control_state_transitions_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    -- PR 4.3a admits exactly the initial draft_created transition. PR 4.3b
    -- must relax these checks through a NEW migration, never by editing this
    -- applied pair.
    CONSTRAINT control_state_transitions_initial_only
        CHECK (transition_sequence = 1),
    CONSTRAINT control_state_transitions_type
        CHECK (transition_type = 'draft_created'),
    CONSTRAINT control_state_transitions_from_initial
        CHECK (from_state IS NULL),
    CONSTRAINT control_state_transitions_to_draft
        CHECK (to_state = 'draft'),
    CONSTRAINT control_state_transitions_subject_nonempty
        CHECK (length(actor_subject) > 0)
);

CREATE FUNCTION scheduler.control_plan_rows_are_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'control-plan rows are immutable: % on %.% is forbidden',
        TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER control_plan_runs_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_plan_runs
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();

CREATE TRIGGER control_plan_requirements_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_plan_requirements
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();

CREATE TRIGGER gate_plan_events_immutable
    BEFORE UPDATE OR DELETE ON scheduler.gate_plan_events
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();

CREATE TRIGGER control_state_transitions_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_state_transitions
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();
