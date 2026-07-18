-- Rollback 0005_control_plan_provenance_v2.
-- REFUSES once any v2 (artifact-reference) draft exists: a v2 row has no
-- prediction_response_document_text to restore, so dropping its columns would
-- irreversibly lose the only provenance the row carries. Once v2 rows exist,
-- forward-fix with a new migration — never roll back. On an empty-of-v2 table it
-- restores the exact 0001 prediction CHECKs and drops the added columns.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM scheduler.control_plan_runs
        WHERE provenance_version IS NOT NULL
    ) THEN
        RAISE EXCEPTION
            'cannot roll back 0005: % v2 artifact-reference draft(s) exist; '
            'their provenance would be lost — forward-fix instead',
            (SELECT count(*) FROM scheduler.control_plan_runs
             WHERE provenance_version IS NOT NULL);
    END IF;
END
$$;

ALTER TABLE scheduler.control_plan_runs
    DROP CONSTRAINT control_plan_runs_provenance_version,
    DROP CONSTRAINT control_plan_runs_engine_build_digest_shape,
    DROP CONSTRAINT control_plan_runs_engine_content_hash_shape,
    DROP CONSTRAINT control_plan_runs_artifact_sha_shape,
    DROP CONSTRAINT control_plan_runs_coverage_summary_sha_shape,
    DROP CONSTRAINT control_plan_runs_ledger_sha_shape,
    DROP CONSTRAINT control_plan_runs_artifact_size_positive,
    DROP CONSTRAINT control_plan_runs_artifact_encoding_version_positive,
    DROP CONSTRAINT control_plan_runs_prediction_identity_version_positive,
    DROP CONSTRAINT control_plan_runs_provenance_v2_identity_version,
    DROP CONSTRAINT control_plan_runs_engine_semantic_version_nonnegative,
    DROP CONSTRAINT control_plan_runs_engine_id_nonempty,
    DROP CONSTRAINT control_plan_runs_artifact_media_type_nonempty,
    DROP CONSTRAINT control_plan_runs_artifact_encoding_nonempty,
    DROP CONSTRAINT control_plan_runs_coverage_summary_nonempty,
    DROP CONSTRAINT control_plan_runs_infeasible_has_no_prediction,
    DROP CONSTRAINT control_plan_runs_feasible_prediction_branch;

ALTER TABLE scheduler.control_plan_runs
    ADD CONSTRAINT control_plan_runs_infeasible_has_no_prediction
        CHECK (optimizer_status <> 'infeasible'
               OR (prediction_status = 'not_requested'
                   AND prediction_run_id IS NULL
                   AND prediction_member_summaries IS NULL
                   AND prediction_request_document_text IS NULL
                   AND prediction_response_document_text IS NULL
                   AND prediction_response_sha256 IS NULL)),
    ADD CONSTRAINT control_plan_runs_feasible_has_prediction
        CHECK (optimizer_status <> 'feasible'
               OR (prediction_status IN ('completed', 'infeasible')
                   AND prediction_run_id IS NOT NULL
                   AND prediction_member_summaries IS NOT NULL
                   AND prediction_request_document_text IS NOT NULL
                   AND prediction_response_document_text IS NOT NULL
                   AND prediction_response_sha256 IS NOT NULL));

ALTER TABLE scheduler.control_plan_runs
    DROP COLUMN provenance_version,
    DROP COLUMN prediction_identity_version,
    DROP COLUMN engine_id,
    DROP COLUMN engine_semantic_contract_version,
    DROP COLUMN engine_build_digest,
    DROP COLUMN engine_descriptor_content_hash,
    DROP COLUMN artifact_sha256,
    DROP COLUMN artifact_uncompressed_size_bytes,
    DROP COLUMN artifact_media_type,
    DROP COLUMN artifact_encoding,
    DROP COLUMN artifact_encoding_version,
    DROP COLUMN coverage_summary_document_text,
    DROP COLUMN coverage_summary_sha256,
    DROP COLUMN predicted_delivery_ledger_sha256;
