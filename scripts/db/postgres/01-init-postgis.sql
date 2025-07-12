-- Enable PostGIS extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS postgis_raster;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;

-- Enable additional useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Create schemas for different services
CREATE SCHEMA IF NOT EXISTS gis;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS config;

-- Set default search path
ALTER DATABASE munbon_dev SET search_path TO public, gis, auth, config;

-- Create a read-only user for analytics
CREATE USER munbon_reader WITH PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE munbon_dev TO munbon_reader;
GRANT USAGE ON SCHEMA public, gis TO munbon_reader;

-- Create application user with proper permissions
CREATE USER munbon_app WITH PASSWORD 'app_password';
GRANT CONNECT ON DATABASE munbon_dev TO munbon_app;
GRANT USAGE ON SCHEMA public, gis, auth, config TO munbon_app;
GRANT CREATE ON SCHEMA public, gis, auth, config TO munbon_app;

-- Set up PostGIS for Thai coordinate systems
-- EPSG:32647 - WGS 84 / UTM zone 47N (Thailand)
-- EPSG:32648 - WGS 84 / UTM zone 48N (Thailand)
INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, proj4text, srtext)
VALUES (
    32647,
    'EPSG',
    32647,
    '+proj=utm +zone=47 +datum=WGS84 +units=m +no_defs',
    'PROJCS["WGS 84 / UTM zone 47N",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",99],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","32647"]]'
) ON CONFLICT (srid) DO NOTHING;

-- Performance tuning for spatial queries
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET random_page_cost = 1.1;

-- Create function for updating modified timestamps
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';