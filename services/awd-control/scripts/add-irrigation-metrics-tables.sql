-- AWD Control Service - Irrigation Metrics Tables
-- This script adds tables for tracking actual irrigation performance and learning

-- =====================================================
-- Add columns to existing tables
-- =====================================================

-- Add flow rate tracking to irrigation_schedules
ALTER TABLE awd.irrigation_schedules 
ADD COLUMN IF NOT EXISTS target_level_cm DECIMAL(6, 2),
ADD COLUMN IF NOT EXISTS initial_level_cm DECIMAL(6, 2),
ADD COLUMN IF NOT EXISTS final_level_cm DECIMAL(6, 2),
ADD COLUMN IF NOT EXISTS avg_flow_rate_cm_per_min DECIMAL(6, 4),
ADD COLUMN IF NOT EXISTS sensor_check_interval_seconds INTEGER DEFAULT 300,
ADD COLUMN IF NOT EXISTS anomaly_detected BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS anomaly_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS weather_conditions JSONB;

-- =====================================================
-- New tables for production system
-- =====================================================

-- Irrigation monitoring records (real-time tracking)
CREATE TABLE IF NOT EXISTS awd.irrigation_monitoring (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  schedule_id UUID REFERENCES awd.irrigation_schedules(id),
  field_id UUID REFERENCES awd.awd_fields(id),
  timestamp TIMESTAMPTZ NOT NULL,
  water_level_cm DECIMAL(6, 2),
  flow_rate_cm_per_min DECIMAL(6, 4),
  gate_status JSONB, -- {gate_id: open/closed/percent}
  sensor_id VARCHAR(50),
  sensor_reliability DECIMAL(3, 2), -- 0.0 to 1.0
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Irrigation performance history (for learning)
CREATE TABLE IF NOT EXISTS awd.irrigation_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id UUID REFERENCES awd.awd_fields(id),
  schedule_id UUID REFERENCES awd.irrigation_schedules(id),
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ NOT NULL,
  initial_level_cm DECIMAL(6, 2),
  target_level_cm DECIMAL(6, 2),
  achieved_level_cm DECIMAL(6, 2),
  total_duration_minutes INTEGER,
  water_volume_liters DECIMAL(12, 2),
  avg_flow_rate_cm_per_min DECIMAL(6, 4),
  max_flow_rate_cm_per_min DECIMAL(6, 4),
  min_flow_rate_cm_per_min DECIMAL(6, 4),
  
  -- Environmental conditions
  avg_temperature DECIMAL(5, 2),
  total_rainfall_mm DECIMAL(6, 2),
  soil_moisture_start DECIMAL(5, 2),
  soil_moisture_end DECIMAL(5, 2),
  concurrent_irrigations INTEGER, -- Other fields irrigating
  
  -- Performance metrics
  efficiency_score DECIMAL(3, 2), -- 0.0 to 1.0
  water_saved_percent DECIMAL(5, 2),
  anomalies_detected INTEGER DEFAULT 0,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Irrigation anomalies tracking
CREATE TABLE IF NOT EXISTS awd.irrigation_anomalies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  schedule_id UUID REFERENCES awd.irrigation_schedules(id),
  field_id UUID REFERENCES awd.awd_fields(id),
  detected_at TIMESTAMPTZ NOT NULL,
  anomaly_type VARCHAR(50) NOT NULL, -- 'low_flow', 'no_rise', 'rapid_drop', 'sensor_failure'
  severity VARCHAR(20) NOT NULL, -- 'warning', 'critical'
  description TEXT,
  metrics JSONB, -- Detailed metrics at time of detection
  resolution_action VARCHAR(100),
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Flow rate predictions (ML model outputs)
CREATE TABLE IF NOT EXISTS awd.flow_rate_predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id UUID REFERENCES awd.awd_fields(id),
  prediction_time TIMESTAMPTZ NOT NULL,
  conditions JSONB NOT NULL, -- Input conditions for prediction
  predicted_flow_rate DECIMAL(6, 4),
  confidence_interval_lower DECIMAL(6, 4),
  confidence_interval_upper DECIMAL(6, 4),
  model_version VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gate control logs
CREATE TABLE IF NOT EXISTS awd.gate_control_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id UUID REFERENCES awd.awd_fields(id),
  gate_id VARCHAR(50) NOT NULL,
  action VARCHAR(20) NOT NULL, -- 'open', 'close', 'set_flow'
  action_value DECIMAL(5, 2), -- Percentage for set_flow
  requested_at TIMESTAMPTZ NOT NULL,
  executed_at TIMESTAMPTZ,
  success BOOLEAN,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- Indexes for performance
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_irrigation_monitoring_schedule_time 
ON awd.irrigation_monitoring(schedule_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_irrigation_monitoring_field_time 
ON awd.irrigation_monitoring(field_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_irrigation_performance_field_time 
ON awd.irrigation_performance(field_id, start_time DESC);

CREATE INDEX IF NOT EXISTS idx_irrigation_anomalies_field_time 
ON awd.irrigation_anomalies(field_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_irrigation_anomalies_type 
ON awd.irrigation_anomalies(anomaly_type);

CREATE INDEX IF NOT EXISTS idx_flow_predictions_field_time 
ON awd.flow_rate_predictions(field_id, prediction_time DESC);

CREATE INDEX IF NOT EXISTS idx_gate_control_field_time 
ON awd.gate_control_logs(field_id, requested_at DESC);

-- =====================================================
-- TimescaleDB hypertables for high-frequency data
-- =====================================================

-- These go in sensor_data database
-- Run separately against TimescaleDB

/*
-- In sensor_data database:
CREATE TABLE IF NOT EXISTS irrigation_sensor_readings (
  time TIMESTAMPTZ NOT NULL,
  schedule_id UUID NOT NULL,
  field_id UUID NOT NULL,
  sensor_id VARCHAR(50) NOT NULL,
  water_level_cm DECIMAL(6, 2),
  flow_rate_cm_per_min DECIMAL(6, 4),
  quality_score DECIMAL(3, 2),
  PRIMARY KEY (time, schedule_id, sensor_id)
);

SELECT create_hypertable('irrigation_sensor_readings', 'time',
  if_not_exists => TRUE,
  chunk_time_interval => INTERVAL '1 day'
);
*/