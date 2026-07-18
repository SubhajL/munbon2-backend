-- Roll back PR 4.4b-1. REFUSE if any identity_version=2 row exists: those rows
-- depend on the engine columns and the relaxed CHECK, so dropping them would
-- destroy content-addressed provenance. Only a v1-only table can revert.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM flow_monitoring.prediction_runs
        WHERE identity_version = 2
    ) THEN
        RAISE EXCEPTION
            'cannot roll back 0002: identity_version=2 prediction runs exist';
    END IF;
END
$$;

ALTER TABLE flow_monitoring.prediction_runs
    DROP CONSTRAINT IF EXISTS prediction_runs_engine_fields_match_identity;

ALTER TABLE flow_monitoring.prediction_runs
    DROP CONSTRAINT IF EXISTS prediction_runs_identity_version_in_1_2;

ALTER TABLE flow_monitoring.prediction_runs
    DROP COLUMN IF EXISTS engine_descriptor_content_hash,
    DROP COLUMN IF EXISTS build_digest,
    DROP COLUMN IF EXISTS semantic_contract_version,
    DROP COLUMN IF EXISTS engine_id;

-- Restore the exact v1-only identity check from 0001.
ALTER TABLE flow_monitoring.prediction_runs
    ADD CONSTRAINT prediction_runs_identity_version_check
    CHECK (identity_version = 1);
