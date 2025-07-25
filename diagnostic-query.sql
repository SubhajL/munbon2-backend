-- Diagnostic Query for EC2 PostgreSQL
-- Run this in your database client while connected to sensor_data database

-- 1. Verify current database
SELECT current_database() as current_db, 
       current_user as connected_user,
       inet_server_addr() as server_ip,
       inet_server_port() as server_port;

-- 2. List all schemas
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
ORDER BY schema_name;

-- 3. Count tables in each schema
SELECT schemaname, COUNT(*) as table_count
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
GROUP BY schemaname
ORDER BY schemaname;

-- 4. Show all tables with row counts in public schema
SELECT 
    'public.' || tablename as full_table_name,
    (SELECT COUNT(*) FROM public.sensor_readings WHERE tablename = 'sensor_readings') as row_count
FROM pg_tables 
WHERE schemaname = 'public' AND tablename = 'sensor_readings'
UNION ALL
SELECT 
    'public.' || tablename,
    (SELECT COUNT(*) FROM public.sensor_registry WHERE tablename = 'sensor_registry')
FROM pg_tables 
WHERE schemaname = 'public' AND tablename = 'sensor_registry'
UNION ALL
SELECT 
    'public.' || tablename,
    (SELECT COUNT(*) FROM public.sensor_calibrations WHERE tablename = 'sensor_calibrations')
FROM pg_tables 
WHERE schemaname = 'public' AND tablename = 'sensor_calibrations'
ORDER BY full_table_name;

-- 5. Direct query on sensor_readings
SELECT 'Direct count from public.sensor_readings:' as query_type, COUNT(*) as count FROM public.sensor_readings
UNION ALL
SELECT 'Direct count from sensor.sensors:', COUNT(*) FROM sensor.sensors;

-- 6. Sample data from sensor_readings
SELECT * FROM public.sensor_readings LIMIT 2;