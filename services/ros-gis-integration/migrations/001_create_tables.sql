-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS ros_gis;

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Sections table with PostGIS geometry
CREATE TABLE IF NOT EXISTS ros_gis.sections (
    section_id VARCHAR(50) PRIMARY KEY,
    zone INTEGER NOT NULL,
    area_hectares DECIMAL(10,2),
    area_rai DECIMAL(10,2) GENERATED ALWAYS AS (area_hectares * 6.25) STORED,
    crop_type VARCHAR(50),
    soil_type VARCHAR(50),
    elevation_m DECIMAL(6,2),
    delivery_gate VARCHAR(50),
    geometry GEOMETRY(Polygon, 4326),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index
CREATE INDEX idx_sections_geometry ON ros_gis.sections USING GIST (geometry);
CREATE INDEX idx_sections_zone ON ros_gis.sections(zone);
CREATE INDEX idx_sections_delivery_gate ON ros_gis.sections(delivery_gate);

-- Demands table
CREATE TABLE IF NOT EXISTS ros_gis.demands (
    demand_id SERIAL PRIMARY KEY,
    section_id VARCHAR(50) REFERENCES ros_gis.sections(section_id),
    week VARCHAR(8) NOT NULL, -- Format: YYYY-WXX
    volume_m3 DECIMAL(12,2),
    priority DECIMAL(3,1) CHECK (priority >= 0 AND priority <= 10),
    priority_class VARCHAR(20) CHECK (priority_class IN ('critical', 'high', 'medium', 'low')),
    crop_type VARCHAR(50),
    growth_stage VARCHAR(50),
    moisture_deficit_percent DECIMAL(5,2),
    stress_level VARCHAR(20) CHECK (stress_level IN ('none', 'mild', 'moderate', 'severe', 'critical')),
    delivery_window_start TIMESTAMP,
    delivery_window_end TIMESTAMP,
    weather_adjustment_factor DECIMAL(4,3) DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_demands_section_week ON ros_gis.demands(section_id, week);
CREATE INDEX idx_demands_week ON ros_gis.demands(week);
CREATE INDEX idx_demands_priority ON ros_gis.demands(priority DESC);

-- Performance tracking
CREATE TABLE IF NOT EXISTS ros_gis.section_performance (
    performance_id SERIAL PRIMARY KEY,
    section_id VARCHAR(50) REFERENCES ros_gis.sections(section_id),
    week VARCHAR(8) NOT NULL,
    planned_m3 DECIMAL(12,2),
    delivered_m3 DECIMAL(12,2),
    efficiency DECIMAL(3,2) CHECK (efficiency >= 0 AND efficiency <= 1),
    deficit_m3 DECIMAL(12,2),
    delivery_count INTEGER DEFAULT 0,
    average_flow_m3s DECIMAL(8,3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_performance_section_week ON ros_gis.section_performance(section_id, week);
CREATE INDEX idx_performance_week ON ros_gis.section_performance(week);

-- Gate mappings table
CREATE TABLE IF NOT EXISTS ros_gis.gate_mappings (
    mapping_id SERIAL PRIMARY KEY,
    gate_id VARCHAR(50) NOT NULL,
    section_id VARCHAR(50) REFERENCES ros_gis.sections(section_id),
    distance_km DECIMAL(6,2),
    travel_time_hours DECIMAL(5,2),
    is_primary BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gate_id, section_id)
);

CREATE INDEX idx_gate_mappings_gate ON ros_gis.gate_mappings(gate_id);
CREATE INDEX idx_gate_mappings_section ON ros_gis.gate_mappings(section_id);

-- Aggregated demands by gate
CREATE TABLE IF NOT EXISTS ros_gis.gate_demands (
    gate_demand_id SERIAL PRIMARY KEY,
    gate_id VARCHAR(50) NOT NULL,
    week VARCHAR(8) NOT NULL,
    total_volume_m3 DECIMAL(12,2),
    section_count INTEGER,
    priority_weighted DECIMAL(3,1),
    schedule_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gate_id, week)
);

CREATE INDEX idx_gate_demands_week ON ros_gis.gate_demands(week);
CREATE INDEX idx_gate_demands_gate ON ros_gis.gate_demands(gate_id);

-- Weather adjustments table
CREATE TABLE IF NOT EXISTS ros_gis.weather_adjustments (
    adjustment_id SERIAL PRIMARY KEY,
    section_id VARCHAR(50) REFERENCES ros_gis.sections(section_id),
    week VARCHAR(8) NOT NULL,
    rainfall_mm DECIMAL(6,2),
    et_mm DECIMAL(6,2),
    adjustment_factor DECIMAL(4,3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_weather_section_week ON ros_gis.weather_adjustments(section_id, week);

-- Create update trigger for updated_at
CREATE OR REPLACE FUNCTION ros_gis.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_sections_updated_at BEFORE UPDATE
    ON ros_gis.sections FOR EACH ROW EXECUTE FUNCTION 
    ros_gis.update_updated_at_column();