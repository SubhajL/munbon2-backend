-- Fix EC2 Tables to be TimescaleDB Hypertables

-- First, check if tables exist and their structure
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('water_level_readings', 'moisture_readings', 'sensor_location_history');

-- Check existing hypertables
SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_schema = 'public';

-- Drop foreign key constraints if they exist
ALTER TABLE IF EXISTS water_level_readings DROP CONSTRAINT IF EXISTS water_level_readings_sensor_id_fkey CASCADE;
ALTER TABLE IF EXISTS moisture_readings DROP CONSTRAINT IF EXISTS moisture_readings_sensor_id_fkey CASCADE;
ALTER TABLE IF EXISTS sensor_location_history DROP CONSTRAINT IF EXISTS sensor_location_history_sensor_id_fkey CASCADE;

-- Create hypertables for tables that aren't already hypertables
DO $$
BEGIN
    -- Check if water_level_readings is already a hypertable
    IF NOT EXISTS (
        SELECT 1 FROM _timescaledb_catalog.hypertable 
        WHERE table_name = 'water_level_readings' AND schema_name = 'public'
    ) THEN
        -- Check if column 'time' exists, if not use 'timestamp'
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'water_level_readings' 
              AND column_name = 'time'
        ) THEN
            PERFORM create_hypertable('water_level_readings', 'time', migrate_data => true);
            RAISE NOTICE 'Created hypertable for water_level_readings on column time';
        ELSIF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'water_level_readings' 
              AND column_name = 'timestamp'
        ) THEN
            PERFORM create_hypertable('water_level_readings', 'timestamp', migrate_data => true);
            RAISE NOTICE 'Created hypertable for water_level_readings on column timestamp';
        ELSE
            RAISE NOTICE 'water_level_readings table not found or has no time column';
        END IF;
    ELSE
        RAISE NOTICE 'water_level_readings is already a hypertable';
    END IF;

    -- Check if moisture_readings is already a hypertable
    IF NOT EXISTS (
        SELECT 1 FROM _timescaledb_catalog.hypertable 
        WHERE table_name = 'moisture_readings' AND schema_name = 'public'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'moisture_readings' 
              AND column_name = 'time'
        ) THEN
            PERFORM create_hypertable('moisture_readings', 'time', migrate_data => true);
            RAISE NOTICE 'Created hypertable for moisture_readings on column time';
        ELSIF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'moisture_readings' 
              AND column_name = 'timestamp'
        ) THEN
            PERFORM create_hypertable('moisture_readings', 'timestamp', migrate_data => true);
            RAISE NOTICE 'Created hypertable for moisture_readings on column timestamp';
        ELSE
            RAISE NOTICE 'moisture_readings table not found or has no time column';
        END IF;
    ELSE
        RAISE NOTICE 'moisture_readings is already a hypertable';
    END IF;

    -- Check if sensor_location_history exists and has data
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'sensor_location_history' AND table_schema = 'public'
    ) AND EXISTS (
        SELECT 1 FROM sensor_location_history LIMIT 1
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM _timescaledb_catalog.hypertable 
            WHERE table_name = 'sensor_location_history' AND schema_name = 'public'
        ) THEN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'sensor_location_history' 
                  AND column_name = 'timestamp'
            ) THEN
                PERFORM create_hypertable('sensor_location_history', 'timestamp', migrate_data => true);
                RAISE NOTICE 'Created hypertable for sensor_location_history';
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'sensor_location_history' 
                  AND column_name = 'time'
            ) THEN
                PERFORM create_hypertable('sensor_location_history', 'time', migrate_data => true);
                RAISE NOTICE 'Created hypertable for sensor_location_history';
            END IF;
        END IF;
    ELSE
        RAISE NOTICE 'sensor_location_history is empty or does not exist, skipping';
    END IF;
END
$$;

-- Verify hypertables were created
SELECT hypertable_name, hypertable_schema 
FROM timescaledb_information.hypertables 
WHERE hypertable_schema = 'public'
ORDER BY hypertable_name;