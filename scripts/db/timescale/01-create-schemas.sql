\c sensor_data;

-- Create schemas for organizing data
CREATE SCHEMA IF NOT EXISTS sensor;
CREATE SCHEMA IF NOT EXISTS aggregates;
CREATE SCHEMA IF NOT EXISTS maintenance;

-- Sensor metadata table
CREATE TABLE IF NOT EXISTS sensor.sensors (
  sensor_id VARCHAR(100) PRIMARY KEY,
  sensor_type VARCHAR(50) NOT NULL,
  location_lat DOUBLE PRECISION,
  location_lng DOUBLE PRECISION,
  region VARCHAR(100),
  zone VARCHAR(100),
  installation_date TIMESTAMPTZ DEFAULT NOW(),
  last_maintenance TIMESTAMPTZ,
  calibration_data JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_sensors_location_lat ON sensor.sensors(location_lat);
CREATE INDEX IF NOT EXISTS idx_sensors_location_lng ON sensor.sensors(location_lng);
CREATE INDEX IF NOT EXISTS idx_sensors_type ON sensor.sensors(sensor_type);
CREATE INDEX IF NOT EXISTS idx_sensors_active ON sensor.sensors(active);

-- Raw sensor readings table (will be converted to hypertable)
CREATE TABLE IF NOT EXISTS sensor.readings (
  time TIMESTAMPTZ NOT NULL,
  sensor_id VARCHAR(100) NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  unit VARCHAR(20) NOT NULL,
  quality_score SMALLINT DEFAULT 100,
  raw_data JSONB DEFAULT '{}',
  FOREIGN KEY (sensor_id) REFERENCES sensor.sensors(sensor_id)
);

-- Convert to hypertable
SELECT create_hypertable('sensor.readings', 'time', 
  chunk_time_interval => INTERVAL '7 days',
  if_not_exists => TRUE
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_readings_sensor_time ON sensor.readings(sensor_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_readings_time ON sensor.readings(time DESC);

-- Create continuous aggregates for 5-minute intervals
CREATE MATERIALIZED VIEW IF NOT EXISTS aggregates.readings_5min
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('5 minutes', time) AS bucket,
  sensor_id,
  AVG(value) AS avg_value,
  MIN(value) AS min_value,
  MAX(value) AS max_value,
  COUNT(*) AS sample_count
FROM sensor.readings
GROUP BY bucket, sensor_id
WITH NO DATA;

-- Add refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('aggregates.readings_5min',
  start_offset => INTERVAL '1 hour',
  end_offset => INTERVAL '10 minutes',
  schedule_interval => INTERVAL '5 minutes');