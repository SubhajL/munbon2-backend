-- PR 4.4b-1: prediction-engine identity v2. Additive, nullable engine pins;
-- relax the identity-version CHECK to IN (1, 2); pin that v2 rows carry the
-- engine fields and v1 rows do not. The 0001 immutability trigger still guards
-- UPDATE/DELETE; the artifact table is untouched. Columns are nullable with no
-- default, so this is metadata-only (no row rewrite, no immutability-trigger
-- fire on existing rows).
ALTER TABLE flow_monitoring.prediction_runs
    ADD COLUMN engine_id TEXT,
    ADD COLUMN semantic_contract_version SMALLINT,
    ADD COLUMN build_digest TEXT,
    ADD COLUMN engine_descriptor_content_hash TEXT;

-- Drop the v1-only identity check (0001 created it unnamed as
-- prediction_runs_identity_version_check) and replace it with IN (1, 2).
ALTER TABLE flow_monitoring.prediction_runs
    DROP CONSTRAINT IF EXISTS prediction_runs_identity_version_check;

ALTER TABLE flow_monitoring.prediction_runs
    ADD CONSTRAINT prediction_runs_identity_version_in_1_2
    CHECK (identity_version IN (1, 2));

-- v1 rows carry NO engine pins; v2 rows carry all four, well-formed.
ALTER TABLE flow_monitoring.prediction_runs
    ADD CONSTRAINT prediction_runs_engine_fields_match_identity
    CHECK (
        (
            identity_version = 1
            AND engine_id IS NULL
            AND semantic_contract_version IS NULL
            AND build_digest IS NULL
            AND engine_descriptor_content_hash IS NULL
        )
        OR (
            identity_version = 2
            AND engine_id IS NOT NULL
            AND btrim(engine_id) <> ''
            AND semantic_contract_version IS NOT NULL
            -- NULL ~ regex is SQL NULL, and Postgres treats a NULL CHECK result
            -- as SATISFIED, so a v2 row with NULL build_digest / content_hash
            -- would COMMIT on the regex alone. Guard both with IS NOT NULL first
            -- (mirrors engine_id / semantic_contract_version above).
            AND build_digest IS NOT NULL
            AND build_digest ~ '^[0-9a-f]{64}$'
            AND engine_descriptor_content_hash IS NOT NULL
            AND engine_descriptor_content_hash ~ '^[0-9a-f]{64}$'
        )
    );
