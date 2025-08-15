-- Create temporary table to import GeoPackage data
DROP TABLE IF EXISTS temp_geopackage_import;
CREATE TEMP TABLE temp_geopackage_import (
    parcel_seq VARCHAR(50),
    sub_member INTEGER,
    parcel_area_rai NUMERIC(10,2),
    geometry GEOMETRY(Polygon, 32648)
);