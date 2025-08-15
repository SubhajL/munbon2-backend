-- AWD Control Service TimescaleDB Tables Initialization Script
-- This script creates time-series tables in the sensor_data database

-- =====================================================
-- TimescaleDB Database: sensor_data
-- =====================================================

-- Set search path
SET search_path TO public;

-- Create AWD sensor readings table
CREATE TABLE IF NOT EXISTS awd_sensor_readings (
  time TIMESTAMPTZ NOT NULL,
  sensor_id VARCHAR(50) NOT NULL,
  field_id UUID NOT NULL,
  water_level_cm DECIMAL(6, 2),
  temperature_celsius DECIMAL(5, 2),
  humidity_percent DECIMAL(5, 2),
  battery_voltage DECIMAL(4, 2),
  signal_strength INTEGER,
  PRIMARY KEY (time, sensor_id)
);

-- Convert to hypertable
SELECT create_hypertable('awd_sensor_readings', 'time', 
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- Create irrigation events table
CREATE TABLE IF NOT EXISTS irrigation_events (
  time TIMESTAMPTZ NOT NULL,
  field_id UUID NOT NULL,
  event_type VARCHAR(50) NOT NULL,
  water_level_before_cm DECIMAL(6, 2),
  water_level_after_cm DECIMAL(6, 2),
  duration_minutes INTEGER,
  water_volume_liters DECIMAL(12, 2),
  gate_ids TEXT[],
  PRIMARY KEY (time, field_id)
);

-- Convert to hypertable
SELECT create_hypertable('irrigation_events', 'time',
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '7 days'
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_awd_sensor_readings_sensor_id_time ON awd_sensor_readings(sensor_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_awd_sensor_readings_field_id_time ON awd_sensor_readings(field_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_irrigation_events_field_id_time ON irrigation_events(field_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_irrigation_events_event_type ON irrigation_events(event_type);

-- Create continuous aggregates for performance (optional)
-- Average water level per hour per field
CREATE MATERIALIZED VIEW IF NOT EXISTS awd_water_level_hourly
WITH (timescaledb.continuous) AS
SELECT 
  time_bucket('1 hour', time) AS hour,
  field_id,
  AVG(water_level_cm) AS avg_water_level,
  MIN(water_level_cm) AS min_water_level,
  MAX(water_level_cm) AS max_water_level,
  COUNT(*) AS reading_count
FROM awd_sensor_readings
WHERE water_level_cm IS NOT NULL
GROUP BY hour, field_id
WITH NO DATA;

-- Add retention policy (optional - keeps 6 months of raw data)
-- SELECT add_retention_policy('awd_sensor_readings', INTERVAL '6 months');
-- SELECT add_retention_policy('irrigation_events', INTERVAL '1 year');

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;