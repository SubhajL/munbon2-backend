# Munbon Irrigation System - Complete API Manual for Frontend Development

## Overview
This manual provides a comprehensive reference for all API endpoints available in the Munbon Irrigation Control System. The system uses a microservices architecture with multiple specialized services.

## Base URLs
- **Development**: `http://localhost:{service-port}`
- **Production**: `https://api.munbon.com`

## Authentication
Most endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

---

# Service Endpoints

## 1. Authentication Service
**Port**: 3002  
**Base Path**: `/api/v1/auth`

### Public Endpoints

#### User Registration
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securePassword123",
  "firstName": "John",
  "lastName": "Doe",
  "phoneNumber": "+66812345678"
}
```

#### User Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securePassword123"
}

Response:
{
  "accessToken": "eyJhbGc...",
  "refreshToken": "eyJhbGc...",
  "user": {
    "id": "123",
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "roles": ["farmer", "viewer"]
  }
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refreshToken": "eyJhbGc..."
}
```

#### Logout
```http
POST /api/v1/auth/logout
Authorization: Bearer <token>
```

#### Password Recovery
```http
POST /api/v1/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### Password Reset
```http
POST /api/v1/auth/reset-password
Content-Type: application/json

{
  "token": "reset-token-from-email",
  "newPassword": "newSecurePassword123"
}
```

### Protected Endpoints

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer <token>

Response:
{
  "id": "123",
  "email": "user@example.com",
  "firstName": "John",
  "lastName": "Doe",
  "roles": ["farmer", "viewer"],
  "permissions": ["view_data", "manage_own_plots"]
}
```

#### Change Password
```http
POST /api/v1/auth/change-password
Authorization: Bearer <token>
Content-Type: application/json

{
  "currentPassword": "oldPassword123",
  "newPassword": "newPassword123"
}
```

### User Management (Admin Only)

#### List Users
```http
GET /api/v1/auth/users?page=1&limit=20&search=john
Authorization: Bearer <admin-token>
```

#### Get User Details
```http
GET /api/v1/auth/users/:userId
Authorization: Bearer <admin-token>
```

#### Update User
```http
PUT /api/v1/auth/users/:userId
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "firstName": "John",
  "lastName": "Doe",
  "roles": ["farmer", "admin"]
}
```

---

## 2. ROS (Rice Optimization System) Service
**Port**: 3012  
**Base Path**: `/api/v1/ros`

### Water Demand Calculation

#### Calculate Weekly Water Demand by Section
```http
POST /api/water-demand/section/weekly
Authorization: Bearer <token>
Content-Type: application/json

{
  "sectionId": "Z1S001",
  "week": 12,
  "year": 2025
}

Response:
{
  "sectionId": "Z1S001",
  "week": 12,
  "year": 2025,
  "totalDemand": 45678.5,
  "irrigationDemand": 40123.2,
  "effectiveRainfall": 5555.3,
  "plotCount": 25,
  "totalArea": 125.5
}
```

#### Calculate Weekly Water Demand by Zone
```http
POST /api/water-demand/zone/weekly
Authorization: Bearer <token>
Content-Type: application/json

{
  "zoneId": "Z1",
  "week": 12,
  "year": 2025
}
```

#### Get Current Water Demand Summary
```http
GET /api/water-demand/current
Authorization: Bearer <token>

Response:
{
  "currentWeek": 12,
  "year": 2025,
  "zones": [
    {
      "zoneId": "Z1",
      "totalDemand": 234567.8,
      "sections": 15,
      "plots": 450
    }
  ]
}
```

### ETO (Evapotranspiration) Data
```http
GET /api/v1/ros/eto?date=2025-03-15
Authorization: Bearer <token>

Response:
{
  "date": "2025-03-15",
  "eto": 4.5,
  "temperature": 28.5,
  "humidity": 65,
  "windSpeed": 2.3,
  "solarRadiation": 18.5
}
```

### Crop Coefficient (Kc) Data
```http
GET /api/v1/ros/kc?cropType=rice&growthStage=vegetative
Authorization: Bearer <token>

Response:
{
  "cropType": "rice",
  "growthStage": "vegetative",
  "kc": 1.05,
  "duration": 30
}
```

### Crop Information
```http
GET /api/v1/ros/crops
Authorization: Bearer <token>

Response:
{
  "crops": [
    {
      "id": "rice-rd47",
      "name": "ข้าว กข.47",
      "type": "rice",
      "duration": 120,
      "waterRequirement": "high"
    }
  ]
}
```

### Irrigation Schedule
```http
GET /api/v1/ros/schedule?zoneId=Z1&week=12
Authorization: Bearer <token>

Response:
{
  "zoneId": "Z1",
  "week": 12,
  "schedule": [
    {
      "date": "2025-03-15",
      "sections": ["Z1S001", "Z1S002"],
      "waterVolume": 12345.6,
      "duration": 480
    }
  ]
}
```

### Plot-Specific Water Demand
```http
GET /api/v1/ros/plot-demand/:plotId
Authorization: Bearer <token>

Response:
{
  "plotId": "P12345",
  "currentDemand": 234.5,
  "weeklyDemand": 1643.5,
  "cropType": "rice",
  "growthStage": "reproductive",
  "plantingDate": "2025-01-15"
}
```

### Plot Planting Dates
```http
GET /api/v1/ros/plot-planting?sectionId=Z1S001
Authorization: Bearer <token>

Response:
{
  "sectionId": "Z1S001",
  "plots": [
    {
      "plotId": "P12345",
      "plantingDate": "2025-01-15",
      "expectedHarvest": "2025-05-15",
      "cropType": "rice-rd47"
    }
  ]
}
```

---

## 3. GIS Data Service
**Port**: 3007  
**Base Path**: `/api/v1/gis`

### Zone Management

#### Get All Zones
```http
GET /api/v1/gis/zones
Authorization: Bearer <token>

Response:
{
  "zones": [
    {
      "id": "Z1",
      "name": "Zone 1",
      "area": 12345.6,
      "sections": 15,
      "parcels": 450,
      "geometry": {...}
    }
  ]
}
```

#### Get Zone Details
```http
GET /api/v1/gis/zones/:zoneId
Authorization: Bearer <token>
```

#### Get Zone Sections
```http
GET /api/v1/gis/zones/:zoneId/sections
Authorization: Bearer <token>
```

### Parcel Data
```http
GET /api/v1/gis/parcels?zoneId=Z1&page=1&limit=50
Authorization: Bearer <token>

Response:
{
  "parcels": [
    {
      "id": "P12345",
      "zoneId": "Z1",
      "sectionId": "Z1S001",
      "area": 2.5,
      "owner": "นายสมชาย ใจดี",
      "cropType": "rice",
      "geometry": {...}
    }
  ],
  "total": 450,
  "page": 1,
  "limit": 50
}
```

### Canal Network
```http
GET /api/v1/gis/canals?type=main
Authorization: Bearer <token>

Response:
{
  "canals": [
    {
      "id": "C001",
      "name": "คลองส่งน้ำสายหลัก 1",
      "type": "main",
      "length": 15234.5,
      "capacity": 50.0,
      "geometry": {...}
    }
  ]
}
```

### Map Tiles
```http
GET /api/v1/gis/tiles/{z}/{x}/{y}.png
Authorization: Bearer <token>
```

---

## 4. RID Management Service (RID-MS)
**Port**: 3011  
**Base Path**: `/api/v1`

### Shapefile Upload
```http
POST /api/v1/shapefiles/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

FormData:
- file: <shapefile.zip>
- name: "Zone 1 Parcels"
- description: "Updated parcel boundaries for Zone 1"
```

### Water Demand Calculation
```http
POST /api/v1/water-demand/calculate
Authorization: Bearer <token>
Content-Type: application/json

{
  "zoneId": "Z1",
  "startWeek": 1,
  "endWeek": 52,
  "year": 2025,
  "includeRainfall": true
}

Response:
{
  "calculationId": "calc-123",
  "status": "completed",
  "summary": {
    "totalDemand": 12345678.9,
    "peakWeek": 15,
    "peakDemand": 456789.0
  }
}
```

### Export Data
```http
GET /api/v1/export/water-demand?format=csv&zoneId=Z1&year=2025
Authorization: Bearer <token>
```

---

## 5. Sensor Data Service
**Port**: 3001  
**Base Path**: `/api/v1`

### Moisture Sensor Data
```http
GET /api/v1/public/moisture/latest
X-API-Key: <api-key>

Response:
{
  "data_type": "soil_moisture",
  "request_time": "2025-08-17T10:30:00Z",
  "sensors": [
    {
      "sensor_id": "SM001",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756,
        "zone": "Z1",
        "section": "Z1S001"
      },
      "latest_reading": {
        "timestamp": "2025-08-17T10:28:30Z",
        "moisture_percentage": 65.5,
        "temperature_celsius": 28.3,
        "battery_voltage": 3.8,
        "signal_quality": "good"
      }
    }
  ]
}
```

### Water Level Data
```http
GET /api/v1/public/waterlevel/latest
X-API-Key: <api-key>

Response:
{
  "data_type": "water_level",
  "request_time": "2025-08-17T10:30:00Z",
  "stations": [
    {
      "station_id": "WL001",
      "station_name": "คลองส่งน้ำสายหลัก 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "latest_reading": {
        "timestamp": "2025-08-17T10:25:00Z",
        "water_level_m": 2.45,
        "flow_rate_cms": 15.6,
        "temperature_celsius": 26.8
      }
    }
  ]
}
```

### AOS Weather Station Data
```http
GET /api/v1/public/aos/latest
X-API-Key: <api-key>

Response:
{
  "data_type": "aos_meteorological",
  "request_time": "2025-08-17T10:30:00Z",
  "stations": [
    {
      "station_id": "AOS001",
      "station_name": "Munbon AOS Weather Station",
      "latest_reading": {
        "timestamp": "2025-08-17T10:00:00Z",
        "temperature_celsius": 32.5,
        "humidity_percentage": 65,
        "rainfall_mm": 0,
        "wind_speed_ms": 2.3,
        "wind_direction_degrees": 180,
        "solar_radiation_wm2": 650,
        "pressure_hpa": 1013
      }
    }
  ]
}
```

---

## 6. AWD Control Service
**Port**: 3013  
**Base Path**: `/api/v1/awd`

### Water Level Control

#### Get Current Settings
```http
GET /api/v1/awd/control/:plotId
Authorization: Bearer <token>

Response:
{
  "plotId": "P12345",
  "targetLevel": 10.0,
  "currentLevel": 8.5,
  "mode": "automatic",
  "status": "filling",
  "gateStatus": "open"
}
```

#### Update Control Settings
```http
PUT /api/v1/awd/control/:plotId
Authorization: Bearer <token>
Content-Type: application/json

{
  "targetLevel": 12.0,
  "mode": "automatic"
}
```

#### Manual Gate Control
```http
POST /api/v1/awd/gate/:gateId/control
Authorization: Bearer <token>
Content-Type: application/json

{
  "action": "open",
  "duration": 30
}
```

---

## 7. Flow Monitoring Service
**Port**: 3014  
**Base Path**: `/api/v1/flow`

### Hydraulic Modeling

#### Get Flow Propagation
```http
POST /api/v1/flow/hydraulics/model/propagation
Authorization: Bearer <token>
Content-Type: application/json

{
  "sourceLocation": "C001",
  "flowRate": 15.5,
  "duration": 240
}

Response:
{
  "propagation": [
    {
      "location": "C002",
      "arrivalTime": 45,
      "peakFlow": 14.8,
      "peakTime": 60
    }
  ]
}
```

#### Flow Efficiency Analysis
```http
GET /api/v1/flow/analytics/efficiency?startDate=2025-08-01&endDate=2025-08-17
Authorization: Bearer <token>

Response:
{
  "period": {
    "start": "2025-08-01",
    "end": "2025-08-17"
  },
  "efficiency": {
    "overall": 0.85,
    "byCanal": {
      "C001": 0.88,
      "C002": 0.82
    }
  },
  "losses": {
    "total": 12345.6,
    "seepage": 8901.2,
    "evaporation": 3444.4
  }
}
```

---

## 8. Scheduler Service
**Port**: 3021  
**Base Path**: `/api/v1/scheduler`

### Schedule Management

#### Get Weekly Schedule
```http
GET /api/v1/scheduler/schedule/week/12?year=2025
Authorization: Bearer <token>

Response:
{
  "week": 12,
  "year": 2025,
  "status": "approved",
  "schedule": [
    {
      "date": "2025-03-17",
      "zone": "Z1",
      "sections": ["Z1S001", "Z1S002"],
      "startTime": "06:00",
      "duration": 480,
      "waterVolume": 45678.9
    }
  ]
}
```

#### Generate Schedule
```http
POST /api/v1/scheduler/schedule/week/13/generate
Authorization: Bearer <token>
Content-Type: application/json

{
  "optimizationMode": "water-saving",
  "constraints": {
    "maxConcurrentSections": 3,
    "maintenanceWindows": [
      {
        "date": "2025-03-25",
        "startTime": "09:00",
        "duration": 240
      }
    ]
  }
}
```

### Field Operations

#### Get Team Instructions
```http
GET /api/v1/scheduler/field-ops/instructions/team-a
Authorization: Bearer <token>

Response:
{
  "team": "team-a",
  "date": "2025-08-17",
  "instructions": [
    {
      "time": "06:00",
      "location": "Gate G001",
      "action": "open",
      "settings": {
        "opening": 75,
        "flowRate": 15.5
      }
    }
  ]
}
```

---

## 9. Weather Monitoring Service
**Port**: 3004  
**Base Path**: `/api/v1/weather`

### Weather Data
```http
GET /api/v1/weather/current
Authorization: Bearer <token>

Response:
{
  "location": "Munbon Project Area",
  "timestamp": "2025-08-17T10:30:00Z",
  "temperature": 32.5,
  "humidity": 65,
  "rainfall": 0,
  "forecast": {
    "today": {
      "rainProbability": 20,
      "expectedRainfall": 0
    },
    "tomorrow": {
      "rainProbability": 60,
      "expectedRainfall": 15
    }
  }
}
```

---

## 10. Water Accounting Service
**Port**: 3020  
**Base Path**: `/api/v1/accounting`

### Deficit Management

#### Get Weekly Deficit
```http
GET /api/v1/accounting/deficit/week/12/2025
Authorization: Bearer <token>

Response:
{
  "week": 12,
  "year": 2025,
  "deficits": [
    {
      "sectionId": "Z1S001",
      "plannedSupply": 12345.6,
      "actualSupply": 11234.5,
      "deficit": 1111.1,
      "carryForward": 2222.2
    }
  ]
}
```

---

## Error Responses

All services use standard HTTP status codes and return errors in this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field": "email",
      "reason": "Invalid email format"
    }
  },
  "timestamp": "2025-08-17T10:30:00Z",
  "path": "/api/v1/auth/register"
}
```

### Common Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Unprocessable Entity
- `429` - Too Many Requests
- `500` - Internal Server Error

---

## Rate Limiting

Most services implement rate limiting:
- **Default**: 100 requests per 15 minutes per IP
- **Auth endpoints**: 5 requests per 15 minutes per IP
- **Data upload**: 10 requests per hour per user

---

## WebSocket Endpoints

### Real-time Sensor Data
```
ws://localhost:3001/ws/sensors
Authorization: Bearer <token>

// Subscribe to sensor updates
{
  "action": "subscribe",
  "sensors": ["SM001", "WL001"]
}

// Receive updates
{
  "type": "update",
  "sensor": "SM001",
  "data": {
    "moisture": 65.5,
    "timestamp": "2025-08-17T10:30:00Z"
  }
}
```

---

## API Versioning

All APIs use versioning in the URL path:
- Current version: `v1`
- Version in path: `/api/v1/...`

When new versions are released, old versions will be maintained for backward compatibility for at least 6 months.

---

## SDK Support

### JavaScript/TypeScript
```bash
npm install @munbon/api-client
```

```javascript
import { MunbonClient } from '@munbon/api-client';

const client = new MunbonClient({
  apiKey: 'your-api-key',
  environment: 'production'
});

const moistureData = await client.sensors.getMoistureLatest();
```

### Python
```bash
pip install munbon-api
```

```python
from munbon_api import MunbonClient

client = MunbonClient(api_key='your-api-key')
moisture_data = client.sensors.get_moisture_latest()
```

---

## Support

For API support and questions:
- Email: api-support@munbon.com
- Documentation: https://docs.munbon.com/api
- Status Page: https://status.munbon.com