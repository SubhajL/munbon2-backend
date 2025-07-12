-- Create GIS upload tables for shape file processing

-- Create enum type for upload status
DO $$ BEGIN
    CREATE TYPE gis.upload_status AS ENUM ('pending', 'processing', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Shape file uploads tracking table
CREATE TABLE IF NOT EXISTS gis.shape_file_uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_id VARCHAR(255) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    status gis.upload_status DEFAULT 'pending',
    metadata JSONB,
    error TEXT,
    parcel_count INTEGER,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_shape_file_uploads_status ON gis.shape_file_uploads(status);
CREATE INDEX IF NOT EXISTS idx_shape_file_uploads_upload_id ON gis.shape_file_uploads(upload_id);

-- Create trigger to update updated_at
CREATE TRIGGER update_shape_file_uploads_modtime 
    BEFORE UPDATE ON gis.shape_file_uploads 
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Additional tables for GIS entities if they don't exist

-- Zones table
CREATE TABLE IF NOT EXISTS gis.zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    geometry GEOMETRY(POLYGON, 4326),
    boundary GEOMETRY(POLYGON, 4326),
    area NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Parcels table
CREATE TABLE IF NOT EXISTS gis.parcels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parcel_code VARCHAR(100) UNIQUE NOT NULL,
    owner_name VARCHAR(255),
    area NUMERIC,
    geometry GEOMETRY(POLYGON, 4326),
    centroid GEOMETRY(POINT, 4326),
    zone_id UUID REFERENCES gis.zones(id),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Canals table
CREATE TABLE IF NOT EXISTS gis.canals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    geometry GEOMETRY(LINESTRING, 4326),
    length NUMERIC,
    width NUMERIC,
    depth NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Gates table
CREATE TABLE IF NOT EXISTS gis.gates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    location GEOMETRY(POINT, 4326),
    canal_id UUID REFERENCES gis.canals(id),
    type VARCHAR(50),
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Pumps table
CREATE TABLE IF NOT EXISTS gis.pumps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    location GEOMETRY(POINT, 4326),
    capacity NUMERIC,
    type VARCHAR(50),
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Water sources table
CREATE TABLE IF NOT EXISTS gis.water_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50),
    geometry GEOMETRY(POLYGON, 4326),
    capacity NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Irrigation blocks table
CREATE TABLE IF NOT EXISTS gis.irrigation_blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    geometry GEOMETRY(POLYGON, 4326),
    area NUMERIC,
    zone_id UUID REFERENCES gis.zones(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Spatial indexes table (for performance optimization)
CREATE TABLE IF NOT EXISTS gis.spatial_indexes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    index_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Parcels simple table (for simplified data)
CREATE TABLE IF NOT EXISTS gis.parcels_simple (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parcel_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial indexes for all geometry columns
CREATE INDEX IF NOT EXISTS idx_zones_geometry ON gis.zones USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_zones_boundary ON gis.zones USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_parcels_geometry ON gis.parcels USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_parcels_centroid ON gis.parcels USING GIST (centroid);
CREATE INDEX IF NOT EXISTS idx_canals_geometry ON gis.canals USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_gates_location ON gis.gates USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_pumps_location ON gis.pumps USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_water_sources_geometry ON gis.water_sources USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_irrigation_blocks_geometry ON gis.irrigation_blocks USING GIST (geometry);

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA gis TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA gis TO postgres;