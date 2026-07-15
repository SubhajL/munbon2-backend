CREATE TABLE ros_gis.section_crop_settings (
    setting_id UUID PRIMARY KEY,
    section_id TEXT NOT NULL CHECK (btrim(section_id) <> ''),
    crop_type TEXT NOT NULL CHECK (btrim(crop_type) <> ''),
    planted_area_rai NUMERIC(18, 6) NOT NULL,
    expected_harvest_date DATE NOT NULL,
    source TEXT NOT NULL CHECK (btrim(source) <> ''),
    as_of_date DATE NOT NULL,
    updated_by TEXT NOT NULL CHECK (btrim(updated_by) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        planted_area_rai > 0
        AND planted_area_rai::text NOT IN ('NaN', 'Infinity', '-Infinity')
    )
);

CREATE INDEX idx_section_crop_settings_current
    ON ros_gis.section_crop_settings (section_id, as_of_date DESC, created_at DESC);

CREATE FUNCTION ros_gis.reject_section_crop_setting_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'section crop settings are append-only';
END
$$;

CREATE TRIGGER section_crop_settings_are_append_only
    BEFORE UPDATE OR DELETE ON ros_gis.section_crop_settings
    FOR EACH ROW EXECUTE FUNCTION ros_gis.reject_section_crop_setting_change();

CREATE UNIQUE INDEX uq_water_requirement_runs_identical_nonfailed_input
    ON ros_gis.water_requirement_runs (as_of_date, content_hash)
    WHERE status IN ('calculating', 'published', 'superseded');
