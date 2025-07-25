-- Complete verification of migrated data on EC2
-- Host: 43.209.12.182, Port: 5432, User: postgres, Password: P@ssw0rd123!

-- ==================================
-- PART 1: munbon_dev database
-- ==================================
-- Connect to munbon_dev database first, then run:

-- Summary of all schemas and tables with data
SELECT 
    n.nspname as schema_name,
    c.relname as table_name,
    pg_stat_get_live_tuples(c.oid) as row_count
FROM pg_class c
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE c.relkind = 'r' 
    AND n.nspname IN ('auth', 'gis', 'ros')
    AND pg_stat_get_live_tuples(c.oid) > 0
ORDER BY n.nspname, c.relname;

-- Sample data from key tables
SELECT 'Sample from gis.canal_network:' as info;
SELECT canal_code, canal_name, canal_type FROM gis.canal_network LIMIT 3;

SELECT 'Sample from gis.control_structures:' as info;
SELECT structure_code, structure_name, structure_type FROM gis.control_structures LIMIT 3;

SELECT 'Sample from ros.kc_weekly:' as info;
SELECT crop_type, crop_week, kc_value FROM ros.kc_weekly LIMIT 3;

-- ==================================
-- PART 2: sensor_data database
-- ==================================
-- Connect to sensor_data database, then run:

-- All tables in public schema with counts
SELECT 
    'public.' || tablename as full_table_name,
    (SELECT COUNT(*) FROM public.sensor_readings WHERE tablename = 'sensor_readings') as count
FROM pg_tables WHERE schemaname = 'public' AND tablename = 'sensor_readings'
UNION ALL
SELECT 
    'public.' || tablename,
    (SELECT COUNT(*) FROM public.sensor_registry WHERE tablename = 'sensor_registry')
FROM pg_tables WHERE schemaname = 'public' AND tablename = 'sensor_registry'
UNION ALL
SELECT 
    'public.' || tablename,
    (SELECT COUNT(*) FROM public.moisture_readings WHERE tablename = 'moisture_readings')
FROM pg_tables WHERE schemaname = 'public' AND tablename = 'moisture_readings'
UNION ALL
SELECT 
    'public.' || tablename,
    (SELECT COUNT(*) FROM public.water_level_readings WHERE tablename = 'water_level_readings')
FROM pg_tables WHERE schemaname = 'public' AND tablename = 'water_level_readings'
ORDER BY full_table_name;

-- Sample sensor data
SELECT 'Sample from public.sensor_readings:' as info;
SELECT time, sensor_id, sensor_type FROM public.sensor_readings LIMIT 3;

SELECT 'Sample from public.sensor_registry:' as info;
SELECT sensor_id, sensor_type, manufacturer FROM public.sensor_registry LIMIT 3;