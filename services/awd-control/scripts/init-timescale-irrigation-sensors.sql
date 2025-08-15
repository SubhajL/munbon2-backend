-- TimescaleDB tables for high-frequency irrigation sensor data
-- Run this against the TimescaleDB instance (sensor_data database)

-- Create extension if not exists
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Irrigation sensor readings table
CREATE TABLE IF NOT EXISTS irrigation_sensor_readings (
  time TIMESTAMPTZ NOT NULL,
  schedule_id UUID NOT NULL,
  field_id UUID NOT NULL,
  sensor_id VARCHAR(50) NOT NULL,
  water_level_cm DECIMAL(6, 2),
  flow_rate_cm_per_min DECIMAL(6, 4),
  quality_score DECIMAL(3, 2),
  gate_status JSONB,
  metadata JSONB,
  PRIMARY KEY (time, schedule_id, sensor_id)
);

-- Convert to hypertable
SELECT create_hypertable('irrigation_sensor_readings', 'time',
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_irrigation_readings_schedule 
ON irrigation_sensor_readings (schedule_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_irrigation_readings_field 
ON irrigation_sensor_readings (field_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_irrigation_readings_sensor 
ON irrigation_sensor_readings (sensor_id, time DESC);

-- Add compression policy (after 7 days)
ALTER TABLE irrigation_sensor_readings SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'field_id,sensor_id'
);

SELECT add_compression_policy('irrigation_sensor_readings', INTERVAL '7 days',
  if_not_exists => TRUE
);

-- Add retention policy (keep 90 days of data)
SELECT add_retention_policy('irrigation_sensor_readings', INTERVAL '90 days',
  if_not_exists => TRUE
);

-- Continuous aggregate for hourly summaries
CREATE MATERIALIZED VIEW IF NOT EXISTS irrigation_hourly_summary
WITH (timescaledb.continuous) AS
SELECT 
  time_bucket('1 hour', time) AS hour,
  field_id,
  schedule_id,
  AVG(water_level_cm) as avg_water_level,
  MAX(water_level_cm) as max_water_level,
  MIN(water_level_cm) as min_water_level,
  AVG(flow_rate_cm_per_min) as avg_flow_rate,
  COUNT(*) as reading_count
FROM irrigation_sensor_readings
GROUP BY hour, field_id, schedule_id
WITH NO DATA;

-- Add refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('irrigation_hourly_summary',
  start_offset => INTERVAL '3 hours',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour',
  if_not_exists => TRUE
);

-- Table for high-frequency anomaly detection
CREATE TABLE IF NOT EXISTS irrigation_anomaly_events (
  time TIMESTAMPTZ NOT NULL,
  field_id UUID NOT NULL,
  schedule_id UUID NOT NULL,
  anomaly_type VARCHAR(50) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  sensor_id VARCHAR(50),
  value DECIMAL(10, 4),
  threshold DECIMAL(10, 4),
  details JSONB,
  PRIMARY KEY (time, field_id, anomaly_type)
);

-- Convert to hypertable
SELECT create_hypertable('irrigation_anomaly_events', 'time',
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '7 days'
);

-- Index for anomaly queries
CREATE INDEX IF NOT EXISTS idx_anomaly_events_field_type 
ON irrigation_anomaly_events (field_id, anomaly_type, time DESC);

-- Grant permissions
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO awd_service;
GRANT USAGE ON SCHEMA public TO awd_service;

-- Create helper functions

-- Function to get latest sensor reading
CREATE OR REPLACE FUNCTION get_latest_irrigation_reading(
  p_field_id UUID,
  p_sensor_id VARCHAR(50) DEFAULT NULL
)
RETURNS TABLE (
  time TIMESTAMPTZ,
  sensor_id VARCHAR(50),
  water_level_cm DECIMAL(6, 2),
  flow_rate_cm_per_min DECIMAL(6, 4),
  quality_score DECIMAL(3, 2)
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    r.time,
    r.sensor_id,
    r.water_level_cm,
    r.flow_rate_cm_per_min,
    r.quality_score
  FROM irrigation_sensor_readings r
  WHERE r.field_id = p_field_id
    AND (p_sensor_id IS NULL OR r.sensor_id = p_sensor_id)
  ORDER BY r.time DESC
  LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate flow statistics
CREATE OR REPLACE FUNCTION calculate_flow_statistics(
  p_schedule_id UUID,
  p_start_time TIMESTAMPTZ,
  p_end_time TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE (
  total_readings BIGINT,
  avg_flow_rate DECIMAL(6, 4),
  max_flow_rate DECIMAL(6, 4),
  min_flow_rate DECIMAL(6, 4),
  flow_variance DECIMAL(6, 4),
  total_volume_estimate DECIMAL(12, 2)
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    COUNT(*) as total_readings,
    AVG(flow_rate_cm_per_min) as avg_flow_rate,
    MAX(flow_rate_cm_per_min) as max_flow_rate,
    MIN(flow_rate_cm_per_min) as min_flow_rate,
    VARIANCE(flow_rate_cm_per_min) as flow_variance,
    SUM(flow_rate_cm_per_min * 
        EXTRACT(EPOCH FROM (
          LEAD(time, 1, p_end_time) OVER (ORDER BY time) - time
        ))/60
    ) * 10000 as total_volume_estimate -- Convert to liters for 1 hectare
  FROM irrigation_sensor_readings
  WHERE schedule_id = p_schedule_id
    AND time BETWEEN p_start_time AND p_end_time
    AND flow_rate_cm_per_min IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Verification query
SELECT 
  'irrigation_sensor_readings' as table_name,
  COUNT(*) as row_count,
  pg_size_pretty(pg_total_relation_size('irrigation_sensor_readings')) as table_size
FROM irrigation_sensor_readings
UNION ALL
SELECT 
  'irrigation_anomaly_events' as table_name,
  COUNT(*) as row_count,
  pg_size_pretty(pg_total_relation_size('irrigation_anomaly_events')) as table_size
FROM irrigation_anomaly_events;