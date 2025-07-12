-- Create munbon_ros database
CREATE DATABASE munbon_ros;

-- Connect to the database
\c munbon_ros;

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Crop types and characteristics
CREATE TABLE crop_types (
    id SERIAL PRIMARY KEY,
    crop_code VARCHAR(20) UNIQUE NOT NULL,
    crop_name_en VARCHAR(100),
    crop_name_th VARCHAR(100),
    crop_group VARCHAR(50),  -- 'cereal', 'vegetable', 'fruit', 'other'
    total_growing_days INTEGER,
    mad_fraction DECIMAL(3,2),  -- Management Allowed Depletion
    yield_response_factor DECIMAL(3,2),  -- Ky
    max_root_depth_m DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Crop growth stages
CREATE TABLE crop_stages (
    id SERIAL PRIMARY KEY,
    crop_code VARCHAR(20) REFERENCES crop_types(crop_code) ON DELETE CASCADE,
    stage_name VARCHAR(50),  -- 'initial', 'development', 'mid', 'late'
    stage_order INTEGER,
    duration_days INTEGER,
    kc_value DECIMAL(3,2),
    root_depth_fraction DECIMAL(3,2),
    critical_depletion DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ETo calculations log
CREATE TABLE eto_calculations (
    id SERIAL PRIMARY KEY,
    calculation_date DATE,
    location GEOGRAPHY(POINT, 4326),
    altitude_m REAL,
    tmin REAL,
    tmax REAL,
    tmean REAL,
    rhmin REAL,
    rhmax REAL,
    wind_speed_2m REAL,
    solar_radiation REAL,
    eto_value REAL,
    method VARCHAR(50),  -- 'penman-monteith', 'hargreaves'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Water demand calculations
CREATE TABLE water_demand_calculations (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50),
    field_id VARCHAR(50),
    calculation_date DATE,
    crop_code VARCHAR(20),
    growth_stage VARCHAR(50),
    area_rai DECIMAL(10,2),
    eto REAL,
    kc REAL,
    etc REAL,  -- ETc = ETo × Kc
    effective_rainfall REAL,
    soil_moisture_depletion REAL,
    net_irrigation_requirement REAL,
    gross_irrigation_requirement REAL,
    irrigation_efficiency DECIMAL(3,2),
    water_volume_m3 DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Irrigation schedules
CREATE TABLE irrigation_schedules (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(20),
    schedule_date DATE,
    total_water_required_m3 DECIMAL(15,2),
    available_water_m3 DECIMAL(15,2),
    priority_algorithm VARCHAR(50),
    status VARCHAR(20),  -- 'draft', 'approved', 'executing', 'completed'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Schedule allocations
CREATE TABLE schedule_allocations (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES irrigation_schedules(id) ON DELETE CASCADE,
    parcel_id VARCHAR(50),
    required_m3 DECIMAL(15,2),
    allocated_m3 DECIMAL(15,2),
    priority_score DECIMAL(5,2),
    deficit_m3 DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Crop calendar
CREATE TABLE crop_calendar (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(20),
    parcel_id VARCHAR(50),
    crop_code VARCHAR(20) REFERENCES crop_types(crop_code),
    planting_date DATE,
    expected_harvest_date DATE,
    actual_harvest_date DATE,
    season VARCHAR(20),  -- 'wet', 'dry'
    year INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_eto_calculations_date ON eto_calculations(calculation_date);
CREATE INDEX idx_eto_calculations_location ON eto_calculations USING GIST(location);
CREATE INDEX idx_water_demand_date ON water_demand_calculations(calculation_date);
CREATE INDEX idx_water_demand_parcel ON water_demand_calculations(parcel_id);
CREATE INDEX idx_irrigation_schedules_zone_date ON irrigation_schedules(zone_id, schedule_date);
CREATE INDEX idx_crop_calendar_zone ON crop_calendar(zone_id);
CREATE INDEX idx_crop_calendar_parcel ON crop_calendar(parcel_id);

-- Insert sample crop data
INSERT INTO crop_types (crop_code, crop_name_en, crop_name_th, crop_group, total_growing_days, mad_fraction, yield_response_factor, max_root_depth_m) VALUES
('RICE_WET', 'Rice (Wet Season)', 'ข้าวนาปี', 'cereal', 120, 0.20, 1.00, 0.60),
('RICE_DRY', 'Rice (Dry Season)', 'ข้าวนาปรัง', 'cereal', 110, 0.20, 1.00, 0.60),
('CORN', 'Corn', 'ข้าวโพด', 'cereal', 125, 0.55, 1.25, 1.00),
('SUGARCANE', 'Sugarcane', 'อ้อย', 'other', 365, 0.65, 1.20, 1.20),
('CASSAVA', 'Cassava', 'มันสำปะหลัง', 'other', 300, 0.50, 1.10, 0.80),
('VEGETABLES', 'Vegetables (General)', 'ผักทั่วไป', 'vegetable', 90, 0.50, 1.05, 0.50);

-- Rice (Wet Season) growth stages
INSERT INTO crop_stages (crop_code, stage_name, stage_order, duration_days, kc_value, root_depth_fraction, critical_depletion) VALUES
('RICE_WET', 'initial', 1, 30, 1.05, 0.10, 0.50),
('RICE_WET', 'development', 2, 30, 1.20, 0.50, 0.30),
('RICE_WET', 'mid', 3, 40, 1.20, 1.00, 0.20),
('RICE_WET', 'late', 4, 20, 0.90, 1.00, 0.20);

-- Rice (Dry Season) growth stages
INSERT INTO crop_stages (crop_code, stage_name, stage_order, duration_days, kc_value, root_depth_fraction, critical_depletion) VALUES
('RICE_DRY', 'initial', 1, 25, 1.05, 0.10, 0.50),
('RICE_DRY', 'development', 2, 30, 1.20, 0.50, 0.30),
('RICE_DRY', 'mid', 3, 35, 1.20, 1.00, 0.20),
('RICE_DRY', 'late', 4, 20, 0.90, 1.00, 0.20);

-- Corn growth stages
INSERT INTO crop_stages (crop_code, stage_name, stage_order, duration_days, kc_value, root_depth_fraction, critical_depletion) VALUES
('CORN', 'initial', 1, 20, 0.30, 0.10, 0.55),
('CORN', 'development', 2, 35, 0.70, 0.40, 0.55),
('CORN', 'mid', 3, 40, 1.20, 1.00, 0.55),
('CORN', 'late', 4, 30, 0.60, 1.00, 0.80);

-- Sugarcane growth stages
INSERT INTO crop_stages (crop_code, stage_name, stage_order, duration_days, kc_value, root_depth_fraction, critical_depletion) VALUES
('SUGARCANE', 'initial', 1, 30, 0.40, 0.10, 0.65),
('SUGARCANE', 'development', 2, 50, 0.70, 0.30, 0.65),
('SUGARCANE', 'mid', 3, 220, 1.25, 1.00, 0.65),
('SUGARCANE', 'late', 4, 65, 0.75, 1.00, 0.65);

-- Cassava growth stages
INSERT INTO crop_stages (crop_code, stage_name, stage_order, duration_days, kc_value, root_depth_fraction, critical_depletion) VALUES
('CASSAVA', 'initial', 1, 20, 0.30, 0.10, 0.50),
('CASSAVA', 'development', 2, 60, 0.60, 0.40, 0.50),
('CASSAVA', 'mid', 3, 180, 1.10, 1.00, 0.50),
('CASSAVA', 'late', 4, 40, 0.50, 1.00, 0.50);

-- Vegetables growth stages (example)
INSERT INTO crop_stages (crop_code, stage_name, stage_order, duration_days, kc_value, root_depth_fraction, critical_depletion) VALUES
('VEGETABLES', 'initial', 1, 20, 0.40, 0.20, 0.50),
('VEGETABLES', 'development', 2, 25, 0.70, 0.50, 0.50),
('VEGETABLES', 'mid', 3, 30, 1.05, 1.00, 0.50),
('VEGETABLES', 'late', 4, 15, 0.95, 1.00, 0.50);

-- Create update trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_crop_types_updated_at BEFORE UPDATE ON crop_types
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_crop_stages_updated_at BEFORE UPDATE ON crop_stages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_irrigation_schedules_updated_at BEFORE UPDATE ON irrigation_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_crop_calendar_updated_at BEFORE UPDATE ON crop_calendar
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();