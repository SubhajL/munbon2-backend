-- Migration: Add tables for daily demand calculation and AquaCrop integration
-- This migration adds support for plot-based daily calculations

-- Create plots table (subdivision of sections)
CREATE TABLE IF NOT EXISTS ros_gis.plots (
    plot_id VARCHAR(50) PRIMARY KEY,
    section_id VARCHAR(50) NOT NULL REFERENCES ros_gis.sections(section_id),
    zone INTEGER NOT NULL,
    plot_number INTEGER NOT NULL,
    area_rai DECIMAL(10,2) NOT NULL,
    crop_type VARCHAR(50),
    planting_date DATE,
    expected_harvest_date DATE,
    farmer_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',
    geometry GEOMETRY(Polygon, 4326),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create daily demands table
CREATE TABLE IF NOT EXISTS ros_gis.daily_demands (
    demand_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    plot_id VARCHAR(50) NOT NULL,
    section_id VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    ros_demand_m3 DECIMAL(10,2),
    aquacrop_demand_m3 DECIMAL(10,2),
    combined_demand_m3 DECIMAL(10,2) NOT NULL,
    crop_type VARCHAR(50),
    growth_stage VARCHAR(50),
    stress_level VARCHAR(20),
    area_rai DECIMAL(10,2),
    source VARCHAR(50), -- 'ros', 'aquacrop', 'combined'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plot_id, date)
);

-- Create AquaCrop results table (populated by data ingestion service)
CREATE TABLE IF NOT EXISTS ros_gis.aquacrop_results (
    result_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    plot_id VARCHAR(50) NOT NULL,
    calculation_date DATE NOT NULL,
    net_irrigation_mm DECIMAL(10,2),
    gross_irrigation_mm DECIMAL(10,2),
    soil_moisture_percent DECIMAL(5,2),
    crop_stage VARCHAR(50),
    water_stress_level VARCHAR(20),
    biomass_kg_ha DECIMAL(10,2),
    yield_kg_ha DECIMAL(10,2),
    geopackage_source VARCHAR(255),
    processing_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plot_id, calculation_date, processing_date)
);

-- Create accumulated demands table (for control intervals)
CREATE TABLE IF NOT EXISTS ros_gis.accumulated_demands (
    accumulation_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    section_id VARCHAR(50) NOT NULL REFERENCES ros_gis.sections(section_id),
    control_interval VARCHAR(20) NOT NULL, -- 'weekly', 'biweekly', 'monthly'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_demand_m3 DECIMAL(12,2) NOT NULL,
    plot_count INTEGER NOT NULL,
    avg_daily_demand_m3 DECIMAL(10,2),
    peak_daily_demand_m3 DECIMAL(10,2),
    delivery_gate VARCHAR(50),
    irrigation_channel VARCHAR(50),
    schedule_id VARCHAR(50), -- Reference to scheduler service
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(section_id, control_interval, start_date)
);

-- Create irrigation channels table
CREATE TABLE IF NOT EXISTS ros_gis.irrigation_channels (
    channel_id VARCHAR(50) PRIMARY KEY,
    channel_name VARCHAR(100),
    channel_type VARCHAR(50), -- 'primary', 'secondary', 'tertiary'
    max_capacity_m3s DECIMAL(10,2),
    length_km DECIMAL(10,2),
    sections_served TEXT[], -- Array of section_ids
    upstream_gate VARCHAR(50),
    downstream_gates TEXT[], -- Array of gate_ids
    geometry GEOMETRY(LineString, 4326),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add irrigation channel reference to gate mappings
ALTER TABLE ros_gis.gate_mappings 
ADD COLUMN IF NOT EXISTS irrigation_channel VARCHAR(50);

-- Create indexes for performance
CREATE INDEX idx_plots_section ON ros_gis.plots(section_id);
CREATE INDEX idx_plots_zone ON ros_gis.plots(zone);
CREATE INDEX idx_plots_status ON ros_gis.plots(status);
CREATE INDEX idx_plots_geometry ON ros_gis.plots USING GIST(geometry);

CREATE INDEX idx_daily_demands_date ON ros_gis.daily_demands(date);
CREATE INDEX idx_daily_demands_section_date ON ros_gis.daily_demands(section_id, date);
CREATE INDEX idx_daily_demands_plot_date ON ros_gis.daily_demands(plot_id, date);

CREATE INDEX idx_aquacrop_plot_date ON ros_gis.aquacrop_results(plot_id, calculation_date);
CREATE INDEX idx_aquacrop_processing_date ON ros_gis.aquacrop_results(processing_date DESC);

CREATE INDEX idx_accumulated_section_interval ON ros_gis.accumulated_demands(section_id, control_interval, start_date);
CREATE INDEX idx_accumulated_schedule ON ros_gis.accumulated_demands(schedule_id);

CREATE INDEX idx_channels_geometry ON ros_gis.irrigation_channels USING GIST(geometry);

-- Create views for common queries

-- View: Current demands by section with channel aggregation
CREATE OR REPLACE VIEW ros_gis.v_section_channel_demands AS
SELECT 
    s.section_id,
    s.zone,
    s.delivery_gate,
    gm.irrigation_channel,
    COUNT(DISTINCT p.plot_id) as plot_count,
    SUM(p.area_rai) as total_area_rai,
    AVG(dd.combined_demand_m3) as avg_daily_demand_m3,
    SUM(dd.combined_demand_m3) as total_daily_demand_m3
FROM ros_gis.sections s
LEFT JOIN ros_gis.plots p ON s.section_id = p.section_id AND p.status = 'active'
LEFT JOIN ros_gis.gate_mappings gm ON s.section_id = gm.section_id
LEFT JOIN ros_gis.daily_demands dd ON p.plot_id = dd.plot_id 
    AND dd.date = CURRENT_DATE
GROUP BY s.section_id, s.zone, s.delivery_gate, gm.irrigation_channel;

-- View: Channel utilization summary
CREATE OR REPLACE VIEW ros_gis.v_channel_utilization AS
SELECT 
    ic.channel_id,
    ic.channel_name,
    ic.channel_type,
    ic.max_capacity_m3s,
    COUNT(DISTINCT scd.section_id) as sections_count,
    SUM(scd.total_daily_demand_m3) / (8 * 3600) as required_flow_m3s,
    (SUM(scd.total_daily_demand_m3) / (8 * 3600)) / NULLIF(ic.max_capacity_m3s, 0) * 100 as utilization_percent
FROM ros_gis.irrigation_channels ic
LEFT JOIN ros_gis.v_section_channel_demands scd ON ic.channel_id = scd.irrigation_channel
GROUP BY ic.channel_id, ic.channel_name, ic.channel_type, ic.max_capacity_m3s;

-- Add trigger to update timestamps
CREATE OR REPLACE FUNCTION ros_gis.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_plots_updated_at BEFORE UPDATE ON ros_gis.plots
    FOR EACH ROW EXECUTE FUNCTION ros_gis.update_updated_at_column();

CREATE TRIGGER update_daily_demands_updated_at BEFORE UPDATE ON ros_gis.daily_demands
    FOR EACH ROW EXECUTE FUNCTION ros_gis.update_updated_at_column();