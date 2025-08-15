# GIS Data Migration Plan: Local to EC2

## Overview
The GIS service processes GeoPackage (`.gpkg`) files uploaded to AWS S3/SQS and writes spatial data to the local `munbon_dev` database. This data needs to be migrated to EC2.

## Current Architecture

### Data Flow
1. **Upload**: GeoPackage files are uploaded to S3
2. **Queue**: SQS message triggers processing
3. **Processing**: `GeoPackageProcessor` extracts parcels and zones
4. **Storage**: Data is saved to local PostgreSQL with PostGIS

### Database Details
- **Local Database**: `munbon_dev` (Docker container on port 5434)
- **Schema**: `gis`
- **Target EC2 Database**: `munbon_dev` on 43.209.22.250:5432

## Tables Created by Shapefile/GeoPackage Processing

### Primary Tables (Populated by Processing)
1. **`agricultural_plots`** (18 MB)
   - Entity: `Parcel`
   - Contains: Individual agricultural parcels/plots
   - Key fields: plot_code, boundary (geometry), properties (JSONB with RID attributes)
   
2. **`irrigation_zones`** (64 KB)
   - Entity: `Zone`
   - Contains: Irrigation zone boundaries
   - Key fields: zone_code, zone_name, boundary (geometry)

### Supporting Tables (May be populated)
3. **`shape_file_uploads`** (24 KB)
   - Tracks upload status and metadata
   - Currently empty but structure exists

### Other GIS Tables (Need verification)
- `canal_network` (64 KB)
- `control_structures` (72 KB)
- `sensor_locations` (56 KB)
- `weather_stations` (32 KB)
- `ros_water_demands` (112 KB)
- `parcels` (16 KB) - Note: Different from agricultural_plots

## Migration Steps

### 1. Pre-Migration Checks
```bash
# Check PostGIS on EC2
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 \
  "PGPASSWORD='correct_password' psql -h localhost -U postgres -d munbon_dev -c 'CREATE EXTENSION IF NOT EXISTS postgis;'"

# Verify gis schema exists
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 \
  "PGPASSWORD='correct_password' psql -h localhost -U postgres -d munbon_dev -c 'CREATE SCHEMA IF NOT EXISTS gis;'"
```

### 2. Export Local Data
```bash
# Export entire gis schema with data
PGPASSWORD=postgres pg_dump -h localhost -p 5434 -U postgres \
  -d munbon_dev -n gis -Fc -f gis_schema_full.dump

# Alternative: Export specific tables
PGPASSWORD=postgres pg_dump -h localhost -p 5434 -U postgres \
  -d munbon_dev \
  -t gis.agricultural_plots \
  -t gis.irrigation_zones \
  -t gis.shape_file_uploads \
  -t gis.canal_network \
  -t gis.control_structures \
  -t gis.sensor_locations \
  -t gis.weather_stations \
  -t gis.ros_water_demands \
  -Fc -f gis_tables.dump
```

### 3. Transfer to EC2
```bash
# Copy dump file to EC2
scp -i ~/dev/th-lab01.pem gis_schema_full.dump ubuntu@43.209.22.250:/tmp/
```

### 4. Import on EC2
```bash
# Import the schema and data
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 \
  "PGPASSWORD='correct_password' pg_restore -h localhost -U postgres \
   -d munbon_dev /tmp/gis_schema_full.dump"

# Create spatial indexes
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 \
  "PGPASSWORD='correct_password' psql -h localhost -U postgres -d munbon_dev -c '
    CREATE INDEX IF NOT EXISTS idx_plots_boundary ON gis.agricultural_plots USING GIST (boundary);
    CREATE INDEX IF NOT EXISTS idx_zones_boundary ON gis.irrigation_zones USING GIST (boundary);
  '"
```

### 5. Verify Migration
```bash
# Check row counts
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 \
  "PGPASSWORD='correct_password' psql -h localhost -U postgres -d munbon_dev -c '
    SELECT 
      '\''agricultural_plots'\'' as table_name, 
      COUNT(*) as row_count 
    FROM gis.agricultural_plots
    UNION ALL
    SELECT 
      '\''irrigation_zones'\'' as table_name, 
      COUNT(*) as row_count 
    FROM gis.irrigation_zones;
  '"
```

### 6. Update GIS Service Configuration
The service is already configured to use EC2:
```
DATABASE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev?schema=gis
```

## Important Notes

1. **Password**: The EC2 PostgreSQL password needs to be verified/updated
2. **PostGIS**: Ensure PostGIS extension is installed on EC2
3. **Spatial Indexes**: Critical for performance with geometric queries
4. **Data Volume**: agricultural_plots has 18MB of data - the largest table
5. **Service Restart**: GIS service may need restart after migration

## Post-Migration Tasks

1. Test shapefile upload functionality
2. Verify spatial queries work correctly
3. Check integration with other services (ROS, etc.)
4. Monitor performance of spatial operations
5. Set up regular backups for GIS data