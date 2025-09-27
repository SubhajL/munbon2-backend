#!/bin/bash

echo "=== Direct Import to EC2 Database ==="
echo "Date: $(date)"

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"

# First, convert geopackage to SQL locally
echo "1. Converting geopackages to SQL..."

# Convert RID-MS data
echo "Converting RID-MS parcels data..."
ogr2ogr -f "CSV" -lco GEOMETRY=AS_WKT ridplan_data.csv data_ridplan/excel_rice_20250810_merge/excel_rice_20250810_merge.gpkg

# Convert water level data  
echo "Converting water level data..."
ogr2ogr -f "CSV" -lco GEOMETRY=AS_WKT water_level_data.csv data_water_level/data_water_level.gpkg

# Copy CSV files to EC2
echo "2. Copying CSV files to EC2..."
scp -i $SSH_KEY ridplan_data.csv water_level_data.csv ubuntu@$EC2_IP:/tmp/

# Import data on EC2
echo "3. Importing data to database..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
cd /tmp

# Import RID-MS parcels as JSONB
echo "Importing RID-MS parcels..."
docker exec -i postgres_timescale_postgis psql -U postgres -d munbon_dev << 'EOSQL'
-- Create temporary table for CSV import
CREATE TEMP TABLE temp_ridplan (
    geom text,
    PARCEL_SEQ text,
    zone_area text,
    area_rai numeric,
    batch_date_int bigint,
    start_int bigint,
    crop_cycle bigint,
    wpet numeric,
    wprod numeric,
    age bigint,
    plant_id text,
    stage_age bigint,
    yield_at_mc_kgpr numeric,
    season_rain_m3_per_rai numeric,
    season_irri_m3_per_rai numeric,
    season_water_input_m3_per_rai numeric,
    auto_note text
);

\copy temp_ridplan FROM 'ridplan_data.csv' WITH CSV HEADER;

-- Insert into gis.parcels as JSONB
INSERT INTO gis.parcels (data)
SELECT jsonb_build_object(
    'type', 'rid_ms_parcel',
    'source', 'excel_rice_20250810_merge',
    'import_date', NOW(),
    'parcel_data', jsonb_build_object(
        'parcel_seq', PARCEL_SEQ,
        'zone_area', zone_area,
        'area_rai', area_rai,
        'batch_date', batch_date_int,
        'start_date', start_int,
        'crop_cycle', crop_cycle,
        'wpet', wpet,
        'wprod', wprod,
        'age', age,
        'plant_id', plant_id,
        'stage_age', stage_age,
        'yield_at_mc_kgpr', yield_at_mc_kgpr,
        'season_rain_m3_per_rai', season_rain_m3_per_rai,
        'season_irri_m3_per_rai', season_irri_m3_per_rai,
        'season_water_input_m3_per_rai', season_water_input_m3_per_rai,
        'auto_note', auto_note,
        'geometry_wkt', geom
    )
)
FROM temp_ridplan;

SELECT COUNT(*) as imported_parcels FROM temp_ridplan;
EOSQL

# Import water level data
echo "Importing water level data..."
docker exec -i postgres_timescale_postgis psql -U postgres -d munbon_dev << 'EOSQL'
-- Create temporary table for CSV import
CREATE TEMP TABLE temp_water_level (
    geom text,
    crop_id text,
    project_name text,
    lat_y numeric,
    lon_x numeric,
    act_date text,
    water_level_mm text
);

\copy temp_water_level FROM 'water_level_data.csv' WITH CSV HEADER;

-- Insert into manual water level readings
INSERT INTO ros_gis.manual_water_level_readings 
(location_id, section_id, plot_id, water_level_m, reading_date,
 volunteer_name, geopackage_source, coordinates, notes)
SELECT 
    crop_id as location_id,
    'MB-001' as section_id,
    project_name as plot_id,
    COALESCE(NULLIF(water_level_mm, '')::numeric, 0) / 1000.0 as water_level_m,
    act_date::date as reading_date,
    'RID-MS Import' as volunteer_name,
    'data_water_level.gpkg' as geopackage_source,
    ST_GeomFromText('POINT(' || lon_x || ' ' || lat_y || ')', 4326) as coordinates,
    'Original water level: ' || COALESCE(water_level_mm, '0') || 'mm' as notes
FROM temp_water_level
WHERE act_date IS NOT NULL;

SELECT COUNT(*) as imported_water_levels FROM temp_water_level WHERE act_date IS NOT NULL;
EOSQL

# Check results
echo ""
echo "=== Checking imported data ==="
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT COUNT(*) as total_parcels,
       COUNT(*) FILTER (WHERE data->>'type' = 'rid_ms_parcel') as rid_ms_parcels
FROM gis.parcels;"

docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT COUNT(*) as total_water_levels,
       MIN(reading_date) as earliest_date,
       MAX(reading_date) as latest_date
FROM ros_gis.manual_water_level_readings 
WHERE geopackage_source = 'data_water_level.gpkg';"

# Cleanup
rm -f /tmp/ridplan_data.csv /tmp/water_level_data.csv
EOF

# Cleanup local files
rm -f ridplan_data.csv water_level_data.csv

echo ""
echo "=== Import completed successfully ===" 