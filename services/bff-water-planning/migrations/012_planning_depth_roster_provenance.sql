-- 012 planning-depth roster provenance
--
-- Records the authoritative roster SNAPSHOT that produced each submission's 41
-- expanded values: the dataset_version_id and source_hash of the roster used to
-- expand the request. Semantics are "snapshot used by this submission", NOT
-- "roster still active at commit" (a commit-time-current guarantee would require
-- a version recheck/locking protocol and is out of scope).
--
-- Additive only. Migration 010 and 011 are immutable. Pre-012 rows keep NULL
-- provenance (unknown legacy) and are never backfilled or fabricated. Provenance
-- is all-or-none, and every NEW submission MUST carry it (fail-closed trigger).

ALTER TABLE water_planning.planning_depth_submissions
    ADD COLUMN roster_dataset_version_id INTEGER,
    ADD COLUMN roster_source_hash TEXT;

ALTER TABLE water_planning.planning_depth_submissions
    ADD CONSTRAINT planning_depth_roster_provenance_all_or_none
    CHECK (
        (roster_dataset_version_id IS NULL) = (roster_source_hash IS NULL)
    );

ALTER TABLE water_planning.planning_depth_submissions
    ADD CONSTRAINT planning_depth_roster_source_hash_format
    CHECK (
        roster_source_hash IS NULL
        OR roster_source_hash ~ '^[0-9a-f]{64}$'
    );

ALTER TABLE water_planning.planning_depth_submissions
    ADD CONSTRAINT planning_depth_roster_dataset_version_positive
    CHECK (
        roster_dataset_version_id IS NULL
        OR roster_dataset_version_id > 0
    );

-- Fail-closed: a NEW submission may never omit provenance, and the provenance
-- pair MUST identify a real section_master roster snapshot -- otherwise a direct
-- insert could fabricate an immutable-but-meaningless (id, hash) audit record.
-- The pair is NOT required to be the currently-active roster: "snapshot used"
-- must accept a since-superseded snapshot, so status is deliberately not checked.
-- Legacy rows are untouched (INSERT triggers do not fire during ADD COLUMN).
-- The plpgsql body is parsed at execution, not at CREATE, so this function may
-- reference ros_gis.dataset_versions even if that schema is created after 012.
-- Stable P0001 messages let tests assert each rejection distinctly, apart from
-- the 23514 CHECK violations above.
CREATE OR REPLACE FUNCTION water_planning.require_planning_depth_roster_provenance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.roster_dataset_version_id IS NULL
       OR NEW.roster_source_hash IS NULL THEN
        RAISE EXCEPTION 'planning_depth_roster_provenance_required';
    END IF;
    -- The pair must identify a real, PUBLISHED section_master roster. Draft
    -- versions never appear in ros_gis.sections_current (the app snapshot source
    -- filters status='active'), so requiring a non-draft status rejects a
    -- fabricated empty-draft pair without ever refusing a legitimate submission.
    -- status is checked only as published vs draft; a since-superseded snapshot
    -- stays valid ("snapshot used", not "active at commit").
    IF NOT EXISTS (
        SELECT 1
        FROM ros_gis.dataset_versions
        WHERE dataset_version_id = NEW.roster_dataset_version_id
          AND source_hash = NEW.roster_source_hash
          AND dataset_kind = 'section_master'
          AND status <> 'draft'
    ) THEN
        RAISE EXCEPTION 'planning_depth_roster_provenance_unknown';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS planning_depth_require_roster_provenance
ON water_planning.planning_depth_submissions;
CREATE TRIGGER planning_depth_require_roster_provenance
BEFORE INSERT ON water_planning.planning_depth_submissions
FOR EACH ROW
EXECUTE FUNCTION water_planning.require_planning_depth_roster_provenance();
