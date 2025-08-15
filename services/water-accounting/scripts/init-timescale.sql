-- Initialize TimescaleDB for Water Accounting Service
-- This script creates hypertables and continuous aggregates for time-series data

-- Create TimescaleDB extension if not exists
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create flow measurements table
CREATE TABLE IF NOT EXISTS flow_measurements (
    time TIMESTAMPTZ NOT NULL,
    gate_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    flow_rate_m3s DOUBLE PRECISION NOT NULL,
    cumulative_volume_m3 DOUBLE PRECISION,
    measurement_quality DOUBLE PRECISION DEFAULT 1.0,
    gate_opening DOUBLE PRECISION,
    water_level_m DOUBLE PRECISION,
    velocity_ms DOUBLE PRECISION,
    data_source TEXT DEFAULT 'automated',
    PRIMARY KEY (time, gate_id, section_id)
);

-- Convert to hypertable with 1 day chunks
SELECT create_hypertable(
    'flow_measurements', 
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_flow_section_time 
ON flow_measurements (section_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_flow_gate_time 
ON flow_measurements (gate_id, time DESC);

-- Create continuous aggregate for hourly statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_flow_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    gate_id,
    section_id,
    AVG(flow_rate_m3s) as avg_flow_rate,
    MAX(flow_rate_m3s) as max_flow_rate,
    MIN(flow_rate_m3s) as min_flow_rate,
    SUM(flow_rate_m3s * 900) as volume_m3, -- 15-min intervals * 900 seconds
    COUNT(*) as measurement_count,
    AVG(measurement_quality) as avg_quality
FROM flow_measurements
GROUP BY hour, gate_id, section_id
WITH NO DATA;

-- Create continuous aggregate for daily statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_flow_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    gate_id,
    section_id,
    AVG(flow_rate_m3s) as avg_flow_rate,
    MAX(flow_rate_m3s) as max_flow_rate,
    MIN(flow_rate_m3s) as min_flow_rate,
    SUM(flow_rate_m3s * 900) as daily_volume_m3,
    COUNT(*) as measurement_count,
    AVG(measurement_quality) as avg_quality
FROM flow_measurements
GROUP BY day, gate_id, section_id
WITH NO DATA;

-- Create environmental conditions table for loss calculations
CREATE TABLE IF NOT EXISTS environmental_conditions (
    time TIMESTAMPTZ NOT NULL,
    section_id TEXT NOT NULL,
    air_temperature_c DOUBLE PRECISION,
    humidity_percent DOUBLE PRECISION,
    wind_speed_ms DOUBLE PRECISION,
    solar_radiation_wm2 DOUBLE PRECISION,
    rainfall_mm DOUBLE PRECISION,
    evaporation_mm DOUBLE PRECISION,
    data_source TEXT,
    PRIMARY KEY (time, section_id)
);

-- Convert to hypertable
SELECT create_hypertable(
    'environmental_conditions', 
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create gate operation logs
CREATE TABLE IF NOT EXISTS gate_operation_logs (
    time TIMESTAMPTZ NOT NULL,
    gate_id TEXT NOT NULL,
    operation_type TEXT NOT NULL, -- 'open', 'close', 'adjust'
    from_opening DOUBLE PRECISION,
    to_opening DOUBLE PRECISION,
    operator_id TEXT,
    reason TEXT,
    PRIMARY KEY (time, gate_id)
);

-- Convert to hypertable
SELECT create_hypertable(
    'gate_operation_logs', 
    'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Create retention policies (keep detailed data for 1 year, aggregated for 5 years)
SELECT add_retention_policy('flow_measurements', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('environmental_conditions', INTERVAL '1 year', if_not_exists => TRUE);
SELECT add_retention_policy('gate_operation_logs', INTERVAL '2 years', if_not_exists => TRUE);

-- Create continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('hourly_flow_stats',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy('daily_flow_stats',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create compression policies for older data
ALTER TABLE flow_measurements SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'gate_id,section_id'
);

SELECT add_compression_policy('flow_measurements', INTERVAL '7 days', if_not_exists => TRUE);

-- Create helper functions for volume integration
CREATE OR REPLACE FUNCTION calculate_volume_trapezoidal(
    p_gate_id TEXT,
    p_section_id TEXT,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_total_volume DOUBLE PRECISION := 0;
    v_prev_time TIMESTAMPTZ;
    v_prev_flow DOUBLE PRECISION;
    v_curr_time TIMESTAMPTZ;
    v_curr_flow DOUBLE PRECISION;
    v_time_diff DOUBLE PRECISION;
BEGIN
    -- Use cursor to iterate through measurements
    FOR v_curr_time, v_curr_flow IN
        SELECT time, flow_rate_m3s
        FROM flow_measurements
        WHERE gate_id = p_gate_id
          AND section_id = p_section_id
          AND time BETWEEN p_start_time AND p_end_time
        ORDER BY time
    LOOP
        IF v_prev_time IS NOT NULL THEN
            -- Calculate time difference in seconds
            v_time_diff := EXTRACT(EPOCH FROM (v_curr_time - v_prev_time));
            -- Trapezoidal integration
            v_total_volume := v_total_volume + ((v_prev_flow + v_curr_flow) / 2.0) * v_time_diff;
        END IF;
        
        v_prev_time := v_curr_time;
        v_prev_flow := v_curr_flow;
    END LOOP;
    
    RETURN v_total_volume;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed)
GRANT SELECT, INSERT ON flow_measurements TO water_accounting_user;
GRANT SELECT ON hourly_flow_stats TO water_accounting_user;
GRANT SELECT ON daily_flow_stats TO water_accounting_user;
GRANT SELECT, INSERT ON environmental_conditions TO water_accounting_user;
GRANT SELECT, INSERT ON gate_operation_logs TO water_accounting_user;