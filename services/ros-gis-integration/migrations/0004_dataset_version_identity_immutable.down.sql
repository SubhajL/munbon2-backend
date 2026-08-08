-- Rollback of 0004: drop the append-only / identity-immutability triggers and
-- their shared function. Removes ONLY what the up migration created; the
-- dataset_versions table and its rows are untouched.
--
-- The trigger drops are guarded by a table-existence check so that an out-of-order
-- rollback (0001 before 0004, which the runner permits) that has already dropped
-- ros_gis.dataset_versions does not error here and strand the function/registry
-- row. Normal reverse-order rollback (0004 before 0001) is unaffected. The
-- runner's tolerance of out-of-order rollback is a separate, pre-existing concern.

DO $$
BEGIN
    IF to_regclass('ros_gis.dataset_versions') IS NOT NULL THEN
        DROP TRIGGER IF EXISTS dataset_versions_no_truncate
            ON ros_gis.dataset_versions;
        DROP TRIGGER IF EXISTS dataset_versions_identity_is_immutable
            ON ros_gis.dataset_versions;
    END IF;
END
$$;

DROP FUNCTION IF EXISTS ros_gis.reject_dataset_version_identity_change();
