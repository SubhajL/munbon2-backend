-- 0005_control_plan_provenance_v2 (PR 4.4b-2)
-- Additive: a feasible draft may now store a BOUNDED artifact REFERENCE instead
-- of copying the (up-to-64 MiB) flow prediction response into the immutable row.
-- A v1 feasible row keeps its prediction_response_document_text + _sha256; a v2
-- feasible row (provenance_version = 2) carries engine pins + artifact metadata +
-- bounded coverage/member summaries + the predicted-delivery-ledger hash and has
-- prediction_response_document_text / prediction_response_sha256 NULL. NEVER edits
-- 0001. Documents are TEXT never JSONB.
--
-- Every hash/regex column is guarded with IS NULL OR ... : a v1 row leaves the v2
-- columns NULL, and `NULL ~ regex` evaluates to UNKNOWN, which a CHECK treats as
-- SATISFIED — so the shape checks admit v1 rows, and the v2 branch below enforces
-- presence with explicit IS NOT NULL (never regex-implies-presence).

ALTER TABLE scheduler.control_plan_runs
    ADD COLUMN provenance_version SMALLINT,
    ADD COLUMN prediction_identity_version SMALLINT,
    ADD COLUMN engine_id TEXT,
    ADD COLUMN engine_semantic_contract_version INTEGER,
    ADD COLUMN engine_build_digest CHAR(64),
    ADD COLUMN engine_descriptor_content_hash CHAR(64),
    ADD COLUMN artifact_sha256 CHAR(64),
    ADD COLUMN artifact_uncompressed_size_bytes BIGINT,
    ADD COLUMN artifact_media_type TEXT,
    ADD COLUMN artifact_encoding TEXT,
    ADD COLUMN artifact_encoding_version INTEGER,
    ADD COLUMN coverage_summary_document_text TEXT,
    ADD COLUMN coverage_summary_sha256 CHAR(64),
    ADD COLUMN predicted_delivery_ledger_sha256 CHAR(64);

-- Replace the two 0001 prediction-presence CHECKs with explicit v1/v2 branches.
ALTER TABLE scheduler.control_plan_runs
    DROP CONSTRAINT control_plan_runs_infeasible_has_no_prediction,
    DROP CONSTRAINT control_plan_runs_feasible_has_prediction;

ALTER TABLE scheduler.control_plan_runs
    ADD CONSTRAINT control_plan_runs_provenance_version
        CHECK (provenance_version IS NULL OR provenance_version = 2),

    -- Shape checks: guarded so a NULL (v1) column is admitted and only a present
    -- (v2) value is validated. Never rely on `col ~ regex` alone to force
    -- presence — a NULL would pass on UNKNOWN.
    ADD CONSTRAINT control_plan_runs_engine_build_digest_shape
        CHECK (engine_build_digest IS NULL
               OR engine_build_digest ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT control_plan_runs_engine_content_hash_shape
        CHECK (engine_descriptor_content_hash IS NULL
               OR engine_descriptor_content_hash ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT control_plan_runs_artifact_sha_shape
        CHECK (artifact_sha256 IS NULL
               OR artifact_sha256 ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT control_plan_runs_coverage_summary_sha_shape
        CHECK (coverage_summary_sha256 IS NULL
               OR coverage_summary_sha256 ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT control_plan_runs_ledger_sha_shape
        CHECK (predicted_delivery_ledger_sha256 IS NULL
               OR predicted_delivery_ledger_sha256 ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT control_plan_runs_artifact_size_positive
        CHECK (artifact_uncompressed_size_bytes IS NULL
               OR artifact_uncompressed_size_bytes > 0),
    ADD CONSTRAINT control_plan_runs_artifact_encoding_version_positive
        CHECK (artifact_encoding_version IS NULL
               OR artifact_encoding_version > 0),
    ADD CONSTRAINT control_plan_runs_prediction_identity_version_positive
        CHECK (prediction_identity_version IS NULL
               OR prediction_identity_version > 0),

    -- A v2 provenance row pins Flow's identity-v2 contract exactly:
    -- provenance_version = 2 REQUIRES prediction_identity_version = 2. Written
    -- with IS DISTINCT FROM so a NULL (v1) provenance_version passes, and a v2 row
    -- whose identity version is NULL or anything other than 2 is rejected.
    ADD CONSTRAINT control_plan_runs_provenance_v2_identity_version
        CHECK (provenance_version IS DISTINCT FROM 2
               OR prediction_identity_version = 2),
    ADD CONSTRAINT control_plan_runs_engine_semantic_version_nonnegative
        CHECK (engine_semantic_contract_version IS NULL
               OR engine_semantic_contract_version >= 0),
    ADD CONSTRAINT control_plan_runs_engine_id_nonempty
        CHECK (engine_id IS NULL OR length(engine_id) > 0),
    ADD CONSTRAINT control_plan_runs_artifact_media_type_nonempty
        CHECK (artifact_media_type IS NULL OR length(artifact_media_type) > 0),
    ADD CONSTRAINT control_plan_runs_artifact_encoding_nonempty
        CHECK (artifact_encoding IS NULL OR length(artifact_encoding) > 0),
    ADD CONSTRAINT control_plan_runs_coverage_summary_nonempty
        CHECK (coverage_summary_document_text IS NULL
               OR length(coverage_summary_document_text) > 0),

    -- An infeasible optimizer result requests no prediction AND carries no
    -- provenance reference: every prediction and v2 column is NULL.
    ADD CONSTRAINT control_plan_runs_infeasible_has_no_prediction
        CHECK (optimizer_status <> 'infeasible'
               OR (prediction_status = 'not_requested'
                   AND prediction_run_id IS NULL
                   AND prediction_member_summaries IS NULL
                   AND prediction_request_document_text IS NULL
                   AND prediction_response_document_text IS NULL
                   AND prediction_response_sha256 IS NULL
                   AND provenance_version IS NULL
                   AND prediction_identity_version IS NULL
                   AND engine_id IS NULL
                   AND engine_semantic_contract_version IS NULL
                   AND engine_build_digest IS NULL
                   AND engine_descriptor_content_hash IS NULL
                   AND artifact_sha256 IS NULL
                   AND artifact_uncompressed_size_bytes IS NULL
                   AND artifact_media_type IS NULL
                   AND artifact_encoding IS NULL
                   AND artifact_encoding_version IS NULL
                   AND coverage_summary_document_text IS NULL
                   AND coverage_summary_sha256 IS NULL
                   AND predicted_delivery_ledger_sha256 IS NULL)),

    -- A feasible optimizer result is EITHER a legacy v1 draft (keeps the full
    -- response + its sha, no v2 columns) OR a v2 artifact-reference draft (engine
    -- pins + artifact metadata + summaries + ledger hash, and NO response copy).
    ADD CONSTRAINT control_plan_runs_feasible_prediction_branch
        CHECK (optimizer_status <> 'feasible'
               OR (
                   -- v1 feasible: full response persisted, no provenance columns.
                   (provenance_version IS NULL
                    AND prediction_status IN ('completed', 'infeasible')
                    AND prediction_run_id IS NOT NULL
                    AND prediction_member_summaries IS NOT NULL
                    AND prediction_request_document_text IS NOT NULL
                    AND prediction_response_document_text IS NOT NULL
                    AND prediction_response_sha256 IS NOT NULL
                    AND prediction_identity_version IS NULL
                    AND engine_id IS NULL
                    AND engine_semantic_contract_version IS NULL
                    AND engine_build_digest IS NULL
                    AND engine_descriptor_content_hash IS NULL
                    AND artifact_sha256 IS NULL
                    AND artifact_uncompressed_size_bytes IS NULL
                    AND artifact_media_type IS NULL
                    AND artifact_encoding IS NULL
                    AND artifact_encoding_version IS NULL
                    AND coverage_summary_document_text IS NULL
                    AND coverage_summary_sha256 IS NULL
                    AND predicted_delivery_ledger_sha256 IS NULL)
                   OR
                   -- v2 feasible: bounded artifact reference, response copy NULL.
                   (provenance_version = 2
                    AND prediction_status IN ('completed', 'infeasible')
                    AND prediction_run_id IS NOT NULL
                    AND prediction_member_summaries IS NOT NULL
                    AND prediction_request_document_text IS NOT NULL
                    AND prediction_response_document_text IS NULL
                    AND prediction_response_sha256 IS NULL
                    AND prediction_identity_version IS NOT NULL
                    AND engine_id IS NOT NULL
                    AND engine_semantic_contract_version IS NOT NULL
                    AND engine_build_digest IS NOT NULL
                    AND engine_descriptor_content_hash IS NOT NULL
                    AND artifact_sha256 IS NOT NULL
                    AND artifact_uncompressed_size_bytes IS NOT NULL
                    AND artifact_media_type IS NOT NULL
                    AND artifact_encoding IS NOT NULL
                    AND artifact_encoding_version IS NOT NULL
                    AND coverage_summary_document_text IS NOT NULL
                    AND coverage_summary_sha256 IS NOT NULL
                    AND predicted_delivery_ledger_sha256 IS NOT NULL)));
