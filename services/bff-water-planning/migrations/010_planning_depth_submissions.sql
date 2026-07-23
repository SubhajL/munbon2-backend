CREATE SCHEMA IF NOT EXISTS water_planning;

CREATE TABLE IF NOT EXISTS water_planning.planning_depth_submissions (
    submission_id UUID PRIMARY KEY,
    schema_version SMALLINT NOT NULL,
    client_submission_id UUID NOT NULL UNIQUE,
    project_key TEXT NOT NULL,
    week_key TEXT NOT NULL,
    week_date DATE NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_by TEXT NOT NULL,
    supersedes_submission_id UUID
        REFERENCES water_planning.planning_depth_submissions (submission_id),
    request_document_text TEXT NOT NULL,
    request_sha256 CHAR(64) NOT NULL,
    expanded_sha256 CHAR(64) NOT NULL,
    CONSTRAINT planning_depth_schema_version_check
        CHECK (schema_version = 1),
    CONSTRAINT planning_depth_project_key_check
        CHECK (project_key = 'mun-bon'),
    CONSTRAINT planning_depth_week_key_check
        CHECK (week_key ~ '^[0-9]{4}-W[0-9]{2}$'),
    CONSTRAINT planning_depth_submitted_by_check
        CHECK (length(btrim(submitted_by)) > 0),
    CONSTRAINT planning_depth_request_sha_check
        CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT planning_depth_expanded_sha_check
        CHECK (expanded_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT planning_depth_predecessor_check
        CHECK (supersedes_submission_id IS NULL
               OR supersedes_submission_id <> submission_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS
    planning_depth_one_successor_per_predecessor
ON water_planning.planning_depth_submissions (supersedes_submission_id)
WHERE supersedes_submission_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS planning_depth_one_root_per_scope
ON water_planning.planning_depth_submissions (project_key, week_key)
WHERE supersedes_submission_id IS NULL;

CREATE INDEX IF NOT EXISTS planning_depth_submission_scope
ON water_planning.planning_depth_submissions (project_key, week_key);

CREATE TABLE IF NOT EXISTS water_planning.planning_depth_values (
    submission_id UUID NOT NULL
        REFERENCES water_planning.planning_depth_submissions (submission_id),
    section_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    planning_depth_mm NUMERIC(12,3) NOT NULL
        CHECK (planning_depth_mm >= 0),
    source_kind TEXT NOT NULL
        CHECK (source_kind IN ('zone_default', 'section_override')),
    source_area_id TEXT NOT NULL,
    PRIMARY KEY (submission_id, section_id),
    CONSTRAINT planning_depth_source_identity_check CHECK (
        (source_kind = 'zone_default' AND source_area_id = zone_id)
        OR
        (source_kind = 'section_override' AND source_area_id = section_id)
    )
);

CREATE OR REPLACE FUNCTION water_planning.reject_planning_depth_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'planning-depth records are immutable'
        USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS planning_depth_submissions_immutable
ON water_planning.planning_depth_submissions;
CREATE TRIGGER planning_depth_submissions_immutable
BEFORE UPDATE OR DELETE ON water_planning.planning_depth_submissions
FOR EACH ROW EXECUTE FUNCTION water_planning.reject_planning_depth_mutation();

DROP TRIGGER IF EXISTS planning_depth_values_immutable
ON water_planning.planning_depth_values;
CREATE TRIGGER planning_depth_values_immutable
BEFORE UPDATE OR DELETE ON water_planning.planning_depth_values
FOR EACH ROW EXECUTE FUNCTION water_planning.reject_planning_depth_mutation();
