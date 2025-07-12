# RID-MS Data Exposure API Documentation

## Base URL
```
http://localhost:3048/api/v1
```

## Authentication
All endpoints require authentication via Bearer token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### 1. Parcels API

#### List Parcels
```http
GET /parcels?zone=Zone1&cropType=Rice&limit=50&offset=0
```

Query Parameters:
- `zone` (optional): Filter by zone
- `cropType` (optional): Filter by crop type
- `ownerName` (optional): Filter by owner name (partial match)
- `waterDemandMethod` (optional): Filter by method (RID-MS, ROS, AWD)
- `limit` (optional): Number of results (default: 50, max: 1000)
- `offset` (optional): Pagination offset (default: 0)
- `sortBy` (optional): Sort field (parcelId, zone, areaRai, createdAt)
- `sortOrder` (optional): Sort order (asc, desc)

Response:
```json
{
  "parcels": [
    {
      "id": "uuid",
      "parcel_id": "RID-12345",
      "zone": "Zone1",
      "area_rai": 25.5,
      "crop_type": "Rice",
      "owner_name": "John Doe",
      "water_demand_method": "AWD",
      "centroid": {
        "type": "Point",
        "coordinates": [100.123, 14.456]
      }
    }
  ],
  "pagination": {
    "total": 1234,
    "limit": 50,
    "offset": 0,
    "pages": 25
  }
}
```

#### Get Single Parcel
```http
GET /parcels/:id
```

Response includes full geometry and latest water demand calculation.

#### Search Parcels
```http
GET /parcels/search?q=rice&searchFields=parcel_id,owner_name&limit=50
```

#### Get Parcel History
```http
GET /parcels/history/:parcelId
```

#### Update Parcel
```http
PUT /parcels/:id
Content-Type: application/json

{
  "cropType": "Corn",
  "waterDemandMethod": "ROS",
  "plantingDate": "2024-03-15"
}
```

### 2. Zones API

#### List Zones
```http
GET /zones?includeStats=true
```

Response:
```json
{
  "zones": [
    {
      "zone": "Zone1",
      "stats": {
        "parcelCount": 1234,
        "totalAreaRai": 15678.45,
        "cropTypes": 5,
        "uniqueOwners": 890,
        "crops": [
          {
            "crop_type": "Rice",
            "count": 800,
            "area_rai": 10000
          }
        ]
      }
    }
  ]
}
```

#### Get Zone Parcels
```http
GET /zones/:zone/parcels?cropType=Rice&limit=100
```

#### Get Zone Summary
```http
GET /zones/:zone/summary?date=2024-03-15
```

Response:
```json
{
  "zone": "Zone1",
  "date": "2024-03-15",
  "totalParcels": 1234,
  "totalAreaRai": 15678.45,
  "cropDistribution": {
    "Rice": { "count": 800, "areaRai": 10000 },
    "Corn": { "count": 434, "areaRai": 5678.45 }
  },
  "waterDemandByMethod": {
    "AWD": 85000,
    "ROS": 40000,
    "RID-MS": 25000
  },
  "totalDailyDemandCubicMeters": 150000
}
```

#### Get Zone GeoJSON
```http
GET /zones/:zone/geojson?includeWaterDemand=true&simplify=true&precision=6
```

#### Get Zone Changes
```http
GET /zones/:zone/changes?startDate=2024-01-01&endDate=2024-03-31
```

### 3. Water Demand API

#### Get Parcel Water Demand
```http
GET /water-demand/parcels/:id?date=2024-03-15
```

#### Calculate Water Demand
```http
POST /water-demand/calculate
Content-Type: application/json

{
  "parcelIds": ["uuid1", "uuid2"],
  "method": "AWD",
  "referenceET": 5.2,
  "rainfall": 2.1,
  "growthStage": "mid"
}
```

#### Get Zone Water Demand
```http
GET /water-demand/zones/:zone?date=2024-03-15&method=AWD
```

#### Get Water Demand Summary
```http
GET /water-demand/summary?groupBy=zone&date=2024-03-15
```

#### Get Water Demand History
```http
GET /water-demand/history/:parcelId?startDate=2024-01-01&endDate=2024-03-31
```

### 4. Export API

#### Export Parcels as GeoJSON
```http
GET /export/parcels/geojson?zone=Zone1&includeWaterDemand=true&limit=10000
```

Features:
- Filter by zone, crop type, water demand method
- Include/exclude water demand data
- Simplify geometries for performance
- Adjust coordinate precision

#### Export Zones as GeoJSON
```http
GET /export/zones/geojson?includeStats=true&includeWaterDemand=true
```

Returns zone boundaries with aggregated statistics.

#### Export Water Demand Heatmap
```http
GET /export/water-demand/geojson?zone=Zone1&resolution=medium
```

Resolution options:
- `high`: ~111m grid cells
- `medium`: ~555m grid cells  
- `low`: ~1.1km grid cells

#### Custom Export
```http
POST /export/custom
Content-Type: application/json

{
  "type": "parcels",
  "filters": {
    "zone": "Zone1",
    "cropType": "Rice"
  },
  "attributes": ["parcel_id", "area_rai", "owner_name"],
  "format": "geojson",
  "simplify": true,
  "precision": 4
}
```

### 5. Shape Files API (Existing)

#### List Shape Files
```http
GET /shapefiles?status=processed&limit=20
```

#### Get Shape File Details
```http
GET /shapefiles/:id
```

#### Get Shape File Parcels
```http
GET /shapefiles/:shapeFileId/parcels
```

## Error Responses

All errors follow this format:
```json
{
  "error": "Error message",
  "details": "Additional error details (optional)"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not Found
- `500` - Internal Server Error

## Performance Considerations

1. **Large GeoJSON Exports**: Use pagination and simplification
2. **Zone Summaries**: Cached for performance
3. **Water Demand Calculations**: May take time for large sets
4. **Coordinate Precision**: Reduce for smaller payloads

## Rate Limiting

- Default: 100 requests per 15 minutes per IP
- Configurable via environment variables

## Example Usage

### Get parcels in Zone1 with AWD method
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3048/api/v1/parcels?zone=Zone1&waterDemandMethod=AWD"
```

### Export Zone1 as GeoJSON for visualization
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3048/api/v1/zones/Zone1/geojson?includeWaterDemand=true" \
  > zone1.geojson
```

### Calculate water demand for selected parcels
```bash
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "parcelIds": ["uuid1", "uuid2"],
    "method": "AWD",
    "referenceET": 5.2
  }' \
  "http://localhost:3048/api/v1/water-demand/calculate"
```