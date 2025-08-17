# GIS Data Service

Comprehensive spatial data management service for the Munbon Irrigation Control System, providing GIS operations, vector tile serving, and spatial analysis capabilities.

## Features

- **Spatial Data Management**
  - Zone management (irrigation zones with water allocation)
  - Parcel tracking (land parcels with ownership and crop data)
  - Canal network (water distribution infrastructure)
  - Gate and pump locations
  - Water source management

- **Vector Tile Serving**
  - Mapbox Vector Tile (MVT) format
  - Dynamic tile generation with caching
  - Multiple zoom levels (8-20)
  - Automatic simplification for performance

- **Spatial Operations**
  - Buffer, union, intersection operations
  - Distance and area calculations
  - Coordinate transformation
  - Network topology analysis

- **Data Import/Export**
  - GeoJSON support
  - Bulk operations
  - Shapefile import (planned)

## Technology Stack

- **Runtime**: Node.js with TypeScript
- **Framework**: Express.js
- **Database**: PostgreSQL with PostGIS
- **ORM**: TypeORM
- **Cache**: Redis
- **Spatial Libraries**: Turf.js, geojson-vt, vt-pbf

## API Endpoints

### Zones
- `GET /api/v1/zones` - List all zones
- `GET /api/v1/zones/:id` - Get zone details
- `POST /api/v1/zones` - Create new zone
- `PUT /api/v1/zones/:id` - Update zone
- `DELETE /api/v1/zones/:id` - Delete zone
- `GET /api/v1/zones/:id/statistics` - Zone statistics
- `GET /api/v1/zones/:id/parcels` - Parcels in zone

### Parcels
- `GET /api/v1/parcels` - List all parcels
- `GET /api/v1/parcels/:id` - Get parcel details
- `POST /api/v1/parcels` - Create new parcel
- `PUT /api/v1/parcels/:id` - Update parcel
- `DELETE /api/v1/parcels/:id` - Delete parcel
- `POST /api/v1/parcels/:id/transfer` - Transfer ownership
- `GET /api/v1/parcels/:id/crop-plan` - Get crop plan
- `POST /api/v1/parcels/merge` - Merge parcels
- `POST /api/v1/parcels/:id/split` - Split parcel

### Canals
- `GET /api/v1/canals` - List all canals
- `GET /api/v1/canals/:id` - Get canal details
- `POST /api/v1/canals` - Create new canal
- `PUT /api/v1/canals/:id` - Update canal
- `DELETE /api/v1/canals/:id` - Delete canal
- `GET /api/v1/canals/:id/flow-history` - Flow history
- `POST /api/v1/canals/:id/flow` - Update flow rate
- `GET /api/v1/canals/network/topology` - Network topology
- `POST /api/v1/canals/network/optimize-flow` - Optimize flow

### Vector Tiles
- `GET /api/v1/tiles/:layer/:z/:x/:y.pbf` - Get vector tile
- `GET /api/v1/tiles/layers` - Available layers
- `GET /api/v1/tiles/metadata/:layer` - Layer metadata
- `GET /api/v1/tiles/style/:style` - MapboxGL style

### Spatial Operations
- `POST /api/v1/spatial/query/bounds` - Query by bounds
- `POST /api/v1/spatial/query/distance` - Query by distance
- `POST /api/v1/spatial/buffer` - Buffer operation
- `POST /api/v1/spatial/union` - Union operation
- `POST /api/v1/spatial/intersection` - Intersection
- `POST /api/v1/spatial/area` - Calculate area
- `GET /api/v1/spatial/elevation/:lng/:lat` - Get elevation

## Environment Variables

```env
# Application
NODE_ENV=development
PORT=3006

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=munbon_gis
DB_USER=postgres
DB_PASSWORD=your_password
DB_SCHEMA=gis

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=

# JWT (for authentication)
JWT_SECRET=your_jwt_secret

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:4200

# Tile Configuration
TILE_CACHE_ENABLED=true
TILE_MAX_ZOOM=20
TILE_MIN_ZOOM=8
```

## Installation

1. Install dependencies:
```bash
npm install
```

2. Set up PostGIS database:
```sql
CREATE DATABASE munbon_gis;
\c munbon_gis;
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
CREATE SCHEMA gis;
```

3. Run migrations:
```bash
npm run migration:run
```

4. Start development server:
```bash
npm run dev
```

## Docker

Build and run with Docker:

```bash
# Build image
docker build -t munbon-gis-service .

# Run container
docker run -p 3006:3006 \
  -e DB_HOST=host.docker.internal \
  -e REDIS_URL=redis://host.docker.internal:6379 \
  munbon-gis-service
```

## Database Schema

### Zones Table
- `id` (UUID) - Primary key
- `code` (string) - Zone code
- `name` (string) - Zone name
- `type` (enum) - irrigation/drainage/mixed
- `geometry` (Polygon) - PostGIS geometry
- `area` (float) - Area in hectares
- `water_allocation` (float) - Water allocation in m³

### Parcels Table
- `id` (UUID) - Primary key
- `parcel_code` (string) - Parcel registration code
- `zone_id` (UUID) - Foreign key to zones
- `geometry` (Polygon) - PostGIS geometry
- `area` (float) - Area in hectares
- `land_use_type` (string) - Current land use
- `owner_name` (string) - Owner name
- `irrigation_status` (enum) - irrigated/non-irrigated/partial

### Canals Table
- `id` (UUID) - Primary key
- `code` (string) - Canal code
- `name` (string) - Canal name
- `type` (enum) - main/secondary/tertiary/field
- `geometry` (LineString) - PostGIS geometry
- `length` (float) - Length in meters
- `capacity` (float) - Flow capacity in m³/s
- `current_flow` (float) - Current flow rate

## Vector Tile Layers

### Available Layers
1. **zones** - Irrigation zones (zoom 8-18)
2. **parcels** - Land parcels (zoom 12-20)
3. **canals** - Canal network (zoom 10-20)
4. **gates** - Water gates (zoom 12-20)
5. **pumps** - Pump stations (zoom 12-20)

### Tile URL Format
```
https://api.munbon.com/api/v1/tiles/{layer}/{z}/{x}/{y}.pbf
```

### Example MapboxGL Usage
```javascript
map.addSource('munbon', {
  type: 'vector',
  tiles: ['https://api.munbon.com/api/v1/tiles/{z}/{x}/{y}.pbf'],
  minzoom: 8,
  maxzoom: 20
});

map.addLayer({
  id: 'zones',
  type: 'fill',
  source: 'munbon',
  'source-layer': 'zones',
  paint: {
    'fill-color': '#729fcf',
    'fill-opacity': 0.5
  }
});
```

## Performance Optimization

1. **Tile Caching**
   - Redis-based tile cache
   - 1-hour TTL for vector tiles
   - Pre-generation for popular areas

2. **Geometry Simplification**
   - Automatic simplification at lower zoom levels
   - Area-based filtering for small features

3. **Database Optimization**
   - Spatial indexes on all geometry columns
   - Clustered indexes for frequently queried fields
   - Query result caching

## Testing

```bash
# Run unit tests
npm test

# Run integration tests
npm run test:integration

# Run with coverage
npm run test:coverage
```

## API Examples

### Create a new zone
```bash
curl -X POST http://localhost:3006/api/v1/zones \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "code": "ZONE_001",
    "name": "North Irrigation Zone",
    "type": "irrigation",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[100.5, 13.5], [100.6, 13.5], [100.6, 13.6], [100.5, 13.6], [100.5, 13.5]]]
    },
    "waterAllocation": 1000000
  }'
```

### Query parcels within bounds
```bash
curl -X POST http://localhost:3006/api/v1/spatial/query/bounds \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "tableName": "parcels",
    "bounds": [100.5, 13.5, 100.6, 13.6],
    "properties": ["id", "parcel_code", "area", "owner_name"]
  }'
```

### Get vector tile
```bash
curl http://localhost:3006/api/v1/tiles/zones/10/817/507.pbf \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output tile.pbf
```

## Monitoring

- Health check endpoint: `GET /health`
- Prometheus metrics: `GET /metrics` (planned)
- Structured logging with Winston
- Performance tracking for tile generation

## Security

- JWT authentication required for write operations
- Role-based access control (RBAC)
- Input validation with Zod schemas
- SQL injection prevention via TypeORM
- Rate limiting on tile endpoints

## Contributing

1. Follow TypeScript best practices
2. Write tests for new features
3. Update API documentation
4. Run linter before committing

## License

Proprietary - Munbon Irrigation Project