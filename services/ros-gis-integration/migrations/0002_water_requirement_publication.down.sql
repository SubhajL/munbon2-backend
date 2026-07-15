-- Rollback of 0002_water_requirement_publication. Only migration-owned
-- publication objects are removed; dataset parents and legacy daily_demands survive.

DROP TABLE IF EXISTS ros_gis.water_requirement_contributions;

DROP TABLE IF EXISTS ros_gis.daily_water_requirements;

DROP TABLE IF EXISTS ros_gis.water_requirement_runs;

DROP FUNCTION IF EXISTS ros_gis.reject_water_requirement_item_change();

DROP FUNCTION IF EXISTS ros_gis.validate_daily_requirement_run();

DROP FUNCTION IF EXISTS ros_gis.validate_water_requirement_contribution_run();

DROP FUNCTION IF EXISTS ros_gis.enforce_water_requirement_run_transition();
