ALTER TABLE flow_monitoring.prediction_runs
    DROP CONSTRAINT IF EXISTS prediction_runs_exact_artifact_fk;

DROP TABLE IF EXISTS flow_monitoring.prediction_artifacts;
DROP TABLE IF EXISTS flow_monitoring.prediction_runs;

DROP FUNCTION IF EXISTS flow_monitoring.reject_prediction_row_change();
