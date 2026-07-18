-- 0006_control_plan_campaign_identity (PR 4.4b-4)
-- Additive: an IMMUTABLE mapping from a stable campaign_id to its monotonic
-- plan_version sequence, so a rolling plan keeps ONE campaign identity across an
-- append-only chain of immutable versions. NEVER edits 0001-0005 and NEVER
-- touches the immutable control_plan_runs rows. Ids are UUID/INTEGER, never JSONB.
--
-- Backfill (below): every existing control_plan_runs row becomes a SINGLETON
-- campaign (campaign_id = plan_id, plan_version = its current version). A fresh
-- draft created through allocate_campaign_version instead gets a NEW campaign_id
-- distinct from its plan_id, so a singleton row is EXACTLY a legacy backfill row.
--
-- OPERATIONAL REQUIREMENT — DRAINED-WRITER CUTOVER (not a two-phase migration):
-- STOP every scheduler writer before applying 0006. From 4.4b-4 on, create_draft
-- inserts a control_plan_runs row and its campaign mapping row in ONE transaction;
-- a legacy (pre-4.4b-4) writer inserts a run with NO mapping. If such a writer
-- commits a run AFTER 0006's backfill has already scanned control_plan_runs, that
-- run has no mapping and is an ORPHAN. Reads fail closed on it (the repository's
-- _assemble + the campaign projection raise on a missing mapping -> HTTP 503), so
-- an orphan is never served silently, but it is unreadable until fixed forward.
-- The single-instance migrate-before-start deploy (one PM2 process, migrate then
-- boot) already satisfies this drain; a rolling deploy with writer overlap MUST
-- drain the old writers first. Do NOT "repair" an orphan with a runtime
-- backfill-on-read: that would mutate an immutable row on the read path. The
-- remedy is a forward-fix migration that maps any orphaned run as a singleton.

CREATE TABLE scheduler.control_plan_campaign_versions (
    campaign_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    plan_id UUID NOT NULL,
    CONSTRAINT control_plan_campaign_versions_pkey
        PRIMARY KEY (campaign_id, plan_version),
    CONSTRAINT control_plan_campaign_versions_plan_key
        UNIQUE (plan_id, plan_version),
    CONSTRAINT control_plan_campaign_versions_version_positive
        CHECK (plan_version > 0),
    -- DEFERRABLE INITIALLY DEFERRED: a run row and its mapping row are inserted in
    -- ONE transaction and the FK is checked at COMMIT, so they land atomically —
    -- a mapping row can never reference a run that did not also commit.
    CONSTRAINT control_plan_campaign_versions_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        DEFERRABLE INITIALLY DEFERRED
);

-- Explicit campaign-scoped lookup index. (The PK's leading column already covers
-- campaign_id, so this is a small belt-and-suspenders per the migration plan.)
CREATE INDEX control_plan_campaign_versions_campaign_idx
    ON scheduler.control_plan_campaign_versions (campaign_id);

-- Append-only: reuse the 0001 immutability trigger function (no UPDATE/DELETE).
CREATE TRIGGER control_plan_campaign_versions_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_plan_campaign_versions
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();

-- Backfill legacy rows as singleton campaigns WITHOUT rewriting any run row.
INSERT INTO scheduler.control_plan_campaign_versions
    (campaign_id, plan_version, plan_id)
SELECT plan_id, plan_version, plan_id
FROM scheduler.control_plan_runs;
