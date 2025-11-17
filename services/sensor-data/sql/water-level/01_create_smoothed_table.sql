-- Create smoothed_water_level_readings table for storing processed water level data
-- This table stores the output of the Hampel Filter + EMA smoothing algorithm
-- Applied to raw water_level_readings to reduce noise and outliers

-- Drop table if exists for clean rebuild
DROP TABLE IF EXISTS smoothed_water_level_readings CASCADE;

-- Create the smoothed water level readings table
CREATE TABLE smoothed_water_level_readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(20) NOT NULL,
    level_cm NUMERIC(10,2) NOT NULL,
    voltage NUMERIC(6,3),
    rssi INTEGER,
    temperature NUMERIC(5,2),
    quality_score NUMERIC(5,2),
    location_lat NUMERIC(10,6),
    location_lng NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pk_smoothed_water_level PRIMARY KEY (sensor_id, time)
);

-- Create hypertable for time-series optimization
SELECT create_hypertable('smoothed_water_level_readings', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Index for sensor-based queries with time ordering
CREATE INDEX idx_smoothed_water_level_sensor_time
ON smoothed_water_level_readings(sensor_id, time DESC);

-- Index for time-range queries across all sensors
CREATE INDEX idx_smoothed_water_level_time
ON smoothed_water_level_readings(time DESC);

-- Index for location-based queries
CREATE INDEX idx_smoothed_water_level_location
ON smoothed_water_level_readings(location_lat, location_lng);

-- Add unique constraint for upsert operations
-- This allows INSERT ... ON CONFLICT DO UPDATE syntax
CREATE UNIQUE INDEX unique_smoothed_water_level_sensor_time
ON smoothed_water_level_readings(sensor_id, time);

-- Enable compression after 7 days for storage efficiency
ALTER TABLE smoothed_water_level_readings SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'sensor_id'
);

-- Create compression policy
SELECT add_compression_policy('smoothed_water_level_readings', INTERVAL '7 days');

-- Grant appropriate permissions (if role exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sensor_data_app') THEN
        GRANT SELECT, INSERT, UPDATE ON smoothed_water_level_readings TO sensor_data_app;
    END IF;
END $$;

-- Add comment for documentation
COMMENT ON TABLE smoothed_water_level_readings IS
'Stores smoothed water level readings processed through Hampel Filter + EMA algorithm.
Data is derived from raw water_level_readings table to reduce noise and outliers.
Used for visualization and analysis where data quality is critical.';

COMMENT ON COLUMN smoothed_water_level_readings.quality_score IS
'Quality metric (0-100) indicating confidence in the smoothed value based on
outlier detection, data gaps, and variance in the smoothing window';