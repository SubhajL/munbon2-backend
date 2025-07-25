-- Create AWD tables in munbon_dev
\c munbon_dev

-- Ensure PostGIS is enabled
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create AWD schema if not exists
CREATE SCHEMA IF NOT EXISTS awd;

-- Set search path
SET search_path TO awd, public;

-- AWD Configuration Tables
CREATE TABLE IF NOT EXISTS awd.awd_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_name VARCHAR(255) NOT NULL,
    field_code VARCHAR(100) UNIQUE NOT NULL,
    area_hectares DECIMAL(10,2),
    location GEOMETRY(Point, 4326),
    zone_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS awd.awd_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id UUID REFERENCES awd.awd_fields(id),
    water_level_min DECIMAL(5,2),
    water_level_max DECIMAL(5,2),
    irrigation_threshold DECIMAL(5,2),
    drainage_threshold DECIMAL(5,2),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS awd.irrigation_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id UUID REFERENCES awd.awd_fields(id),
    scheduled_date DATE,
    scheduled_time TIME,
    duration_minutes INTEGER,
    water_amount_mm DECIMAL(5,2),
    status VARCHAR(50) DEFAULT 'scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS awd.awd_field_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id UUID REFERENCES awd.awd_fields(id),
    cycle_type VARCHAR(20) NOT NULL,
    cycle_status VARCHAR(20) NOT NULL,
    drying_start_date TIMESTAMP,
    drying_day_count INTEGER,
    target_water_level DECIMAL(6, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_awd_fields_location ON awd.awd_fields USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_awd_fields_zone ON awd.awd_fields(zone_id);
CREATE INDEX IF NOT EXISTS idx_awd_config_field ON awd.awd_configurations(field_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_field_date ON awd.irrigation_schedules(field_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_awd_sensors_field ON awd.awd_sensors(field_id);
CREATE INDEX IF NOT EXISTS idx_awd_field_cycles_field ON awd.awd_field_cycles(field_id);

-- Grant permissions
GRANT ALL ON SCHEMA awd TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA awd TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA awd TO postgres;

-- List tables in AWD schema
\dt awd.*