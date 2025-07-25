-- Migration: Add ROS water demands table to GIS schema
-- This consolidates ROS calculations with GIS parcel data

-- Create the ROS water demands table
CREATE TABLE IF NOT EXISTS gis.ros_water_demands (
    id SERIAL PRIMARY KEY,
    parcel_id UUID REFERENCES gis.agricultural_plots(id) ON DELETE CASCADE,
    section_id VARCHAR(50),
    calculation_date TIMESTAMP NOT NULL,
    calendar_week INTEGER NOT NULL,
    calendar_year INTEGER NOT NULL,
    
    -- Crop information
    crop_type VARCHAR(50),
    crop_week INTEGER,
    growth_stage VARCHAR(50),
    planting_date DATE,
    harvest_date DATE,
    
    -- Water demand calculation inputs
    area_rai NUMERIC NOT NULL,
    et0_mm NUMERIC,
    kc_factor NUMERIC,
    percolation_mm NUMERIC DEFAULT 14,
    
    -- Results
    gross_demand_mm NUMERIC,
    gross_demand_m3 NUMERIC,
    effective_rainfall_mm NUMERIC,
    net_demand_mm NUMERIC,
    net_demand_m3 NUMERIC,
    
    -- Additional metrics
    moisture_deficit_percent NUMERIC,
    stress_level VARCHAR(20) CHECK (stress_level IN ('none', 'mild', 'moderate', 'severe', 'critical')),
    
    -- Metadata
    source VARCHAR(50) DEFAULT 'ros_calculation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unique constraint for upsert operations
CREATE UNIQUE INDEX idx_ros_demands_unique ON gis.ros_water_demands(parcel_id, calendar_week, calendar_year) 
WHERE parcel_id IS NOT NULL;

-- Create indexes for performance
CREATE INDEX idx_ros_demands_section_week ON gis.ros_water_demands(section_id, calendar_week, calendar_year);
CREATE INDEX idx_ros_demands_section_date ON gis.ros_water_demands(section_id, calculation_date);
CREATE INDEX idx_ros_demands_crop_type ON gis.ros_water_demands(crop_type, growth_stage);
CREATE INDEX idx_ros_demands_calculation_date ON gis.ros_water_demands(calculation_date DESC);

-- Create a view for latest demands per parcel
CREATE OR REPLACE VIEW gis.latest_ros_demands AS
SELECT DISTINCT ON (parcel_id)
    rwd.*,
    p.plot_code,
    p.properties->>'amphoe' as amphoe,
    p.properties->>'tambon' as tambon,
    p.boundary as geometry
FROM gis.ros_water_demands rwd
JOIN gis.agricultural_plots p ON rwd.parcel_id = p.id
ORDER BY parcel_id, calculation_date DESC;

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION gis.update_ros_demands_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updated_at
CREATE TRIGGER update_ros_demands_updated_at
    BEFORE UPDATE ON gis.ros_water_demands
    FOR EACH ROW
    EXECUTE FUNCTION gis.update_ros_demands_updated_at();

-- Add comments for documentation
COMMENT ON TABLE gis.ros_water_demands IS 'Time-series water demand calculations from ROS service';
COMMENT ON COLUMN gis.ros_water_demands.parcel_id IS 'Reference to GIS parcel';
COMMENT ON COLUMN gis.ros_water_demands.section_id IS 'Agricultural section identifier';
COMMENT ON COLUMN gis.ros_water_demands.gross_demand_m3 IS 'Total water demand before rainfall adjustment';
COMMENT ON COLUMN gis.ros_water_demands.net_demand_m3 IS 'Net water demand after rainfall adjustment';

-- Create a materialized view for weekly demand summaries
CREATE MATERIALIZED VIEW gis.weekly_demand_summary AS
SELECT 
    calendar_year,
    calendar_week,
    p.properties->>'amphoe' as amphoe,
    p.properties->>'tambon' as tambon,
    crop_type,
    COUNT(DISTINCT rwd.parcel_id) as parcel_count,
    SUM(rwd.area_rai) as total_area_rai,
    SUM(rwd.net_demand_m3) as total_net_demand_m3,
    AVG(rwd.net_demand_m3) as avg_net_demand_m3,
    AVG(rwd.moisture_deficit_percent) as avg_moisture_deficit
FROM gis.ros_water_demands rwd
JOIN gis.agricultural_plots p ON rwd.parcel_id = p.id
GROUP BY calendar_year, calendar_week, amphoe, tambon, crop_type;

-- Create index on materialized view
CREATE INDEX idx_weekly_summary_week ON gis.weekly_demand_summary(calendar_year, calendar_week);

-- Grant permissions (skip if role doesn't exist)
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gis_service') THEN
        GRANT SELECT, INSERT, UPDATE ON gis.ros_water_demands TO gis_service;
        GRANT SELECT ON gis.latest_ros_demands TO gis_service;
        GRANT SELECT ON gis.weekly_demand_summary TO gis_service;
    END IF;
END $$;