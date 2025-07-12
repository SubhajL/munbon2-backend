# ROS Service API Documentation

## Overview
The ROS (Reservoir Operation System) Service provides water demand calculation and irrigation scheduling endpoints for the Munbon Irrigation Control System.

**Base URL**: `http://localhost:3047/api/v1/ros`

## Authentication
All endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### 1. ETo Data Management

#### Upload ETo Data from Excel
```http
POST /eto/upload
Content-Type: multipart/form-data

Form Data:
- file: Excel file (.xlsx) containing monthly ETo data
```

**Response**:
```json
{
  "success": true,
  "message": "Successfully imported 12 ETo records",
  "count": 12
}
```

#### Get ETo Data
```http
GET /eto?aosStation=นครราชสีมา&month=5
```

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": 5,
      "aosStation": "นครราชสีมา",
      "province": "นครราชสีมา",
      "month": 5,
      "etoValue": 148.8
    }
  ]
}
```

#### Download ETo Template
```http
GET /eto/template
```
Returns an Excel template for ETo data upload.

### 2. Kc Data Management

#### Upload Kc Data from Excel
```http
POST /kc/upload
Content-Type: multipart/form-data

Form Data:
- file: Excel file (.xlsx) containing weekly Kc data
```

#### Get Kc Data
```http
GET /kc?cropType=rice&cropWeek=5
```

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": 5,
      "cropType": "rice",
      "cropWeek": 5,
      "kcValue": 1.10
    }
  ]
}
```

#### Download Kc Template
```http
GET /kc/template
```

### 3. Water Demand Calculation

#### Calculate Water Demand for Single Week
```http
POST /demand/calculate
Content-Type: application/json

{
  "areaId": "Z1-S1",
  "areaType": "section",
  "areaRai": 1000,
  "cropType": "rice",
  "cropWeek": 5,
  "calendarWeek": 18,
  "calendarYear": 2024
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "areaId": "Z1-S1",
    "areaType": "section",
    "areaRai": 1000,
    "cropType": "rice",
    "cropWeek": 5,
    "calendarWeek": 18,
    "calendarYear": 2024,
    "monthlyETo": 156.0,
    "weeklyETo": 39.0,
    "kcValue": 1.10,
    "percolation": 14,
    "cropWaterDemandMm": 56.9,
    "cropWaterDemandM3": 91040,
    "effectiveRainfall": 5.2,
    "waterLevel": 221.5,
    "netWaterDemandMm": 51.7,
    "netWaterDemandM3": 82720
  }
}
```

#### Calculate Seasonal Water Demand
```http
POST /demand/seasonal
Content-Type: application/json

{
  "areaId": "Z1-S1",
  "areaType": "section",
  "areaRai": 1000,
  "cropType": "rice",
  "plantingDate": "2024-05-01",
  "includeRainfall": true
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "areaId": "Z1-S1",
    "areaType": "section",
    "areaRai": 1000,
    "cropType": "rice",
    "totalCropWeeks": 16,
    "plantingDate": "2024-05-01",
    "harvestDate": "2024-08-21",
    "totalWaterDemandMm": 910.4,
    "totalWaterDemandM3": 1456640,
    "totalEffectiveRainfall": 245.6,
    "totalNetWaterDemandMm": 664.8,
    "totalNetWaterDemandM3": 1063680,
    "weeklyDetails": [...]
  }
}
```

### 4. Area Management

#### Create Area
```http
POST /areas
Content-Type: application/json

{
  "areaId": "Z1-S1",
  "areaType": "section",
  "areaName": "Zone 1 Section 1",
  "totalAreaRai": 1000,
  "parentAreaId": "Z1",
  "aosStation": "นครราชสีมา",
  "province": "นครราชสีมา"
}
```

#### Get Area by ID
```http
GET /areas/Z1-S1
```

#### Get Areas by Type
```http
GET /areas/type/section
```

#### Get Area Hierarchy
```http
GET /areas/hierarchy/PROJECT-01
```

**Response**:
```json
{
  "success": true,
  "data": {
    "areaId": "PROJECT-01",
    "areaType": "project",
    "areaName": "Munbon Irrigation Project",
    "totalAreaRai": 50000,
    "zones": [
      {
        "areaId": "Z1",
        "areaType": "zone",
        "areaName": "Zone 1",
        "totalAreaRai": 15000,
        "sections": [
          {
            "areaId": "Z1-S1",
            "areaType": "section",
            "areaName": "Zone 1 Section 1",
            "totalAreaRai": 5000
          }
        ]
      }
    ]
  }
}
```

#### Import Multiple Areas
```http
POST /areas/import
Content-Type: application/json

{
  "areas": [
    {
      "areaId": "Z1",
      "areaType": "zone",
      "areaName": "Zone 1",
      "totalAreaRai": 15000,
      "parentAreaId": "PROJECT-01"
    },
    {
      "areaId": "Z1-S1",
      "areaType": "section",
      "areaName": "Zone 1 Section 1",
      "totalAreaRai": 5000,
      "parentAreaId": "Z1"
    }
  ]
}
```

#### Get Area Statistics
```http
GET /areas/statistics
```

**Response**:
```json
{
  "success": true,
  "data": {
    "totalProjects": 1,
    "totalZones": 6,
    "totalSections": 24,
    "totalAreaRai": 50000
  }
}
```

### 5. Rainfall Data Management

#### Add Rainfall Data
```http
POST /rainfall
Content-Type: application/json

{
  "areaId": "Z1-S1",
  "date": "2024-05-01",
  "rainfallMm": 25.4,
  "effectiveRainfallMm": 20.3,
  "source": "weather_api"
}
```

#### Get Weekly Effective Rainfall
```http
GET /rainfall/weekly/Z1-S1?weekStartDate=2024-05-01
```

#### Get Rainfall History
```http
GET /rainfall/history/Z1-S1?startDate=2024-01-01&endDate=2024-12-31
```

#### Get Rainfall Statistics
```http
GET /rainfall/statistics/Z1-S1?year=2024&month=5
```

### 6. Water Level Monitoring

#### Add Water Level Measurement
```http
POST /water-level
Content-Type: application/json

{
  "areaId": "Z1-S1",
  "measurementDate": "2024-05-01",
  "measurementTime": "08:00",
  "waterLevelM": 221.5,
  "referenceLevel": "MSL",
  "source": "sensor",
  "sensorId": "WL-001"
}
```

#### Get Current Water Level
```http
GET /water-level/current/Z1-S1
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": 123,
    "areaId": "Z1-S1",
    "measurementDate": "2024-05-01",
    "measurementTime": "08:00:00",
    "waterLevelM": 221.5,
    "referenceLevel": "MSL",
    "source": "sensor",
    "sensorId": "WL-001"
  }
}
```

#### Get Water Level History
```http
GET /water-level/history/Z1-S1?startDate=2024-01-01&endDate=2024-12-31&source=sensor
```

#### Get Water Level Trends
```http
GET /water-level/trends/Z1-S1?days=30
```

### 7. Crop Calendar Management

#### Create Crop Calendar Entry
```http
POST /calendar
Content-Type: application/json

{
  "areaId": "Z1-S1",
  "areaType": "section",
  "cropType": "rice",
  "plantingDate": "2024-05-01",
  "season": "wet",
  "year": 2024
}
```

#### Get Crop Calendar by Area
```http
GET /calendar/area/Z1-S1?year=2024
```

#### Get Active Crops
```http
GET /calendar/active?date=2024-06-15
```

### 8. Irrigation Scheduling

#### Create Irrigation Schedule
```http
POST /schedule
Content-Type: application/json

{
  "areaId": "Z1-S1",
  "cropType": "rice",
  "startDate": "2024-05-01",
  "endDate": "2024-08-21",
  "frequency": "weekly"
}
```

#### Get Schedules by Area
```http
GET /schedule/area/Z1-S1?status=active
```

#### Get Weekly Schedule
```http
GET /schedule/weekly?week=18&year=2024
```

## Error Responses

All endpoints follow a consistent error response format:

```json
{
  "success": false,
  "error": "Error message",
  "message": "Detailed error description"
}
```

### Common Error Codes:
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (missing or invalid token)
- `404` - Not Found (resource not found)
- `409` - Conflict (duplicate resource)
- `500` - Internal Server Error

## Data Formats

### Date Formats
- Dates: ISO 8601 format (YYYY-MM-DD)
- Time: 24-hour format (HH:MM)

### Numeric Values
- Area: in rai (ไร่)
- Water demand: mm (millimeters) or m³ (cubic meters)
- Water level: m (meters)
- ETo/Rainfall: mm (millimeters)

### Enumerations

**Area Types**: 
- `project` - Project level
- `zone` - Zone level
- `section` - Section level
- `FTO` - Field Turnout level

**Crop Types**:
- `rice` - Rice (16 weeks)
- `corn` - Corn (16 weeks)
- `sugarcane` - Sugarcane (52 weeks)

**Data Sources**:
- `manual` - Manual entry
- `sensor` - Sensor data
- `weather_api` - Weather API
- `scada` - SCADA system

## Notes

1. **Water Demand Calculation Formula**:
   - Weekly Water Demand (mm) = (Weekly ETo × Kc) + Percolation (14 mm)
   - Water Demand (m³) = Water Demand (mm) × Area (rai) × 1.6

2. **Effective Rainfall**:
   - Automatically fetched from rainfall data if not provided
   - Net water demand = Crop water demand - Effective rainfall

3. **Water Level Integration**:
   - Current water level is automatically included in demand calculations
   - Used for determining water availability

4. **Excel Import**:
   - Supports both English and Thai column headers
   - Templates available for download
   - Validates data before import