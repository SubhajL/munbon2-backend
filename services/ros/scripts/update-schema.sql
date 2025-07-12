-- Set schema search path
SET search_path TO ros, public;

-- Drop existing tables that we won't use
DROP TABLE IF EXISTS ros.eto_calculations CASCADE;
DROP TABLE IF EXISTS ros.water_demand_calculations CASCADE;
DROP TABLE IF EXISTS ros.schedule_allocations CASCADE;
DROP TABLE IF EXISTS ros.irrigation_schedules CASCADE;

-- Create new tables for Excel-based data

-- Monthly ETo data from Excel worksheet
CREATE TABLE ros.eto_monthly (
    id SERIAL PRIMARY KEY,
    aos_station VARCHAR(100) NOT NULL,      -- AOS station name (e.g., 'นครราชสีมา')
    province VARCHAR(100) NOT NULL,         -- Province name (e.g., 'นครราชสีมา')
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    eto_value DECIMAL(10,2) NOT NULL,       -- Monthly ETo in mm
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(aos_station, province, month)
);

-- Weekly Kc data from Excel worksheet
CREATE TABLE ros.kc_weekly (
    id SERIAL PRIMARY KEY,
    crop_type VARCHAR(50) NOT NULL,         -- 'rice', 'corn', 'sugarcane'
    crop_week INTEGER NOT NULL,             -- Week number in crop growth cycle
    kc_value DECIMAL(4,3) NOT NULL,         -- Kc coefficient
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(crop_type, crop_week)
);

-- Water demand calculations
CREATE TABLE ros.water_demand_calculations (
    id SERIAL PRIMARY KEY,
    area_id VARCHAR(50) NOT NULL,
    area_type VARCHAR(20) NOT NULL,         -- 'project', 'zone', 'section', 'FTO'
    area_rai DECIMAL(10,2) NOT NULL,
    crop_type VARCHAR(50) NOT NULL,
    crop_week INTEGER NOT NULL,
    calendar_week INTEGER NOT NULL,
    calendar_year INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    
    -- Input values
    monthly_eto DECIMAL(10,2),              -- Monthly ETo from table
    weekly_eto DECIMAL(10,2),               -- Weekly ETo (monthly/4 or adjusted)
    kc_value DECIMAL(4,3),                  -- Kc from table
    percolation DECIMAL(10,2) DEFAULT 14,   -- Fixed at 14 mm/week
    
    -- Calculated values
    crop_water_demand_mm DECIMAL(10,2),     -- EToxKc + percolation
    crop_water_demand_m3 DECIMAL(15,2),     -- mm x area x 1.6
    
    -- Optional values
    effective_rainfall DECIMAL(10,2),       -- mm/week
    water_level DECIMAL(10,2),              -- meters
    net_water_demand_mm DECIMAL(10,2),      -- After rainfall
    net_water_demand_m3 DECIMAL(15,2),      -- After rainfall
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Crop calendar for tracking planting dates
CREATE TABLE ros.crop_calendar (
    id SERIAL PRIMARY KEY,
    area_id VARCHAR(50) NOT NULL,
    area_type VARCHAR(20) NOT NULL,
    crop_type VARCHAR(50) NOT NULL,
    planting_date DATE NOT NULL,
    expected_harvest_date DATE,
    season VARCHAR(20),                     -- 'wet', 'dry'
    year INTEGER NOT NULL,
    total_crop_weeks INTEGER,               -- Total weeks for this crop
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Area information
CREATE TABLE ros.area_info (
    id SERIAL PRIMARY KEY,
    area_id VARCHAR(50) UNIQUE NOT NULL,
    area_type VARCHAR(20) NOT NULL,
    area_name VARCHAR(200),
    total_area_rai DECIMAL(10,2),
    parent_area_id VARCHAR(50),             -- For hierarchical structure
    aos_station VARCHAR(100) DEFAULT 'นครราชสีมา',
    province VARCHAR(100) DEFAULT 'นครราชสีมา',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Rainfall data table
CREATE TABLE ros.rainfall_data (
    id SERIAL PRIMARY KEY,
    area_id VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    rainfall_mm DECIMAL(10,2) NOT NULL,
    effective_rainfall_mm DECIMAL(10,2),
    source VARCHAR(20) NOT NULL, -- 'manual', 'weather_api', 'sensor'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(area_id, date)
);

-- Water level monitoring table
CREATE TABLE ros.water_level_data (
    id SERIAL PRIMARY KEY,
    area_id VARCHAR(50) NOT NULL,
    measurement_date DATE NOT NULL,
    measurement_time TIME,
    water_level_m DECIMAL(10,3) NOT NULL,
    reference_level VARCHAR(50), -- 'MSL', 'local_datum', etc.
    source VARCHAR(20) NOT NULL, -- 'manual', 'sensor', 'scada'
    sensor_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_water_demand_area ON ros.water_demand_calculations(area_id, area_type);
CREATE INDEX idx_water_demand_date ON ros.water_demand_calculations(calculation_date);
CREATE INDEX idx_water_demand_crop ON ros.water_demand_calculations(crop_type, crop_week);
CREATE INDEX idx_crop_calendar_area ON ros.crop_calendar(area_id, area_type);
CREATE INDEX idx_area_info_type ON ros.area_info(area_type);
CREATE INDEX idx_rainfall_area_date ON ros.rainfall_data(area_id, date);
CREATE INDEX idx_water_level_area_date ON ros.water_level_data(area_id, measurement_date);

-- Insert sample ETo data for Nakhon Ratchasima
INSERT INTO ros.eto_monthly (aos_station, province, month, eto_value) VALUES
('นครราชสีมา', 'นครราชสีมา', 1, 108.5),   -- January
('นครราชสีมา', 'นครราชสีมา', 2, 122.4),   -- February
('นครราชสีมา', 'นครราชสีมา', 3, 151.9),   -- March
('นครราชสีมา', 'นครราชสีมา', 4, 156.0),   -- April
('นครราชสีมา', 'นครราชสีมา', 5, 148.8),   -- May
('นครราชสีมา', 'นครราชสีมา', 6, 132.0),   -- June
('นครราชสีมา', 'นครราชสีมา', 7, 130.2),   -- July
('นครราชสีมา', 'นครราชสีมา', 8, 127.1),   -- August
('นครราชสีมา', 'นครราชสีมา', 9, 114.0),   -- September
('นครราชสีมา', 'นครราชสีมา', 10, 108.5),  -- October
('นครราชสีมา', 'นครราชสีมา', 11, 102.0),  -- November
('นครราชสีมา', 'นครราชสีมา', 12, 99.2);   -- December

-- Insert sample Kc data for rice (16 weeks)
INSERT INTO ros.kc_weekly (crop_type, crop_week, kc_value) VALUES
('rice', 1, 1.05), ('rice', 2, 1.05), ('rice', 3, 1.05), ('rice', 4, 1.05),
('rice', 5, 1.10), ('rice', 6, 1.15), ('rice', 7, 1.20), ('rice', 8, 1.20),
('rice', 9, 1.20), ('rice', 10, 1.20), ('rice', 11, 1.20), ('rice', 12, 1.15),
('rice', 13, 1.10), ('rice', 14, 1.00), ('rice', 15, 0.95), ('rice', 16, 0.90);

-- Insert sample Kc data for corn (16 weeks)
INSERT INTO ros.kc_weekly (crop_type, crop_week, kc_value) VALUES
('corn', 1, 0.30), ('corn', 2, 0.30), ('corn', 3, 0.40), ('corn', 4, 0.50),
('corn', 5, 0.60), ('corn', 6, 0.75), ('corn', 7, 0.90), ('corn', 8, 1.05),
('corn', 9, 1.20), ('corn', 10, 1.20), ('corn', 11, 1.20), ('corn', 12, 1.10),
('corn', 13, 1.00), ('corn', 14, 0.85), ('corn', 15, 0.70), ('corn', 16, 0.60);

-- Insert sample Kc data for sugarcane (52 weeks)
INSERT INTO ros.kc_weekly (crop_type, crop_week, kc_value) 
SELECT 'sugarcane', generate_series, 
    CASE 
        WHEN generate_series <= 4 THEN 0.40
        WHEN generate_series <= 8 THEN 0.50
        WHEN generate_series <= 12 THEN 0.70
        WHEN generate_series <= 16 THEN 0.90
        WHEN generate_series <= 20 THEN 1.00
        WHEN generate_series <= 36 THEN 1.25
        WHEN generate_series <= 44 THEN 1.10
        WHEN generate_series <= 48 THEN 0.90
        ELSE 0.75
    END
FROM generate_series(1, 52);

-- Update triggers for new tables
CREATE TRIGGER update_eto_monthly_updated_at BEFORE UPDATE ON ros.eto_monthly
    FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

CREATE TRIGGER update_kc_weekly_updated_at BEFORE UPDATE ON ros.kc_weekly
    FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

CREATE TRIGGER update_area_info_updated_at BEFORE UPDATE ON ros.area_info
    FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

CREATE TRIGGER update_crop_calendar_updated_at BEFORE UPDATE ON ros.crop_calendar
    FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

CREATE TRIGGER update_rainfall_data_updated_at BEFORE UPDATE ON ros.rainfall_data
    FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

CREATE TRIGGER update_water_level_data_updated_at BEFORE UPDATE ON ros.water_level_data
    FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();