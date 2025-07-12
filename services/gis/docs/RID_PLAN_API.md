# RID Plan API Documentation

This document describes the REST API endpoints for accessing and querying RID Plan parcel data that was imported from GeoPackage files.

## Base URL
```
http://localhost:3007/api/v1/rid-plan
```

## Authentication
All endpoints require JWT authentication. Include the bearer token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

## Endpoints

### 1. Get RID Plan Parcels
Retrieve RID Plan parcels with filtering and pagination support.

**Endpoint:** `GET /parcels`

**Query Parameters:**
- `amphoe` (optional): Filter by amphoe (district) name
- `tambon` (optional): Filter by tambon (sub-district) name  
- `plantId` (optional): Filter by plant/crop ID
- `minArea` (optional): Minimum area in hectares
- `maxArea` (optional): Maximum area in hectares
- `page` (optional): Page number (default: 1)
- `limit` (optional): Results per page (default: 20, max: 100)
- `bbox` (optional): Bounding box for spatial filter (format: `minLon,minLat,maxLon,maxLat`)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3007/api/v1/rid-plan/parcels?amphoe=เมืองนครราชสีมา&limit=10"
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "plotCode": "RID-12345",
        "areaHectares": 1.6,
        "areaRai": 10,
        "cropType": "rice",
        "parcelAreaRai": 10,
        "yieldAtMcKgpr": 450,
        "seasonIrrM3PerRai": 800,
        "amphoe": "เมืองนครราชสีมา",
        "tambon": "ในเมือง",
        "lastUpdated": "2025-01-10T10:30:00Z"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[102.1, 15.0], [102.11, 15.0], [102.11, 15.01], [102.1, 15.01], [102.1, 15.0]]]
      }
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 15069,
    "totalPages": 1507
  }
}
```

### 2. Get Parcel by ID
Retrieve detailed information about a specific parcel.

**Endpoint:** `GET /parcels/:id`

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3007/api/v1/rid-plan/parcels/123e4567-e89b-12d3-a456-426614174000"
```

**Response:**
```json
{
  "type": "Feature",
  "properties": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "plotCode": "RID-12345",
    "farmerId": "unknown",
    "zoneId": "zone-uuid",
    "areaHectares": 1.6,
    "areaRai": 10,
    "cropType": "rice",
    "soilType": "unknown",
    "uploadId": "ridplan-import-1736500000",
    "ridAttributes": {
      "parcelAreaRai": 10,
      "dataDateProcess": "2025-01-01T00:00:00Z",
      "startInt": "2024-11-15T00:00:00Z",
      "wpet": 1200,
      "age": 60,
      "wprod": 800,
      "plantId": "rice",
      "yieldAtMcKgpr": 450,
      "seasonIrrM3PerRai": 800,
      "autoNote": "Auto-generated"
    },
    "location": {
      "amphoe": "เมืองนครราชสีมา",
      "tambon": "ในเมือง",
      "lat": 15.0,
      "lon": 102.1
    },
    "createdAt": "2025-01-10T10:00:00Z",
    "updatedAt": "2025-01-10T10:30:00Z"
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[102.1, 15.0], [102.11, 15.0], [102.11, 15.01], [102.1, 15.01], [102.1, 15.0]]]
  }
}
```

### 3. Get Aggregated Statistics
Get statistical summary of RID Plan parcels grouped by various criteria.

**Endpoint:** `GET /statistics`

**Query Parameters:**
- `groupBy` (optional): Group results by 'amphoe', 'tambon', 'cropType', or 'zone' (default: 'amphoe')
- `amphoe` (optional): Filter by amphoe before aggregation
- `tambon` (optional): Filter by tambon before aggregation

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3007/api/v1/rid-plan/statistics?groupBy=amphoe"
```

**Response:**
```json
{
  "summary": {
    "total_parcels": 15069,
    "total_area_hectares": 24110.4,
    "total_area_rai": 150690,
    "avg_area_rai": 10,
    "unique_amphoe": 25,
    "unique_tambon": 150
  },
  "statistics": [
    {
      "amphoe": "เมืองนครราชสีมา",
      "parcel_count": 2500,
      "total_area_hectares": 4000,
      "total_area_rai": 25000,
      "avg_area_rai": 10,
      "min_area_rai": 5,
      "max_area_rai": 50,
      "total_yield_kg": 11250000,
      "avg_yield_kg_per_rai": 450,
      "total_water_usage_m3": 20000000,
      "avg_water_usage_m3_per_rai": 800
    }
  ],
  "groupedBy": "amphoe"
}
```

### 4. Search Locations
Search for amphoe or tambon names containing the search query.

**Endpoint:** `GET /search`

**Query Parameters:**
- `q` (required): Search query string
- `type` (optional): Search in 'amphoe', 'tambon', or 'both' (default: 'both')
- `limit` (optional): Maximum results (default: 10, max: 50)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3007/api/v1/rid-plan/search?q=นคร&type=amphoe"
```

**Response:**
```json
{
  "query": "นคร",
  "results": [
    {
      "name": "เมืองนครราชสีมา",
      "type": "amphoe",
      "parcel_count": 2500,
      "total_area_rai": 25000
    },
    {
      "name": "พิมาย",
      "type": "tambon",
      "amphoe": "พิมาย",
      "parcel_count": 150,
      "total_area_rai": 1500
    }
  ]
}
```

### 5. Water Demand Analysis
Calculate water demand based on RID Plan data.

**Endpoint:** `GET /water-demand`

**Query Parameters:**
- `amphoe` (optional): Filter by amphoe
- `tambon` (optional): Filter by tambon
- `month` (optional): Calculate monthly demand (1-12)

**Example Request:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3007/api/v1/rid-plan/water-demand?amphoe=เมืองนครราชสีมา"
```

**Response:**
```json
{
  "waterDemand": [
    {
      "amphoe": "เมืองนครราชสีมา",
      "tambon": "ในเมือง",
      "parcel_count": 500,
      "total_area_rai": 5000,
      "total_seasonal_water_m3": 4000000,
      "avg_water_per_rai": 800,
      "total_water_pet": 600000,
      "avg_water_pet": 1200
    }
  ],
  "summary": {
    "totalWaterDemandM3": 120000000,
    "totalAreaRai": 150000,
    "waterDemandPerRai": 800,
    "month": null
  }
}
```

## Error Responses

All endpoints return standard error responses:

```json
{
  "error": "Error message",
  "message": "Detailed error description"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing or invalid token)
- `404` - Not Found
- `500` - Internal Server Error

## Notes

1. All RID Plan parcels are identified by having `uploadId` starting with "ridplan-"
2. Areas are stored in hectares but converted to rai (1 hectare = 6.25 rai) in responses
3. Point geometries from GeoPackage are converted to small polygon buffers (50m) for compatibility
4. Water demand calculations are based on `seasonIrrM3PerRai` attribute from RID data
5. All spatial queries use WGS84 (EPSG:4326) coordinate system