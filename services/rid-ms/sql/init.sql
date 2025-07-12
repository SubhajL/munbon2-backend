-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Shape file uploads tracking
CREATE TABLE shape_file_uploads (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  upload_id VARCHAR(100) UNIQUE NOT NULL, -- From S3/SQS
  upload_date TIMESTAMP NOT NULL DEFAULT NOW(),
  file_name VARCHAR(255) NOT NULL,
  s3_bucket VARCHAR(255) NOT NULL,
  s3_key VARCHAR(500) NOT NULL,
  status VARCHAR(50) DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
  processing_started_at TIMESTAMP,
  processing_completed_at TIMESTAMP,
  parcel_count INTEGER,
  processing_time_ms INTEGER,
  error_message TEXT,
  file_size_bytes BIGINT,
  processing_interval VARCHAR(20) CHECK (processing_interval IN ('daily', 'weekly', 'bi-weekly')),
  water_demand_method VARCHAR(20) CHECK (water_demand_method IN ('RID-MS', 'ROS', 'AWD')),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Parcels with spatial data and versioning
CREATE TABLE parcels (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  parcel_id VARCHAR(100) NOT NULL, -- Original ID from shape file
  shape_file_id UUID REFERENCES shape_file_uploads(id) ON DELETE CASCADE,
  valid_from TIMESTAMP NOT NULL DEFAULT NOW(),
  valid_to TIMESTAMP, -- NULL means current version
  
  -- Spatial data
  geometry GEOMETRY(Polygon, 4326) NOT NULL,
  area_rai NUMERIC(10,2), -- Thai unit (1 rai = 1600 sqm)
  area_sqm NUMERIC(12,2),
  centroid GEOMETRY(Point, 4326),
  
  -- Location hierarchy
  zone VARCHAR(50) NOT NULL,
  sub_zone VARCHAR(50),
  mooban VARCHAR(100), -- Village
  tambon VARCHAR(100), -- Sub-district
  amphoe VARCHAR(100), -- District
  
  -- Ownership and land use
  owner_name VARCHAR(255),
  owner_id VARCHAR(100),
  land_use_type VARCHAR(100),
  crop_type VARCHAR(100),
  planting_date DATE,
  harvest_date DATE,
  
  -- Water demand settings
  water_demand_method VARCHAR(20) DEFAULT 'RID-MS',
  irrigation_type VARCHAR(50), -- sprinkler, drip, flood
  
  -- Original attributes from shape file
  attributes JSONB DEFAULT '{}',
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  
  -- Ensure only one current version per parcel
  CONSTRAINT unique_current_parcel UNIQUE (parcel_id, valid_to)
);

-- Water demand calculations
CREATE TABLE water_demand_calculations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  parcel_id UUID REFERENCES parcels(id) ON DELETE CASCADE,
  calculated_date DATE NOT NULL,
  calculation_time TIMESTAMP NOT NULL DEFAULT NOW(),
  
  -- Calculation inputs
  method VARCHAR(20) NOT NULL CHECK (method IN ('RID-MS', 'ROS', 'AWD')),
  crop_type VARCHAR(100),
  growth_stage VARCHAR(50), -- initial, development, mid, late
  crop_coefficient NUMERIC(4,2),
  
  -- Weather data
  reference_et NUMERIC(6,2), -- Reference evapotranspiration (mm/day)
  rainfall NUMERIC(6,2), -- mm/day
  effective_rainfall NUMERIC(6,2), -- mm/day
  
  -- Efficiency factors
  irrigation_efficiency NUMERIC(3,2), -- 0.65 for RID-MS, 0.75 for ROS, 0.85 for AWD
  distribution_efficiency NUMERIC(3,2) DEFAULT 0.90,
  field_application_efficiency NUMERIC(3,2) DEFAULT 0.85,
  
  -- Calculated demand
  crop_water_requirement NUMERIC(8,2), -- mm/day
  net_irrigation_requirement NUMERIC(8,2), -- mm/day (after rainfall)
  gross_irrigation_requirement NUMERIC(8,2), -- mm/day (after efficiency)
  daily_demand_cubic_meters NUMERIC(12,2),
  daily_demand_liters NUMERIC(15,2),
  
  -- Aggregated values
  weekly_demand_cubic_meters NUMERIC(12,2),
  monthly_demand_cubic_meters NUMERIC(12,2),
  
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW()
);

-- Zone summary for quick access
CREATE TABLE zone_summaries (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  zone VARCHAR(50) NOT NULL,
  summary_date DATE NOT NULL,
  total_parcels INTEGER,
  total_area_rai NUMERIC(12,2),
  total_area_sqm NUMERIC(15,2),
  
  -- Crop distribution
  crop_distribution JSONB, -- {"Rice": 1234, "Corn": 567, ...}
  
  -- Water demand by method
  water_demand_by_method JSONB, -- {"RID-MS": 12345, "ROS": 6789, ...}
  total_daily_demand_cubic_meters NUMERIC(15,2),
  
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  
  CONSTRAINT unique_zone_date UNIQUE (zone, summary_date)
);

-- Create indexes for performance
CREATE INDEX idx_uploads_status ON shape_file_uploads(status);
CREATE INDEX idx_uploads_upload_date ON shape_file_uploads(upload_date DESC);
CREATE INDEX idx_uploads_upload_id ON shape_file_uploads(upload_id);

CREATE INDEX idx_parcels_parcel_id ON parcels(parcel_id);
CREATE INDEX idx_parcels_zone ON parcels(zone);
CREATE INDEX idx_parcels_zone_subzone ON parcels(zone, sub_zone);
CREATE INDEX idx_parcels_valid ON parcels(valid_from, valid_to);
CREATE INDEX idx_parcels_current ON parcels(parcel_id) WHERE valid_to IS NULL;
CREATE INDEX idx_parcels_shape_file ON parcels(shape_file_id);
CREATE INDEX idx_parcels_crop_type ON parcels(crop_type);

-- Spatial indexes
CREATE INDEX idx_parcels_geometry ON parcels USING GIST (geometry);
CREATE INDEX idx_parcels_centroid ON parcels USING GIST (centroid);

CREATE INDEX idx_water_demand_parcel ON water_demand_calculations(parcel_id);
CREATE INDEX idx_water_demand_date ON water_demand_calculations(calculated_date DESC);
CREATE INDEX idx_water_demand_parcel_date ON water_demand_calculations(parcel_id, calculated_date DESC);

CREATE INDEX idx_zone_summaries_zone_date ON zone_summaries(zone, summary_date DESC);

-- Helper functions
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at
CREATE TRIGGER update_shape_file_uploads_updated_at BEFORE UPDATE ON shape_file_uploads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_parcels_updated_at BEFORE UPDATE ON parcels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_zone_summaries_updated_at BEFORE UPDATE ON zone_summaries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate area in rai
CREATE OR REPLACE FUNCTION sqm_to_rai(area_sqm NUMERIC) 
RETURNS NUMERIC AS $$
BEGIN
    RETURN area_sqm / 1600.0;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to get current parcels
CREATE OR REPLACE FUNCTION get_current_parcels(p_zone VARCHAR DEFAULT NULL)
RETURNS TABLE (
    parcel_id VARCHAR,
    zone VARCHAR,
    area_rai NUMERIC,
    crop_type VARCHAR,
    owner_name VARCHAR,
    geometry GEOMETRY
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.parcel_id,
        p.zone,
        p.area_rai,
        p.crop_type,
        p.owner_name,
        p.geometry
    FROM parcels p
    WHERE p.valid_to IS NULL
    AND (p_zone IS NULL OR p.zone = p_zone);
END;
$$ LANGUAGE plpgsql;

-- Sample data for testing (optional)
-- INSERT INTO shape_file_uploads (upload_id, file_name, s3_bucket, s3_key, status)
-- VALUES ('test-001', 'test_parcels.zip', 'munbon-shape-files-dev', 'shape-files/2024-03-15/test-001/test_parcels.zip', 'uploaded');