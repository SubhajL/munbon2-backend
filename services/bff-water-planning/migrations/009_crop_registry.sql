-- F-07: give gis.crop_registry a tracked schema + loader.
--
-- Previously the table was read by scripts (populate_weekly_demands_with_events.py) but
-- written by NOTHING in-repo, so it had no reproducible population path. These columns are
-- exactly what the readers use (layer_name, sec_no, area_rai, status) and what
-- scripts/load_crop_registry.py populates.
--
-- Long-term: retire gis.crop_registry in favour of gis.agricultural_plots (the maintained
-- table), per the ROS/ros_gis single-source-of-truth decision (F-06).
CREATE SCHEMA IF NOT EXISTS gis;

CREATE TABLE IF NOT EXISTS gis.crop_registry (
    id          SERIAL PRIMARY KEY,
    layer_name  TEXT        NOT NULL,
    sec_no      INTEGER     NOT NULL,
    area_rai    NUMERIC     NOT NULL CHECK (area_rai >= 0),
    status      TEXT        NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crop_registry_active
    ON gis.crop_registry (status) WHERE status = 'active';
