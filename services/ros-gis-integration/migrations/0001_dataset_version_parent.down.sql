-- Rollback of 0001_dataset_version_parent: drops ONLY what the up migration
-- created. The pre-existing data tables (ros_gis.sections, ros_gis.gate_mappings
-- and the rest of the pipeline) are never dropped.

DROP VIEW IF EXISTS ros_gis.gate_mappings_current;

DROP VIEW IF EXISTS ros_gis.sections_current;

DROP TABLE IF EXISTS ros_gis.gate_mapping_history;

DROP TABLE IF EXISTS ros_gis.section_master_history;

DROP TABLE IF EXISTS ros_gis.dataset_versions;

DROP FUNCTION IF EXISTS ros_gis.reject_immutable_dataset_row_change();

-- Additive hardening of the legacy current tables is deliberately retained.
-- ADD COLUMN IF NOT EXISTS cannot prove column ownership, and narrowing repaired
-- MULTIPOLYGON geometry would be destructive. Rollback removes only the versioned
-- contract objects that this migration owns unambiguously.
