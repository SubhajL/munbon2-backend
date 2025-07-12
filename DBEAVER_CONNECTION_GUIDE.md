# DBeaver Connection Guide for Munbon Backend

This guide provides all the connection details needed to set up DBeaver for viewing PostgreSQL, PostGIS, and TimescaleDB databases.

## Quick Setup Summary

You have two main database containers running:
1. **PostgreSQL with PostGIS** - Port 5432 (Spatial & general data)
2. **TimescaleDB** - Port 5433 (Time-series sensor data)

## 1. PostgreSQL with PostGIS (Main Database)

**Connection Details:**
- **Host:** localhost
- **Port:** 5432
- **Database:** munbon_dev
- **Username:** postgres
- **Password:** postgres
- **URL:** postgresql://postgres:postgres@localhost:5432/munbon_dev

**PostGIS Features:**
- PostGIS 3.3 is installed
- Handles spatial data for GIS operations
- Will store land parcels, irrigation zones, etc.

**Setup in DBeaver:**
1. Click "New Database Connection" → Select "PostgreSQL"
2. Enter the connection details above
3. Click "Test Connection" (download driver if prompted)
4. Click "Finish"

## 2. TimescaleDB (Time-Series Database)

**Connection Details:**
- **Host:** localhost
- **Port:** 5433 (⚠️ Different port!)
- **Database:** munbon_timescale (or sensor_data)
- **Username:** postgres
- **Password:** postgres
- **URL:** postgresql://postgres:postgres@localhost:5433/munbon_timescale

**TimescaleDB Features:**
- Optimized for time-series data
- Stores sensor readings, water levels, etc.
- Hypertables for automatic data partitioning

**Setup in DBeaver:**
1. Create new PostgreSQL connection (TimescaleDB uses PostgreSQL driver)
2. Enter the connection details above (note port 5433)
3. Test connection

## 3. Additional PostgreSQL Databases

### Main Development Database
- **Host:** localhost
- **Port:** 5432
- **Database:** munbon_dev
- **Username:** postgres
- **Password:** postgres
- **URL:** postgresql://postgres:postgres@localhost:5432/munbon_dev

### Other Service-Specific Databases
Based on Docker Compose configuration, you may also have:
- Authentication service data
- User management data
- System configuration data

## 4. MongoDB (Document Store)

**Connection Details:**
- **Host:** localhost
- **Port:** 27017
- **Database:** munbon_dev
- **Username:** admin
- **Password:** admin
- **Authentication Database:** admin
- **URL:** mongodb://admin:admin@localhost:27017/munbon_dev?authSource=admin

## 5. Redis (Cache)

**Connection Details:**
- **Host:** localhost
- **Port:** 6379
- **Password:** (no password)

## 6. InfluxDB (Metrics)

**Connection Details:**
- **Host:** localhost
- **Port:** 8086
- **Organization:** munbon
- **Username:** admin
- **Password:** admin123456
- **Token:** local-dev-token
- **Bucket:** metrics

## DBeaver Setup Steps

### For PostgreSQL/PostGIS/TimescaleDB:
1. Download PostgreSQL driver if not already installed
2. Create new connection → PostgreSQL
3. Fill in connection details from above
4. Go to "Driver Properties" tab and add:
   - `currentSchema` = `gis` (for GIS database)
   - `ssl` = `false`
5. Test connection and save

### Viewing Spatial Data:
1. For PostGIS tables, you can view geometry columns as:
   - WKT (Well-Known Text)
   - WKB (Well-Known Binary)
   - GeoJSON
   - Visual map (if DBeaver spatial viewer is installed)

### Useful SQL Queries for PostGIS:

```sql
-- View PostGIS version
SELECT PostGIS_Full_Version();

-- Count parcels
SELECT COUNT(*) FROM gis.parcels;

-- View parcel with geometry as GeoJSON
SELECT parcel_code, ST_AsGeoJSON(geometry) as geojson 
FROM gis.parcels 
LIMIT 5;

-- Find parcels in a specific area
SELECT parcel_code, area, owner_name 
FROM gis.parcels 
WHERE ST_Within(
  geometry, 
  ST_MakeEnvelope(102.15, 14.68, 102.16, 14.69, 4326)
);

-- View all spatial tables
SELECT f_table_schema, f_table_name, f_geometry_column, srid, type
FROM geometry_columns
WHERE f_table_schema = 'gis';
```

### Troubleshooting:

1. **Connection refused on port 5432:**
   - Check if PostgreSQL is running: `pg_isready`
   - Check if it's using a different port: `lsof -i :5432`

2. **Authentication failed:**
   - For local development, PostgreSQL might be configured for trust authentication
   - Try connecting without a password first

3. **Cannot see PostGIS functions:**
   - Ensure you're connected to the correct database (munbon_gis)
   - Run `CREATE EXTENSION IF NOT EXISTS postgis;` if needed

4. **TimescaleDB connection issues:**
   - Make sure you're using port 5433, not 5432
   - TimescaleDB container might need to be started: `docker-compose up timescaledb`

## Notes:
- All services are configured for local development
- In production, credentials will be different and connections will use SSL
- PostGIS spatial data can be exported as shapefiles, GeoJSON, or KML from DBeaver