-- F-07: give gis.crop_registry a tracked schema + loader.
--
-- Columns are EXACTLY what the readers select (verified against
-- scripts/populate_weekly_demands_with_events.py): layer_name, "Zone" (quoted,
-- case-sensitive), sec_no, area_rai, status. Only area_1 uses "Zone"
-- (IN ('1A','1B','1C')); area_2..5 ignore it, hence DEFAULT ''.
--
-- The UNIQUE key makes the loader idempotent (ON CONFLICT), so re-running the
-- population never duplicates rows (which would double-count weekly demands).
--
-- Long-term: retire gis.crop_registry for gis.agricultural_plots (F-06).
CREATE SCHEMA IF NOT EXISTS gis;

CREATE TABLE IF NOT EXISTS gis.crop_registry (
    id          SERIAL PRIMARY KEY,
    layer_name  TEXT        NOT NULL,
    "Zone"      TEXT        NOT NULL DEFAULT '',
    sec_no      INTEGER     NOT NULL,
    area_rai    NUMERIC     NOT NULL CHECK (area_rai >= 0),
    status      TEXT        NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_crop_registry_natural UNIQUE (layer_name, "Zone", sec_no)
);

CREATE INDEX IF NOT EXISTS idx_crop_registry_active
    ON gis.crop_registry (status) WHERE status = 'active';
