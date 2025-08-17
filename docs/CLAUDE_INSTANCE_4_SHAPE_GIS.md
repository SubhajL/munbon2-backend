# Claude Instance 4: SHAPE/GIS Service

## Scope of Work
This instance handles all GIS operations, SHAPE file processing, spatial analysis, and geographic data management.

## Assigned Components

### 1. **GIS Service** (Primary)
- **Path**: `/services/gis`
- **Port**: 3007
- **Responsibilities**:
  - SHAPE file upload and processing
  - PostGIS database operations
  - Spatial queries and analysis
  - Vector tile generation
  - Coordinate transformations
  - Parcel/zone management

### 2. **GIS Queue Processor**
- **Path**: `/services/gis/src/processors/queue.processor.ts`
- **Port**: None (Background worker)
- **Queue**: `gis-processing`
- **Responsibilities**:
  - Async SHAPE file processing
  - Feature extraction and validation
  - Spatial index creation
  - Tile generation jobs

### 3. **RID-MS Integration**
- **Path**: `/services/rid-ms`
- **Port**: 3009
- **Responsibilities**:
  - RID parcel management
  - Zone calculations
  - Area measurements
  - Owner information

## Environment Setup

```bash
# GIS Service
cat > services/gis/.env.local << EOF
SERVICE_NAME=gis-service
PORT=3007
NODE_ENV=development

# PostGIS Database
POSTGIS_HOST=localhost
POSTGIS_PORT=5434
POSTGIS_DB=munbon_gis
POSTGIS_USER=postgres
POSTGIS_PASSWORD=postgres123

# Spatial Configuration
DEFAULT_SRID=4326  # WGS84
PROJECT_SRID=32647  # UTM Zone 47N (Thailand)
GEOMETRY_PRECISION=6  # decimal places

# File Processing
UPLOAD_DIR=/tmp/munbon-gis-uploads
TEMP_DIR=/tmp/munbon-gis-temp
MAX_FILE_SIZE_MB=200
ALLOWED_FORMATS=shp,zip,geojson,kml,gpx
PROCESS_TIMEOUT_MS=600000  # 10 minutes

# Vector Tiles
TILE_CACHE_DIR=/tmp/munbon-tiles
MIN_ZOOM=8
MAX_ZOOM=18
TILE_BUFFER=64
SIMPLIFICATION_TOLERANCE=1.0

# Queue Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=2
QUEUE_NAME=gis-processing
CONCURRENT_WORKERS=2

# S3 Storage (for processed files)
AWS_REGION=ap-southeast-1
S3_BUCKET=munbon-gis-data
S3_PREFIX=shapefiles/

# External Services
AUTH_SERVICE_URL=http://localhost:3001
SENSOR_SERVICE_URL=http://localhost:3003
EOF

# RID-MS Service
cat > services/rid-ms/.env.local << EOF
SERVICE_NAME=rid-ms-service
PORT=3009
NODE_ENV=development

# Database (shares with GIS)
DB_HOST=localhost
DB_PORT=5434
DB_NAME=munbon_gis
DB_USER=postgres
DB_PASSWORD=postgres123

# RID Configuration
RID_API_URL=https://rid.go.th/api
RID_API_KEY=your-rid-key
DEFAULT_PROVINCE_CODE=30  # Nakhon Ratchasima

# Calculation Parameters
HECTARE_TO_RAI=6.25
DEFAULT_CROP_TYPE=rice
EOF
```

## PostGIS Database Schema

```sql
-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Parcels table
CREATE TABLE parcels (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50) UNIQUE NOT NULL,
    rid_code VARCHAR(50),
    owner_name VARCHAR(255),
    owner_id VARCHAR(13),  -- Thai ID
    area_rai DECIMAL(10,2),
    area_sqm DECIMAL(15,2),
    crop_type VARCHAR(50),
    zone_id VARCHAR(20),
    geom GEOMETRY(Polygon, 4326),
    geom_utm GEOMETRY(Polygon, 32647),
    properties JSONB,
    source VARCHAR(50),  -- 'SHAPE', 'MANUAL', 'RID'
    upload_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Zones table
CREATE TABLE zones (
    id SERIAL PRIMARY KEY,
    zone_code VARCHAR(20) UNIQUE NOT NULL,
    zone_name VARCHAR(100),
    zone_type VARCHAR(50),  -- 'irrigation', 'administrative', 'custom'
    area_rai DECIMAL(12,2),
    geom GEOMETRY(MultiPolygon, 4326),
    geom_utm GEOMETRY(MultiPolygon, 32647),
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Canals table
CREATE TABLE canals (
    id SERIAL PRIMARY KEY,
    canal_id VARCHAR(50) UNIQUE NOT NULL,
    canal_name VARCHAR(100),
    canal_type VARCHAR(50),  -- 'main', 'lateral', 'sublateral'
    width_m DECIMAL(10,2),
    depth_m DECIMAL(10,2),
    length_m DECIMAL(15,2),
    geom GEOMETRY(LineString, 4326),
    geom_utm GEOMETRY(LineString, 32647),
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Gates/Structures
CREATE TABLE structures (
    id SERIAL PRIMARY KEY,
    structure_id VARCHAR(50) UNIQUE NOT NULL,
    structure_type VARCHAR(50),  -- 'gate', 'pump', 'weir'
    canal_id VARCHAR(50),
    location GEOMETRY(Point, 4326),
    location_utm GEOMETRY(Point, 32647),
    properties JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- SHAPE upload tracking
CREATE TABLE shape_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255),
    file_size BIGINT,
    status VARCHAR(50),  -- 'pending', 'processing', 'completed', 'failed'
    feature_count INTEGER,
    error_message TEXT,
    processed_at TIMESTAMP,
    s3_url TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Spatial indexes
CREATE INDEX idx_parcels_geom ON parcels USING GIST(geom);
CREATE INDEX idx_parcels_geom_utm ON parcels USING GIST(geom_utm);
CREATE INDEX idx_zones_geom ON zones USING GIST(geom);
CREATE INDEX idx_canals_geom ON canals USING GIST(geom);
CREATE INDEX idx_structures_location ON structures USING GIST(location);

-- Commonly used views
CREATE VIEW parcel_summary AS
SELECT 
    z.zone_code,
    z.zone_name,
    COUNT(p.id) as parcel_count,
    SUM(p.area_rai) as total_area_rai,
    COUNT(DISTINCT p.owner_id) as unique_owners
FROM zones z
LEFT JOIN parcels p ON ST_Within(p.geom, z.geom)
GROUP BY z.zone_code, z.zone_name;
```

## SHAPE File Processing

### Expected Structure
```
shapefile.zip/
├── parcels.shp      # Geometry
├── parcels.shx      # Index
├── parcels.dbf      # Attributes
├── parcels.prj      # Projection
├── parcels.cpg      # Character encoding
└── parcels.qpj      # QGIS projection (optional)

DBF Attributes Expected:
- PARCEL_ID or ID
- OWNER_NAME or OWNER
- AREA_RAI or AREA
- CROP_TYPE or CROP
- Custom fields → stored in properties JSONB
```

### Processing Pipeline
```javascript
// SHAPE processing workflow
async function processShapeFile(uploadId, filePath) {
  // 1. Extract and validate
  const extracted = await extractZip(filePath);
  const validation = await validateShapeFiles(extracted);
  
  // 2. Read projection
  const sourceProj = await readProjection(extracted.prj);
  
  // 3. Parse features
  const features = await parseShapefile(extracted.shp, extracted.dbf);
  
  // 4. Transform coordinates
  const transformed = await features.map(f => ({
    ...f,
    geometry: transformCoordinates(f.geometry, sourceProj, 'EPSG:4326'),
    geometryUTM: transformCoordinates(f.geometry, sourceProj, 'EPSG:32647')
  }));
  
  // 5. Validate geometry
  const valid = transformed.filter(f => 
    ST_IsValid(f.geometry) && 
    !ST_IsEmpty(f.geometry)
  );
  
  // 6. Store in PostGIS
  await bulkInsertParcels(valid, uploadId);
  
  // 7. Update spatial indexes
  await updateSpatialIndexes();
  
  // 8. Generate tiles
  await queueTileGeneration(valid.map(f => f.bbox));
}
```

## Current Status
- ✅ Database schema designed
- ✅ Basic service structure
- ⚠️ SHAPE upload endpoint: Partial
- ❌ Processing pipeline: Not implemented
- ❌ Vector tile generation: Not implemented
- ❌ Spatial analysis endpoints: Not implemented
- ❌ RID-MS integration: Not connected

## Priority Tasks
1. Implement SHAPE file parser using shapefile.js
2. Build coordinate transformation pipeline
3. Create bulk geometry validation
4. Implement vector tile generation
5. Build spatial query endpoints
6. Create area calculation services
7. Implement parcel merge/split operations
8. Add topology validation

## API Endpoints

### File Upload
```
POST /api/v1/gis/upload/shapefile
POST /api/v1/gis/upload/geojson
GET /api/v1/gis/uploads/{uploadId}/status

### Parcels
GET /api/v1/gis/parcels
GET /api/v1/gis/parcels/{parcelId}
GET /api/v1/gis/parcels/bbox?minLat={}&minLng={}&maxLat={}&maxLng={}
GET /api/v1/gis/parcels/within-zone/{zoneId}
PUT /api/v1/gis/parcels/{parcelId}
DELETE /api/v1/gis/parcels/{parcelId}

### Zones
GET /api/v1/gis/zones
GET /api/v1/gis/zones/{zoneId}
GET /api/v1/gis/zones/{zoneId}/parcels
GET /api/v1/gis/zones/{zoneId}/statistics

### Spatial Analysis
POST /api/v1/gis/analysis/intersection
POST /api/v1/gis/analysis/buffer
GET /api/v1/gis/analysis/nearest?lat={}&lng={}&type={}
GET /api/v1/gis/analysis/within-distance?lat={}&lng={}&distance={}

### Vector Tiles
GET /api/v1/gis/tiles/{layer}/{z}/{x}/{y}.pbf
GET /api/v1/gis/styles/{styleName}.json

### Export
GET /api/v1/gis/export/geojson?zone={zoneId}
GET /api/v1/gis/export/shapefile?zone={zoneId}
GET /api/v1/gis/export/kml?zone={zoneId}
```

## Testing Commands

```bash
# Upload SHAPE file
curl -X POST http://localhost:3007/api/v1/gis/upload/shapefile \
  -H "Authorization: Bearer token" \
  -F "file=@/path/to/parcels.zip" \
  -F "metadata={\"source\":\"RID\",\"zone\":\"Z1\"}"

# Query parcels in bounding box
curl "http://localhost:3007/api/v1/gis/parcels/bbox?minLat=14.8&minLng=102.0&maxLat=14.9&maxLng=102.1"

# Get zone statistics
curl http://localhost:3007/api/v1/gis/zones/Z1/statistics

# Export as GeoJSON
curl http://localhost:3007/api/v1/gis/export/geojson?zone=Z1 -o zone1.geojson

# Get vector tile
curl http://localhost:3007/api/v1/gis/tiles/parcels/14/12906/7466.pbf -o tile.pbf
```

## Vector Tile Generation

```javascript
// Generate vector tiles for zoom levels
async function generateVectorTiles(bbox, minZoom, maxZoom) {
  const layers = ['parcels', 'zones', 'canals', 'structures'];
  
  for (let z = minZoom; z <= maxZoom; z++) {
    const tiles = getTilesInBbox(bbox, z);
    
    for (const tile of tiles) {
      const mvt = await generateMVT(tile, layers);
      await saveTile(mvt, tile);
    }
  }
}

// Simplify geometry for zoom level
function simplifyForZoom(geometry, zoom) {
  const tolerance = getSimplificationTolerance(zoom);
  return ST_SimplifyPreserveTopology(geometry, tolerance);
}
```

## Integration Points

### With Other Services
```javascript
// Provide parcel data to ROS
export async function getParcelForWaterDemand(parcelId) {
  const parcel = await getParcel(parcelId);
  return {
    area: parcel.area_rai,
    cropType: parcel.crop_type,
    geometry: parcel.geom
  };
}

// Spatial query for sensors
export async function findParcelsNearSensor(sensorLocation, radius) {
  return db.query(`
    SELECT * FROM parcels
    WHERE ST_DWithin(
      geom::geography, 
      ST_MakePoint($1, $2)::geography, 
      $3
    )
  `, [sensorLocation.lng, sensorLocation.lat, radius]);
}
```

## Notes for Development
- Always validate geometry before insertion
- Use appropriate SRID for calculations
- Implement chunked processing for large files
- Cache frequently accessed tiles
- Use spatial indexes effectively
- Handle topology errors gracefully
- Support incremental updates
- Implement proper CRS handling