DROP INDEX IF EXISTS ros_gis.uq_water_requirement_runs_identical_nonfailed_input;
DROP TRIGGER IF EXISTS section_crop_settings_are_append_only
    ON ros_gis.section_crop_settings;
DROP FUNCTION IF EXISTS ros_gis.reject_section_crop_setting_change();
DROP TABLE IF EXISTS ros_gis.section_crop_settings;
