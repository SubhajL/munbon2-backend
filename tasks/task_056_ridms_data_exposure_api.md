# Task 56: RID-MS Data Exposure API

## Overview
Create REST APIs to expose shape file data, parcels, and water demand calculations for frontend visualization and water demand planning.

## Subtasks

### 1. Create Express Routes for Shape File Management
- [ ] GET /api/v1/shape-files - List uploaded shape files with pagination
- [ ] GET /api/v1/shape-files/:id - Get shape file details and processing status
- [ ] GET /api/v1/shape-files/:id/parcels - Get all parcels from a shape file
- [ ] DELETE /api/v1/shape-files/:id - Mark shape file as deleted (soft delete)

### 2. Create Parcel Query APIs
- [ ] GET /api/v1/parcels - List parcels with filters (zone, crop type, owner)
- [ ] GET /api/v1/parcels/:id - Get single parcel details with geometry
- [ ] GET /api/v1/parcels/search - Search parcels by various criteria
- [ ] PUT /api/v1/parcels/:id - Update parcel attributes (crop type, water method)

### 3. Create Zone-based APIs
- [ ] GET /api/v1/zones - List all zones with summary statistics
- [ ] GET /api/v1/zones/:zone/parcels - Get all parcels in a zone
- [ ] GET /api/v1/zones/:zone/summary - Get zone summary (area, crops, water demand)
- [ ] GET /api/v1/zones/:zone/geojson - Export zone as GeoJSON for mapping

### 4. Create Water Demand APIs
- [ ] GET /api/v1/water-demand/parcels/:id - Get water demand for a parcel
- [ ] POST /api/v1/water-demand/calculate - Calculate water demand for selected parcels
- [ ] GET /api/v1/water-demand/zones/:zone - Get aggregated water demand by zone
- [ ] GET /api/v1/water-demand/summary - Get system-wide water demand summary

### 5. Create GeoJSON Export APIs
- [ ] GET /api/v1/export/parcels/geojson - Export parcels as GeoJSON with filters
- [ ] GET /api/v1/export/zones/geojson - Export zones as GeoJSON
- [ ] GET /api/v1/export/water-demand/geojson - Export water demand heatmap
- [ ] POST /api/v1/export/custom - Custom GeoJSON export with specific attributes

### 6. Create Temporal Query APIs
- [ ] GET /api/v1/parcels/history/:id - Get parcel version history
- [ ] GET /api/v1/parcels/at-date - Get parcels valid at specific date
- [ ] GET /api/v1/zones/:zone/changes - Get zone changes over time
- [ ] GET /api/v1/shape-files/comparison - Compare two shape file uploads

### 7. Add API Documentation and Testing
- [ ] Create OpenAPI/Swagger documentation
- [ ] Add request validation middleware
- [ ] Implement proper error handling
- [ ] Create integration tests
- [ ] Add performance monitoring

## Technical Requirements

### Database Queries
- Use PostGIS functions for spatial queries
- Implement efficient pagination
- Add database indexes for common queries
- Use connection pooling

### Response Formats
- Standard JSON for data endpoints
- GeoJSON RFC 7946 for spatial data
- Include metadata in responses
- Support filtering and sorting

### Performance
- Implement caching for zone summaries
- Use database views for complex queries
- Limit GeoJSON precision for large datasets
- Support partial responses

### Security
- Validate all inputs
- Prevent SQL injection
- Rate limiting per endpoint
- Audit logging for updates

## API Examples

### List Parcels with Filters
```http
GET /api/v1/parcels?zone=Zone1&cropType=Rice&limit=50&offset=0
```

### Get Zone Summary
```http
GET /api/v1/zones/Zone1/summary

Response:
{
  "zone": "Zone1",
  "totalParcels": 1234,
  "totalAreaRai": 15678.45,
  "crops": {
    "Rice": { "count": 800, "areaRai": 10000 },
    "Corn": { "count": 434, "areaRai": 5678.45 }
  },
  "waterDemand": {
    "dailyCubicMeters": 125000,
    "method": "AWD"
  }
}
```

### Export Parcels as GeoJSON
```http
GET /api/v1/export/parcels/geojson?zone=Zone1&includeWaterDemand=true

Response:
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "parcelId": "RID-12345",
        "zone": "Zone1",
        "cropType": "Rice",
        "areaRai": 25.5,
        "waterDemandDaily": 850
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[100.123, 14.456], ...]]
      }
    }
  ]
}
```

## Dependencies
- Express.js for routing
- PostGIS for spatial queries
- @turf/turf for GeoJSON operations
- express-validator for input validation
- node-cache for caching

## Success Criteria
- All APIs return data within 500ms for standard queries
- GeoJSON exports handle 10,000+ parcels efficiently
- Proper error messages for invalid requests
- 100% test coverage for critical paths
- API documentation accessible via Swagger UI