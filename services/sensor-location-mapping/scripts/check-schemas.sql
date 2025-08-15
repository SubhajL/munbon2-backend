-- Check schemas and tables in both databases

-- Check sensor_data database
\c sensor_data

-- List schemas
SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast');

-- Check sensor tables
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_name IN ('sensor_registry', 'water_level_readings', 'moisture_readings', 'sensor_location_history')
ORDER BY table_schema, table_name;

-- Check gis_db database
\c gis_db

-- List schemas
SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast');

-- Check GIS tables
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_name IN ('irrigation_zones', 'irrigation_blocks', 'parcels')
ORDER BY table_schema, table_name;

-- Check if PostGIS is enabled
SELECT PostGIS_Version();