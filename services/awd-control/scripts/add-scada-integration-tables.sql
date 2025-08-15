-- AWD Control Service - SCADA Integration Tables
-- This script adds tables for SCADA gate control integration

-- =====================================================
-- Field to Gate Station Mapping
-- =====================================================
CREATE TABLE IF NOT EXISTS awd.field_gate_mapping (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id UUID REFERENCES awd.awd_fields(id),
  station_code VARCHAR(50) NOT NULL, -- Maps to stationcode in tb_site
  gate_type VARCHAR(50) DEFAULT 'main',
  max_flow_rate DECIMAL(10, 2), -- m³/s
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(field_id, station_code)
);

-- =====================================================
-- SCADA Command Log (Local tracking)
-- =====================================================
CREATE TABLE IF NOT EXISTS awd.scada_command_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scada_command_id INTEGER NOT NULL, -- ID from tb_gatelevel_command
  field_id UUID REFERENCES awd.awd_fields(id),
  gate_name VARCHAR(50) NOT NULL, -- station code
  gate_level INTEGER NOT NULL CHECK (gate_level BETWEEN 1 AND 4),
  target_flow_rate DECIMAL(10, 2), -- m³/s
  command_time TIMESTAMPTZ NOT NULL,
  status VARCHAR(20) DEFAULT 'sent', -- sent, completed, failed
  completed_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- Canal Water Levels (From Flow Monitoring)
-- =====================================================
CREATE TABLE IF NOT EXISTS awd.canal_water_levels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  schedule_id UUID REFERENCES awd.irrigation_schedules(id),
  timestamp TIMESTAMPTZ NOT NULL,
  levels_data JSONB NOT NULL, -- Store complete response from Flow Monitoring
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- Update AWD Fields table
-- =====================================================
ALTER TABLE awd.awd_fields 
ADD COLUMN IF NOT EXISTS gate_station_code VARCHAR(50),
ADD COLUMN IF NOT EXISTS area_hectares DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS soil_percolation_rate DECIMAL(6, 2); -- m³/hr/ha

-- =====================================================
-- Update irrigation_schedules table
-- =====================================================
ALTER TABLE awd.irrigation_schedules 
ADD COLUMN IF NOT EXISTS target_flow_rate DECIMAL(10, 2), -- m³/s
ADD COLUMN IF NOT EXISTS scada_command_id INTEGER; -- Reference to tb_gatelevel_command

-- =====================================================
-- Gate Flow Calibration Table
-- =====================================================
CREATE TABLE IF NOT EXISTS awd.gate_flow_calibration (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  station_code VARCHAR(50) NOT NULL,
  gate_level INTEGER NOT NULL CHECK (gate_level BETWEEN 1 AND 4),
  measured_flow_rate DECIMAL(10, 2) NOT NULL, -- m³/s
  upstream_level DECIMAL(6, 2), -- meters
  downstream_level DECIMAL(6, 2), -- meters
  measurement_date DATE NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(station_code, gate_level, measurement_date)
);

-- =====================================================
-- Indexes
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_field_gate_mapping_field 
ON awd.field_gate_mapping(field_id);

CREATE INDEX IF NOT EXISTS idx_field_gate_mapping_station 
ON awd.field_gate_mapping(station_code);

CREATE INDEX IF NOT EXISTS idx_scada_command_log_field 
ON awd.scada_command_log(field_id);

CREATE INDEX IF NOT EXISTS idx_scada_command_log_status 
ON awd.scada_command_log(status);

CREATE INDEX IF NOT EXISTS idx_scada_command_log_time 
ON awd.scada_command_log(command_time DESC);

CREATE INDEX IF NOT EXISTS idx_canal_water_levels_schedule 
ON awd.canal_water_levels(schedule_id);

-- =====================================================
-- Sample Data for Testing
-- =====================================================
-- Map some fields to station codes (adjust based on actual data)
/*
INSERT INTO awd.field_gate_mapping (field_id, station_code, max_flow_rate)
SELECT 
  f.id,
  'WWA' || ROW_NUMBER() OVER (ORDER BY f.id),
  10.0
FROM awd.awd_fields f
LIMIT 5
ON CONFLICT DO NOTHING;

-- Sample gate flow calibration data
INSERT INTO awd.gate_flow_calibration 
(station_code, gate_level, measured_flow_rate, measurement_date)
VALUES 
  ('WWA', 1, 0.0, CURRENT_DATE),
  ('WWA', 2, 3.5, CURRENT_DATE),
  ('WWA', 3, 7.0, CURRENT_DATE),
  ('WWA', 4, 10.5, CURRENT_DATE)
ON CONFLICT DO NOTHING;
*/

-- =====================================================
-- Permissions
-- =====================================================
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA awd TO awd_service;