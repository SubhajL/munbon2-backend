# Claude Instance 2: SHAPE Ingestion

## Scope of Work
This instance handles GIS data processing, SHAPE file uploads, and spatial operations.

## Assigned Services

### 1. **GIS Service** (Primary)
- **Path**: `/services/gis`
- **Port**: 3007
- **Responsibilities**:
  - SHAPE file upload and processing
  - PostGIS spatial operations
  - Vector tile generation
  - Spatial queries and analysis
  - GeoJSON API endpoints

### 2. **GIS Queue Processor**
- **Path**: `/services/gis/queue-processor`
- **Port**: None (Background worker)
- **Responsibilities**:
  - Process uploaded SHAPE files
  - Extract and transform spatial data
  - Store in PostGIS
  - Generate vector tiles

### 3. **RID-MS Service** (Secondary)
- **Path**: `/services/rid-ms`
- **Port**: 3009
- **Responsibilities**:
  - Parcel management
  - Zone calculations
  - Integration with RID systems
  - Water demand by parcel

## Environment Setup

```bash
# Copy this to start your instance
cd /Users/subhajlimanond/dev/munbon2-backend

# Set up environment files
cp services/gis/.env.local.example services/gis/.env.local
cp services/rid-ms/.env.local.example services/rid-ms/.env.local
```

## Key Configurations

### PostGIS Connection
```env
# services/gis/.env.local
POSTGIS_HOST=localhost
POSTGIS_PORT=5434
POSTGIS_DB=munbon_gis
DEFAULT_SRID=4326
PROJECT_SRID=32647  # UTM Zone 47N for Thailand
```

### File Processing
```env
UPLOAD_DIR=/tmp/munbon-gis-uploads
MAX_FILE_SIZE_MB=100
ALLOWED_FORMATS=shp,geojson,kml,gpx
PROCESS_TIMEOUT_MS=300000  # 5 minutes
```

### Queue Configuration
```env
REDIS_QUEUE=gis-processing
CONCURRENT_JOBS=2
RETRY_ATTEMPTS=3
```

## Data Flow
```
SHAPE Upload → GIS Service → Redis Queue → Queue Processor → PostGIS
                                                          ↓
                                              Vector Tiles / GeoJSON API
```

## Current Status
- ✅ GIS Service: Basic structure
- ✅ File upload endpoint
- ⚠️ SHAPE processing: Needs implementation
- ⚠️ PostGIS integration: Partial
- ❌ Vector tile generation: Not started
- ❌ Queue processor: Not implemented

## Priority Tasks
1. Implement SHAPE file parser (use shapefile.js)
2. Set up PostGIS schema with spatial indexes
3. Create queue processor for async processing
4. Implement vector tile generation
5. Add spatial query endpoints
6. Handle coordinate system transformations

## Database Schema
```sql
-- Main GIS tables
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE parcels (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50) UNIQUE,
    owner_name VARCHAR(255),
    area_rai DECIMAL(10,2),
    geom GEOMETRY(Polygon, 4326),
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE zones (
    id SERIAL PRIMARY KEY,
    zone_code VARCHAR(20) UNIQUE,
    zone_name VARCHAR(100),
    geom GEOMETRY(MultiPolygon, 4326),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Spatial indexes
CREATE INDEX idx_parcels_geom ON parcels USING GIST(geom);
CREATE INDEX idx_zones_geom ON zones USING GIST(geom);
```

## Testing Commands
```bash
# Upload SHAPE file
curl -X POST http://localhost:3007/api/v1/upload/shapefile \
  -F "file=@/path/to/shapefile.zip" \
  -H "Authorization: Bearer token"

# Get parcels in area
curl "http://localhost:3007/api/v1/parcels?bbox=100.5,13.7,100.6,13.8"

# Get parcel by ID
curl http://localhost:3007/api/v1/parcels/P12345

# Export zone as GeoJSON
curl http://localhost:3007/api/v1/zones/Z1/export?format=geojson
```

## Key Files to Focus On
- `/services/gis/src/routes/upload.routes.ts`
- `/services/gis/src/services/shapefile.service.ts`
- `/services/gis/src/services/postgis.service.ts`
- `/services/gis/src/processors/shape.processor.ts`
- `/services/rid-ms/src/services/parcel.service.ts`

## Required Libraries
```json
{
  "dependencies": {
    "shapefile": "^0.6.6",
    "turf": "^6.5.0",
    "proj4": "^2.8.0",
    "geojson": "^0.5.0",
    "mapnik": "^4.5.9",
    "bull": "^4.10.0"
  }
}
```

## SHAPE File Structure Expected
```
shapefile.zip/
├── parcels.shp     # Geometry
├── parcels.shx     # Index
├── parcels.dbf     # Attributes
├── parcels.prj     # Projection
└── parcels.cpg     # Encoding (optional)
```

## Notes for Development
- Always validate SHAPE files before processing
- Handle different coordinate systems properly
- Use streaming for large files
- Implement progress tracking for uploads
- Add spatial validation (no self-intersections)
- Cache frequently accessed geometries
- Use ST_SimplifyPreserveTopology for web display