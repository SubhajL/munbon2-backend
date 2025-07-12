-- Create PostGIS extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS postgis_raster;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS address_standardizer;

-- Create GIS schema
CREATE SCHEMA IF NOT EXISTS gis;

-- Set search path
SET search_path TO gis, public;

-- Create spatial reference table for Thailand
INSERT INTO spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text)
VALUES (
  32647,
  'EPSG',
  32647,
  'PROJCS["WGS 84 / UTM zone 47N",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",99],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","32647"]]',
  '+proj=utm +zone=47 +datum=WGS84 +units=m +no_defs'
) ON CONFLICT (srid) DO NOTHING;

-- Create function to update geometry area
CREATE OR REPLACE FUNCTION gis.update_geometry_area()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.geometry IS NOT NULL THEN
    NEW.area = ST_Area(ST_Transform(NEW.geometry, 32647)) / 10000; -- Convert to hectares
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create function to update geometry length
CREATE OR REPLACE FUNCTION gis.update_geometry_length()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.geometry IS NOT NULL THEN
    NEW.length = ST_Length(ST_Transform(NEW.geometry, 32647)); -- Length in meters
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL ON SCHEMA gis TO postgres;
GRANT USAGE ON SCHEMA gis TO PUBLIC;