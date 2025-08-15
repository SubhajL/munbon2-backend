-- Add land preparation water requirements table
SET search_path TO ros, public;

-- Create land preparation water table
CREATE TABLE IF NOT EXISTS ros.land_preparation_water (
    id SERIAL PRIMARY KEY,
    crop_type VARCHAR(50) NOT NULL UNIQUE,
    preparation_water_mm DECIMAL(10,2) NOT NULL,
    preparation_weeks INTEGER DEFAULT 1,
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert land preparation data from Excel
INSERT INTO ros.land_preparation_water (crop_type, preparation_water_mm, preparation_weeks, description) VALUES
('rice', 100.0, 1, 'Water for land soaking, puddling and initial flooding'),
('corn', 50.0, 1, 'Pre-irrigation for soil moisture'),
('sugarcane', 50.0, 1, 'Pre-irrigation for planting preparation')
ON CONFLICT (crop_type) DO UPDATE
SET preparation_water_mm = EXCLUDED.preparation_water_mm,
    preparation_weeks = EXCLUDED.preparation_weeks,
    description = EXCLUDED.description,
    updated_at = NOW();

-- Add trigger for updated_at
CREATE TRIGGER update_land_preparation_water_updated_at 
BEFORE UPDATE ON ros.land_preparation_water
FOR EACH ROW EXECUTE FUNCTION ros.update_updated_at_column();

-- Add land preparation to water demand calculations table
ALTER TABLE ros.water_demand_calculations
ADD COLUMN IF NOT EXISTS is_land_preparation BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS land_preparation_mm DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS land_preparation_m3 DECIMAL(15,2);

-- Create index for land preparation queries
CREATE INDEX IF NOT EXISTS idx_water_demand_land_prep 
ON ros.water_demand_calculations(is_land_preparation)
WHERE is_land_preparation = TRUE;

COMMENT ON TABLE ros.land_preparation_water IS 'Land preparation water requirements by crop type from ROS Excel';
COMMENT ON COLUMN ros.land_preparation_water.preparation_water_mm IS 'Water required for land preparation in mm (from Excel น้ำเตรียมแปลง)';
COMMENT ON COLUMN ros.land_preparation_water.preparation_weeks IS 'Duration of land preparation phase in weeks';