-- Wave 2.5 (HIGH #5): dataset-version parent + effective-dated immutable history
-- for the section master and the section->gate crosswalk, plus current views and
-- hardening of the current projection tables. DDL only — no data statements.
-- Apply:    python migrations/migrate.py apply 0001_dataset_version_parent
-- Rollback: python migrations/migrate.py rollback 0001_dataset_version_parent

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS ros_gis;

CREATE TABLE ros_gis.dataset_versions (
    dataset_version_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_kind VARCHAR(30) NOT NULL
        CHECK (dataset_kind IN ('section_master', 'gate_crosswalk')),
    source_hash VARCHAR(64) NOT NULL,
    source_description VARCHAR(500),
    status VARCHAR(15) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'superseded')),
    effective_from TIMESTAMPTZ,
    effective_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_version_id, dataset_kind),
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_from < effective_to)
);

CREATE UNIQUE INDEX uq_dataset_versions_one_active_per_kind
    ON ros_gis.dataset_versions (dataset_kind) WHERE status = 'active';

CREATE TABLE ros_gis.section_master_history (
    dataset_version_id INTEGER NOT NULL,
    dataset_kind VARCHAR(30) NOT NULL DEFAULT 'section_master'
        CHECK (dataset_kind = 'section_master'),
    section_id VARCHAR(50) NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    zone INTEGER NOT NULL,
    source_code VARCHAR(50),
    area_hectares NUMERIC(10, 2),
    area_rai NUMERIC(12, 2),
    irrigation_channel VARCHAR(100),
    delivery_gate VARCHAR(50),
    geometry geometry(MULTIPOLYGON, 4326),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_version_id, section_id, valid_from),
    FOREIGN KEY (dataset_version_id, dataset_kind)
        REFERENCES ros_gis.dataset_versions (dataset_version_id, dataset_kind),
    CHECK (valid_to IS NULL OR valid_from < valid_to),
    CONSTRAINT excl_section_history_overlapping_validity
        EXCLUDE USING gist (
            dataset_version_id WITH =,
            section_id WITH =,
            tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz)) WITH &&
        )
);

CREATE TABLE ros_gis.gate_mapping_history (
    dataset_version_id INTEGER NOT NULL,
    dataset_kind VARCHAR(30) NOT NULL DEFAULT 'gate_crosswalk'
        CHECK (dataset_kind = 'gate_crosswalk'),
    section_id VARCHAR(50) NOT NULL,
    gate_id VARCHAR(50) NOT NULL
        CHECK (gate_id ~ '^M ?\(\d+,\d+(; ?\d+,\d+)*\)$'),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    irrigation_channel VARCHAR(100),
    distance_km NUMERIC(6, 2),
    travel_time_hours NUMERIC(5, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_version_id, section_id, gate_id, valid_from),
    FOREIGN KEY (dataset_version_id, dataset_kind)
        REFERENCES ros_gis.dataset_versions (dataset_version_id, dataset_kind),
    CHECK (valid_to IS NULL OR valid_from < valid_to),
    CONSTRAINT excl_gate_mapping_history_overlapping_validity
        EXCLUDE USING gist (
            dataset_version_id WITH =,
            section_id WITH =,
            gate_id WITH =,
            tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz)) WITH &&
        ),
    CONSTRAINT excl_gate_mapping_history_one_primary_per_interval
        EXCLUDE USING gist (
            dataset_version_id WITH =,
            section_id WITH =,
            tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz)) WITH &&
        ) WHERE (is_primary)
);

CREATE FUNCTION ros_gis.reject_immutable_dataset_row_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'versioned dataset history is immutable';
END
$$;

CREATE TRIGGER section_master_history_is_immutable
    BEFORE UPDATE OR DELETE ON ros_gis.section_master_history
    FOR EACH ROW EXECUTE FUNCTION ros_gis.reject_immutable_dataset_row_change();

CREATE TRIGGER gate_mapping_history_is_immutable
    BEFORE UPDATE OR DELETE ON ros_gis.gate_mapping_history
    FOR EACH ROW EXECUTE FUNCTION ros_gis.reject_immutable_dataset_row_change();

-- Current views: the ACTIVE dataset's rows whose validity covers now().
CREATE OR REPLACE VIEW ros_gis.sections_current AS
    SELECT h.*
    FROM ros_gis.section_master_history h
    JOIN ros_gis.dataset_versions dv USING (dataset_version_id)
    WHERE dv.dataset_kind = 'section_master'
      AND dv.status = 'active'
      AND (dv.effective_from IS NULL OR dv.effective_from <= now())
      AND (dv.effective_to IS NULL OR now() < dv.effective_to)
      AND h.valid_from <= now()
      AND (h.valid_to IS NULL OR now() < h.valid_to);

CREATE OR REPLACE VIEW ros_gis.gate_mappings_current AS
    SELECT h.*
    FROM ros_gis.gate_mapping_history h
    JOIN ros_gis.dataset_versions dv USING (dataset_version_id)
    WHERE dv.dataset_kind = 'gate_crosswalk'
      AND dv.status = 'active'
      AND (dv.effective_from IS NULL OR dv.effective_from <= now())
      AND (dv.effective_to IS NULL OR now() < dv.effective_to)
      AND h.valid_from <= now()
      AND (h.valid_to IS NULL OR now() < h.valid_to);

-- Hardening of the CURRENT projection tables (empty today; the RID-gated 2.5
-- load populates them at dataset activation).
ALTER TABLE IF EXISTS ros_gis.sections
    ADD COLUMN IF NOT EXISTS irrigation_channel VARCHAR(100);

ALTER TABLE IF EXISTS ros_gis.sections
    ALTER COLUMN geometry TYPE geometry(GEOMETRY, 4326)
    USING geometry;

DO $$
BEGIN
    IF to_regclass('ros_gis.sections') IS NOT NULL
       AND NOT EXISTS (
           SELECT 1
           FROM pg_constraint
           WHERE conrelid = to_regclass('ros_gis.sections')
             AND conname = 'chk_sections_polygonal_geometry'
       ) THEN
        ALTER TABLE ros_gis.sections
            ADD CONSTRAINT chk_sections_polygonal_geometry
            CHECK (
                geometry IS NULL
                OR GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')
            ) NOT VALID;
        ALTER TABLE ros_gis.sections
            VALIDATE CONSTRAINT chk_sections_polygonal_geometry;
    END IF;
END
$$;

ALTER TABLE IF EXISTS ros_gis.gate_mappings
    ADD COLUMN IF NOT EXISTS irrigation_channel VARCHAR(100);

DO $$
BEGIN
    IF to_regclass('ros_gis.gate_mappings') IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM ros_gis.gate_mappings WHERE is_primary IS NULL
        ) THEN
            RAISE EXCEPTION 'gate mappings contain null is_primary values; resolve before migration';
        END IF;

        ALTER TABLE ros_gis.gate_mappings
            ALTER COLUMN is_primary SET DEFAULT false,
            ALTER COLUMN is_primary SET NOT NULL;
    END IF;
END
$$;

DO $$
DECLARE
    duplicate_section VARCHAR(50);
BEGIN
    IF to_regclass('ros_gis.gate_mappings') IS NOT NULL
       AND to_regclass('ros_gis.uq_gate_mappings_one_primary_per_section') IS NULL THEN
        SELECT section_id
        INTO duplicate_section
        FROM ros_gis.gate_mappings
        WHERE is_primary AND section_id IS NOT NULL
        GROUP BY section_id
        HAVING COUNT(*) > 1
        LIMIT 1;

        IF duplicate_section IS NOT NULL THEN
            RAISE EXCEPTION 'duplicate primary gate mappings for section %; resolve before migration',
                duplicate_section;
        END IF;

        CREATE UNIQUE INDEX uq_gate_mappings_one_primary_per_section
            ON ros_gis.gate_mappings (section_id) WHERE is_primary;
    END IF;
END
$$;
