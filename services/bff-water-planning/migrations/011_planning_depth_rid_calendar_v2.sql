ALTER TABLE water_planning.planning_depth_submissions
ADD COLUMN calendar_system TEXT NOT NULL DEFAULT 'legacy-calendar-v1';

ALTER TABLE water_planning.planning_depth_submissions
DROP CONSTRAINT planning_depth_schema_version_check;

ALTER TABLE water_planning.planning_depth_submissions
DROP CONSTRAINT planning_depth_week_key_check;

ALTER TABLE water_planning.planning_depth_submissions
ADD CONSTRAINT planning_depth_calendar_identity_check CHECK (
    CASE schema_version
        WHEN 1 THEN
            calendar_system = 'legacy-calendar-v1'
            AND week_key ~ '^[0-9]{4}-W[0-9]{2}$'
        WHEN 2 THEN
            calendar_system = 'rid-irrigation-v1'
            AND week_key ~ '^[0-9]{4}-R(0[1-9]|[1-4][0-9]|5[0-3])$'
            AND substring(week_key FROM 1 FOR 4)::INTEGER BETWEEN 1901 AND 2401
            AND week_date =
                make_date(
                    substring(week_key FROM 1 FOR 4)::INTEGER - 1,
                    11,
                    1
                )
                + (
                    substring(week_key FROM 7 FOR 2)::INTEGER - 1
                ) * 7
        ELSE FALSE
    END
);

ALTER TABLE water_planning.planning_depth_submissions
DROP CONSTRAINT planning_depth_submissions_client_submission_id_key;

CREATE UNIQUE INDEX planning_depth_client_replay_scope
ON water_planning.planning_depth_submissions (
    calendar_system,
    client_submission_id
);

DROP INDEX water_planning.planning_depth_one_root_per_scope;
CREATE UNIQUE INDEX planning_depth_one_root_per_scope
ON water_planning.planning_depth_submissions (
    project_key,
    calendar_system,
    week_key
)
WHERE supersedes_submission_id IS NULL;

DROP INDEX water_planning.planning_depth_submission_scope;
CREATE INDEX planning_depth_submission_scope
ON water_planning.planning_depth_submissions (
    project_key,
    calendar_system,
    week_key
);

CREATE OR REPLACE FUNCTION water_planning.enforce_planning_depth_predecessor_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    predecessor_project_key TEXT;
    predecessor_calendar_system TEXT;
    predecessor_week_key TEXT;
BEGIN
    IF NEW.supersedes_submission_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT project_key, calendar_system, week_key
    INTO predecessor_project_key, predecessor_calendar_system, predecessor_week_key
    FROM water_planning.planning_depth_submissions
    WHERE submission_id = NEW.supersedes_submission_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'planning-depth predecessor does not exist'
            USING ERRCODE = '23503';
    END IF;

    IF (
        predecessor_project_key,
        predecessor_calendar_system,
        predecessor_week_key
    ) IS DISTINCT FROM (
        NEW.project_key,
        NEW.calendar_system,
        NEW.week_key
    ) THEN
        RAISE EXCEPTION 'planning-depth predecessor scope mismatch'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS planning_depth_predecessor_scope
ON water_planning.planning_depth_submissions;
CREATE TRIGGER planning_depth_predecessor_scope
BEFORE INSERT ON water_planning.planning_depth_submissions
FOR EACH ROW EXECUTE FUNCTION water_planning.enforce_planning_depth_predecessor_scope();
