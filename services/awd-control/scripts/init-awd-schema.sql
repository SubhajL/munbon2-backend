-- AWD Control Service Database Initialization Script
-- This script creates all necessary schemas and tables for the AWD Control Service

-- =====================================================
-- PostgreSQL Database: munbon_dev
-- =====================================================

-- Create AWD schema
CREATE SCHEMA IF NOT EXISTS awd;

-- Set search path
SET search_path TO awd, public;

-- Create AWD fields table
CREATE TABLE IF NOT EXISTS awd.awd_fields (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_code VARCHAR(50) UNIQUE NOT NULL,
  field_name VARCHAR(100) NOT NULL,
  zone_id INTEGER NOT NULL,
  area_hectares DECIMAL(10, 2) NOT NULL,
  soil_type VARCHAR(50),
  awd_enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create AWD configurations table
CREATE TABLE IF NOT EXISTS awd.awd_configurations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id UUID REFERENCES awd.awd_fields(id) UNIQUE,
  planting_method VARCHAR(20) DEFAULT 'direct-seeded',
  start_date TIMESTAMP NOT NULL,
  current_week INTEGER DEFAULT 0,
  current_phase VARCHAR(20) DEFAULT 'preparation',
  target_water_level INTEGER DEFAULT 0,
  drying_depth_cm INTEGER DEFAULT 15,
  safe_awd_depth_cm INTEGER DEFAULT 10,
  emergency_threshold_cm INTEGER DEFAULT 25,
  growth_stage VARCHAR(50) DEFAULT 'vegetative',
  irrigation_duration_minutes INTEGER DEFAULT 120,
  priority_level INTEGER DEFAULT 5,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create AWD sensors table
CREATE TABLE IF NOT EXISTS awd.awd_sensors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sensor_id VARCHAR(50) UNIQUE NOT NULL,
  field_id UUID REFERENCES awd.awd_fields(id),
  sensor_type VARCHAR(50) NOT NULL,
  mac_address VARCHAR(17),
  calibration_offset DECIMAL(5, 2) DEFAULT 0,
  last_reading_at TIMESTAMP,
  status VARCHAR(20) DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create irrigation schedules table
CREATE TABLE IF NOT EXISTS awd.irrigation_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id UUID REFERENCES awd.awd_fields(id),
  scheduled_start TIMESTAMP NOT NULL,
  scheduled_end TIMESTAMP NOT NULL,
  actual_start TIMESTAMP,
  actual_end TIMESTAMP,
  water_volume_liters DECIMAL(12, 2),
  status VARCHAR(20) DEFAULT 'pending',
  created_by VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create AWD field cycles table
CREATE TABLE IF NOT EXISTS awd.awd_field_cycles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id UUID REFERENCES awd.awd_fields(id),
  cycle_type VARCHAR(20) NOT NULL, -- 'wetting' or 'drying'
  cycle_status VARCHAR(20) NOT NULL, -- 'active', 'completed'
  drying_start_date TIMESTAMP,
  drying_day_count INTEGER,
  target_water_level DECIMAL(6, 2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_awd_fields_zone_id ON awd.awd_fields(zone_id);
CREATE INDEX IF NOT EXISTS idx_awd_fields_awd_enabled ON awd.awd_fields(awd_enabled);
CREATE INDEX IF NOT EXISTS idx_awd_configurations_field_id ON awd.awd_configurations(field_id);
CREATE INDEX IF NOT EXISTS idx_awd_configurations_active ON awd.awd_configurations(active);
CREATE INDEX IF NOT EXISTS idx_awd_sensors_field_id ON awd.awd_sensors(field_id);
CREATE INDEX IF NOT EXISTS idx_awd_sensors_sensor_id ON awd.awd_sensors(sensor_id);
CREATE INDEX IF NOT EXISTS idx_awd_sensors_status ON awd.awd_sensors(status);
CREATE INDEX IF NOT EXISTS idx_irrigation_schedules_field_id ON awd.irrigation_schedules(field_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_schedules_status ON awd.irrigation_schedules(status);
CREATE INDEX IF NOT EXISTS idx_awd_field_cycles_field_id ON awd.awd_field_cycles(field_id);
CREATE INDEX IF NOT EXISTS idx_awd_field_cycles_cycle_status ON awd.awd_field_cycles(cycle_status);

-- Grant permissions (adjust as needed)
GRANT ALL PRIVILEGES ON SCHEMA awd TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA awd TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA awd TO postgres;