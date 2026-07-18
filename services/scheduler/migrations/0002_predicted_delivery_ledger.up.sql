-- 0002_predicted_delivery_ledger (PR 5.1)
-- Append-only projection of a feasible draft's persisted flow prediction into
-- per-requirement, per-checkpoint delivery-ledger rows. Prediction-only
-- vocabulary; raw member values kept (min/max computed at read time). Canonical
-- documents are TEXT never JSONB. Reuses the 0001 immutability trigger function.

CREATE TABLE scheduler.section_delivery_ledger (
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    requirement_id UUID NOT NULL,
    checkpoint_index INTEGER NOT NULL,
    ledger_schema_version SMALLINT NOT NULL DEFAULT 1,
    section_id TEXT NOT NULL,
    checkpoint_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    required_volume_m3 DOUBLE PRECISION NOT NULL,
    approved_excess_m3 DOUBLE PRECISION NOT NULL,
    lower_delivered_m3 DOUBLE PRECISION,
    nominal_delivered_m3 DOUBLE PRECISION,
    upper_delivered_m3 DOUBLE PRECISION,
    lower_path_in_transit_m3 DOUBLE PRECISION,
    nominal_path_in_transit_m3 DOUBLE PRECISION,
    upper_path_in_transit_m3 DOUBLE PRECISION,
    checkpoint_reasons_document_text TEXT NOT NULL,
    projection_document_text TEXT NOT NULL,
    projection_sha256 CHAR(64) NOT NULL,
    prediction_run_id CHAR(64) NOT NULL,
    prediction_response_sha256 CHAR(64) NOT NULL,
    projected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT section_delivery_ledger_pkey
        PRIMARY KEY (plan_id, plan_version, requirement_id, checkpoint_index),
    CONSTRAINT section_delivery_ledger_requirement_fkey
        FOREIGN KEY (plan_id, plan_version, requirement_id)
        REFERENCES scheduler.control_plan_requirements
            (plan_id, plan_version, requirement_id)
        ON DELETE RESTRICT,
    CONSTRAINT section_delivery_ledger_checkpoint_key
        UNIQUE (plan_id, plan_version, requirement_id, checkpoint_at),
    CONSTRAINT section_delivery_ledger_projection_key
        UNIQUE (plan_id, plan_version, projection_sha256),
    CONSTRAINT section_delivery_ledger_index_positive
        CHECK (checkpoint_index > 0),
    CONSTRAINT section_delivery_ledger_schema_version
        CHECK (ledger_schema_version = 1),
    CONSTRAINT section_delivery_ledger_status
        CHECK (status IN ('not_started', 'predicted_in_progress',
                          'predicted_fulfilled', 'predicted_excess_risk',
                          'invalidated', 'manual_review')),
    CONSTRAINT section_delivery_ledger_required_positive
        CHECK (required_volume_m3 > 0),
    CONSTRAINT section_delivery_ledger_excess_nonnegative
        CHECK (approved_excess_m3 >= 0),
    CONSTRAINT section_delivery_ledger_projection_shape
        CHECK (projection_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT section_delivery_ledger_run_shape
        CHECK (prediction_run_id ~ '^[0-9a-f]{64}$'),
    CONSTRAINT section_delivery_ledger_response_shape
        CHECK (prediction_response_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT section_delivery_ledger_section_nonempty
        CHECK (length(section_id) > 0),
    -- Non-review rows carry a complete six-value member envelope; only
    -- manual_review / invalidated rows may leave envelope columns null.
    CONSTRAINT section_delivery_ledger_review_or_full_envelope
        CHECK (status IN ('manual_review', 'invalidated')
               OR (lower_delivered_m3 IS NOT NULL
                   AND nominal_delivered_m3 IS NOT NULL
                   AND upper_delivered_m3 IS NOT NULL
                   AND lower_path_in_transit_m3 IS NOT NULL
                   AND nominal_path_in_transit_m3 IS NOT NULL
                   AND upper_path_in_transit_m3 IS NOT NULL))
);

CREATE TRIGGER section_delivery_ledger_immutable
    BEFORE UPDATE OR DELETE ON scheduler.section_delivery_ledger
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();
