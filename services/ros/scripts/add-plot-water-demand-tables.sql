-- Add plot-level water demand tables
SET search_path TO ros, public;

-- Create plot information table
CREATE TABLE IF NOT EXISTS ros.plots (
    id SERIAL PRIMARY KEY,
    plot_id VARCHAR(50) UNIQUE NOT NULL,       -- Unique plot identifier
    plot_code VARCHAR(50),                     -- Plot code from shapefile
    area_rai DECIMAL(10,2) NOT NULL,          -- Area in rai
    geometry GEOMETRY(Polygon, 32648),        -- Spatial data (UTM Zone 48N)
    parent_section_id VARCHAR(50),            -- Link to section
    parent_zone_id VARCHAR(50),               -- Link to zone
    aos_station VARCHAR(100) DEFAULT 'นครราชสีมา',
    province VARCHAR(100) DEFAULT 'นครราชสีมา',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create plot crop schedule table
CREATE TABLE IF NOT EXISTS ros.plot_crop_schedule (
    id SERIAL PRIMARY KEY,
    plot_id VARCHAR(50) NOT NULL REFERENCES ros.plots(plot_id),
    crop_type VARCHAR(50) NOT NULL,
    planting_date DATE NOT NULL,
    expected_harvest_date DATE,
    season VARCHAR(20) NOT NULL,              -- 'wet' or 'dry'
    year INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'planned',     -- 'planned', 'active', 'harvested'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(plot_id, year, season)
);

-- Create plot water demand calculations table (weekly)
CREATE TABLE IF NOT EXISTS ros.plot_water_demand_weekly (
    id SERIAL PRIMARY KEY,
    plot_id VARCHAR(50) NOT NULL REFERENCES ros.plots(plot_id),
    crop_type VARCHAR(50) NOT NULL,
    crop_week INTEGER NOT NULL,
    calendar_week INTEGER NOT NULL,
    calendar_year INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    
    -- Input values
    area_rai DECIMAL(10,2) NOT NULL,
    monthly_eto DECIMAL(10,2),
    weekly_eto DECIMAL(10,2),
    kc_value DECIMAL(4,3),
    percolation DECIMAL(10,2) DEFAULT 14,
    
    -- Calculated values
    crop_water_demand_mm DECIMAL(10,2),
    crop_water_demand_m3 DECIMAL(15,2),
    crop_water_demand_m3_per_rai DECIMAL(15,2),
    
    -- Rainfall and net demand
    effective_rainfall_mm DECIMAL(10,2),
    net_water_demand_mm DECIMAL(10,2),
    net_water_demand_m3 DECIMAL(15,2),
    net_water_demand_m3_per_rai DECIMAL(15,2),
    
    -- Land preparation flag
    is_land_preparation BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(plot_id, crop_type, crop_week, calendar_year, calendar_week)
);

-- Create plot water demand seasonal summary table
CREATE TABLE IF NOT EXISTS ros.plot_water_demand_seasonal (
    id SERIAL PRIMARY KEY,
    plot_id VARCHAR(50) NOT NULL REFERENCES ros.plots(plot_id),
    crop_type VARCHAR(50) NOT NULL,
    planting_date DATE NOT NULL,
    harvest_date DATE,
    season VARCHAR(20) NOT NULL,
    year INTEGER NOT NULL,
    
    -- Area
    area_rai DECIMAL(10,2) NOT NULL,
    
    -- Total seasonal values
    total_crop_weeks INTEGER NOT NULL,
    total_water_demand_mm DECIMAL(10,2),
    total_water_demand_m3 DECIMAL(15,2),
    
    -- Land preparation
    land_preparation_mm DECIMAL(10,2),
    land_preparation_m3 DECIMAL(15,2),
    
    -- Rainfall totals
    total_effective_rainfall_mm DECIMAL(10,2),
    total_net_water_demand_mm DECIMAL(10,2),
    total_net_water_demand_m3 DECIMAL(15,2),
    
    -- Calculation metadata
    calculation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    includes_land_preparation BOOLEAN DEFAULT TRUE,
    includes_rainfall BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(plot_id, crop_type, planting_date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_plots_geometry ON ros.plots USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_plots_parent_section ON ros.plots(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_plots_parent_zone ON ros.plots(parent_zone_id);

CREATE INDEX IF NOT EXISTS idx_plot_crop_schedule_plot ON ros.plot_crop_schedule(plot_id);
CREATE INDEX IF NOT EXISTS idx_plot_crop_schedule_status ON ros.plot_crop_schedule(status);
CREATE INDEX IF NOT EXISTS idx_plot_crop_schedule_dates ON ros.plot_crop_schedule(planting_date, expected_harvest_date);

CREATE INDEX IF NOT EXISTS idx_plot_water_demand_weekly_plot ON ros.plot_water_demand_weekly(plot_id);
CREATE INDEX IF NOT EXISTS idx_plot_water_demand_weekly_date ON ros.plot_water_demand_weekly(calendar_year, calendar_week);
CREATE INDEX IF NOT EXISTS idx_plot_water_demand_weekly_crop ON ros.plot_water_demand_weekly(crop_type, crop_week);

CREATE INDEX IF NOT EXISTS idx_plot_water_demand_seasonal_plot ON ros.plot_water_demand_seasonal(plot_id);
CREATE INDEX IF NOT EXISTS idx_plot_water_demand_seasonal_year ON ros.plot_water_demand_seasonal(year, season);

-- Add triggers for updated_at
CREATE TRIGGER update_plots_updated_at 
BEFORE UPDATE ON ros.plots
FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

CREATE TRIGGER update_plot_crop_schedule_updated_at 
BEFORE UPDATE ON ros.plot_crop_schedule
FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

CREATE TRIGGER update_plot_water_demand_seasonal_updated_at 
BEFORE UPDATE ON ros.plot_water_demand_seasonal
FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

-- Add comments
COMMENT ON TABLE ros.plots IS 'Individual agricultural plots from shapefile with spatial data';
COMMENT ON TABLE ros.plot_crop_schedule IS 'Crop planting schedule for each plot';
COMMENT ON TABLE ros.plot_water_demand_weekly IS 'Weekly water demand calculations for each plot';
COMMENT ON TABLE ros.plot_water_demand_seasonal IS 'Seasonal water demand summary for each plot';

COMMENT ON COLUMN ros.plots.geometry IS 'Spatial polygon data in UTM Zone 48N (EPSG:32648)';
COMMENT ON COLUMN ros.plot_water_demand_weekly.is_land_preparation IS 'TRUE for week 0 (land preparation)';
COMMENT ON COLUMN ros.plot_water_demand_weekly.crop_water_demand_m3_per_rai IS 'Crop water demand in cubic meters per rai (m³/rai)';
COMMENT ON COLUMN ros.plot_water_demand_weekly.net_water_demand_m3_per_rai IS 'Net water demand after rainfall in cubic meters per rai (m³/rai)';
COMMENT ON COLUMN ros.plot_water_demand_seasonal.includes_land_preparation IS 'Whether land preparation water is included in totals';