CREATE SCHEMA IF NOT EXISTS flow_monitoring;

CREATE TABLE flow_monitoring.prediction_runs (
    prediction_run_id TEXT PRIMARY KEY
        CHECK (prediction_run_id ~ '^[0-9a-f]{64}$'),
    identity_version SMALLINT NOT NULL DEFAULT 1
        CHECK (identity_version = 1),
    response_schema_version SMALLINT NOT NULL
        CHECK (response_schema_version = 2),
    -- TEXT, deliberately NOT jsonb: the run id is a hash over these exact
    -- canonical bytes, and jsonb normalizes numerics (e.g. -0.0 -> 0.0),
    -- which would permanently break identity recomputation on load.
    request_payload TEXT NOT NULL
        CHECK (left(request_payload, 1) = '{'),
    model_snapshot_id TEXT NOT NULL
        CHECK (model_snapshot_id ~ '^[0-9a-f]{64}$'),
    model_release_id TEXT NOT NULL
        CHECK (btrim(model_release_id) <> ''),
    model_release_content_hash TEXT NOT NULL
        CHECK (model_release_content_hash ~ '^[0-9a-f]{64}$'),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    timestep_seconds DOUBLE PRECISION NOT NULL
        CHECK (
            timestep_seconds > 0
            AND timestep_seconds < 'Infinity'::DOUBLE PRECISION
        ),
    member_summaries JSONB NOT NULL
        CHECK (
            jsonb_typeof(member_summaries) = 'array'
            AND jsonb_array_length(member_summaries) = 3
        ),
    artifact_sha256 TEXT NOT NULL
        CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    stored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (starts_at < ends_at)
);

CREATE TABLE flow_monitoring.prediction_artifacts (
    prediction_run_id TEXT PRIMARY KEY
        REFERENCES flow_monitoring.prediction_runs (prediction_run_id)
        ON DELETE RESTRICT,
    artifact_sha256 TEXT NOT NULL
        CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    media_type TEXT NOT NULL DEFAULT 'application/json'
        CHECK (media_type = 'application/json'),
    encoding TEXT NOT NULL DEFAULT 'canonical-json+zlib'
        CHECK (encoding = 'canonical-json+zlib'),
    encoding_version SMALLINT NOT NULL DEFAULT 1
        CHECK (encoding_version = 1),
    uncompressed_size_bytes BIGINT NOT NULL
        CHECK (
            uncompressed_size_bytes > 0
            AND uncompressed_size_bytes <= 67108864
        ),
    compressed_payload BYTEA NOT NULL
        CHECK (octet_length(compressed_payload) > 0),
    stored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (prediction_run_id, artifact_sha256)
);

ALTER TABLE flow_monitoring.prediction_runs
    ADD CONSTRAINT prediction_runs_exact_artifact_fk
    FOREIGN KEY (prediction_run_id, artifact_sha256)
    REFERENCES flow_monitoring.prediction_artifacts (
        prediction_run_id,
        artifact_sha256
    )
    DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION flow_monitoring.reject_prediction_row_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'prediction persistence rows are immutable';
END;
$$;

CREATE TRIGGER prediction_runs_are_immutable
    BEFORE UPDATE OR DELETE ON flow_monitoring.prediction_runs
    FOR EACH ROW
    EXECUTE FUNCTION flow_monitoring.reject_prediction_row_change();

CREATE TRIGGER prediction_artifacts_are_immutable
    BEFORE UPDATE OR DELETE ON flow_monitoring.prediction_artifacts
    FOR EACH ROW
    EXECUTE FUNCTION flow_monitoring.reject_prediction_row_change();
