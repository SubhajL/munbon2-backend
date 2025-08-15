-- Check current hypertable status
SELECT hypertable_schema, hypertable_name
FROM timescaledb_information.hypertables
WHERE hypertable_schema = 'public';

-- Drop hypertable conversion if exists (keeps the data)
SELECT drop_chunks('moisture_readings', older_than => INTERVAL '1000 years');
SELECT drop_chunks('water_level_readings', older_than => INTERVAL '1000 years');

-- Convert back to regular tables
ALTER TABLE moisture_readings SET (timescaledb.hypertable = false);
ALTER TABLE water_level_readings SET (timescaledb.hypertable = false);

-- Or if above doesn't work, recreate tables
BEGIN;

-- Backup existing data if any
CREATE TEMP TABLE moisture_readings_backup AS SELECT * FROM moisture_readings;
CREATE TEMP TABLE water_level_readings_backup AS SELECT * FROM water_level_readings;

-- Drop existing tables
DROP TABLE IF EXISTS moisture_readings CASCADE;
DROP TABLE IF EXISTS water_level_readings CASCADE;

-- Recreate as regular tables first
CREATE TABLE moisture_readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    location_lat DECIMAL(10, 6),
    location_lng DECIMAL(10, 6),
    moisture_surface_pct DECIMAL(5, 2),
    moisture_deep_pct DECIMAL(5, 2),
    temp_surface_c DECIMAL(5, 2),
    temp_deep_c DECIMAL(5, 2),
    ambient_humidity_pct DECIMAL(5, 2),
    ambient_temp_c DECIMAL(5, 2),
    flood_status BOOLEAN DEFAULT false,
    voltage DECIMAL(5, 2),
    quality_score DECIMAL(3, 2) DEFAULT 1.0
);

CREATE TABLE water_level_readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    location_lat DECIMAL(10, 6),
    location_lng DECIMAL(10, 6),
    level_cm DECIMAL(10, 2) NOT NULL,
    voltage DECIMAL(5, 2),
    rssi INTEGER,
    temperature DECIMAL(5, 2),
    quality_score DECIMAL(3, 2) DEFAULT 1.0
);

-- Convert to hypertables with proper settings
SELECT create_hypertable('moisture_readings', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE,
    migrate_data => TRUE);

SELECT create_hypertable('water_level_readings', 'time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE,
    migrate_data => TRUE);

-- Create indexes
CREATE INDEX idx_moisture_sensor_time ON moisture_readings (sensor_id, time DESC);
CREATE INDEX idx_water_level_sensor_time ON water_level_readings (sensor_id, time DESC);

-- Restore data if any
INSERT INTO moisture_readings SELECT * FROM moisture_readings_backup;
INSERT INTO water_level_readings SELECT * FROM water_level_readings_backup;

COMMIT;

-- Test inserts
INSERT INTO moisture_readings 
(time, sensor_id, location_lat, location_lng, moisture_surface_pct, moisture_deep_pct,
 temp_surface_c, temp_deep_c, ambient_humidity_pct, ambient_temp_c,
 flood_status, voltage, quality_score)
VALUES (NOW(), 'TEST-RECREATE', 14.4972, 102.1505, 38.2, 48.7, 26.2, 25.9, 55.5, 27.8, false, 4.05, 0.95);

SELECT * FROM moisture_readings WHERE sensor_id = 'TEST-RECREATE';

DELETE FROM moisture_readings WHERE sensor_id = 'TEST-RECREATE';