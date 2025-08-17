# ROS Service API Documentation

## Base URL
```
http://localhost:3047/api/v1/ros
```

## Authentication
All endpoints require JWT authentication token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### 1. Calculate Water Demand
Calculate water demand for given crop and planting data.

**Endpoint:** `POST /calculate`

**Request Body:**
```json
{
  "cropType": "ข้าว กข.(นาดำ)",
  "plantings": [
    {
      "plantingDate": "2024-11-01",
      "areaRai": 1000,
      "growthDays": 45  // Optional, calculated if not provided
    }
  ],
  "calculationDate": "2024-12-15",
  "calculationPeriod": "daily",  // "daily" | "weekly" | "monthly"
  "nonAgriculturalDemands": {    // Optional
    "domestic": 5000,
    "industrial": 2000,
    "ecosystem": 1000,
    "other": 500
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "waterRequirement": {
      "etc": 4.6,
      "percolation": 2.0,
      "total_mm": 6.6,
      "total_m3": 10560
    },
    "effectiveRainfall": {
      "amount_mm": 2.0,
      "amount_m3": 3200
    },
    "netIrrigation": {
      "amount_mm": 4.6,
      "amount_m3": 7360
    },
    "cropDetails": {
      "totalAreaRai": 1000,
      "weightedKc": 1.15,
      "et0": 4.0,
      "activeGrowthStages": [
        {
          "plantingId": "2024-11-01T00:00:00.000Z_1000",
          "growthWeek": 7,
          "kc": 1.15,
          "areaRai": 1000,
          "growthStage": "development"
        }
      ]
    },
    "nonAgriculturalDemand_m3": 8500,
    "totalWaterDemand_m3": 15860,
    "calculationDate": "2024-12-15T00:00:00.000Z",
    "calculationPeriod": "daily",
    "calculationMethod": "Excel-based lookup tables"
  },
  "timestamp": "2024-12-15T10:30:00.000Z"
}
```

### 2. Batch Calculate
Calculate water demand for multiple scenarios.

**Endpoint:** `POST /calculate/batch`

**Request Body:**
```json
{
  "scenarios": [
    {
      "cropType": "ข้าว กข.(นาดำ)",
      "plantings": [...],
      "calculationDate": "2024-12-15",
      "calculationPeriod": "daily"
    },
    // More scenarios...
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "jobId": "job_123456",
    "status": "queued",
    "scenarioCount": 5
  }
}
```

### 3. Import Kc Data
Import crop coefficient data from Excel file.

**Endpoint:** `POST /data/kc/import`

**Request:** Multipart form data
- `file`: Excel file (.xlsx, .xls)

**Response:**
```json
{
  "success": true,
  "data": {
    "recordsImported": 340,
    "crops": ["ข้าว กข.(นาดำ)", "ข้าวหอมมะลิ", "ข้าวเหนียว"]
  }
}
```

### 4. Get Kc Curve
Get Kc values for all growth stages of a crop.

**Endpoint:** `GET /data/kc/:cropType`

**Response:**
```json
{
  "success": true,
  "data": {
    "cropType": "ข้าว กข.(นาดำ)",
    "curve": [
      {
        "week": 1,
        "kc": 1.10,
        "stage": "Initial"
      },
      {
        "week": 2,
        "kc": 1.10,
        "stage": "Initial"
      },
      // More weeks...
    ]
  }
}
```

### 5. Generate Report
Generate a report for a calculation.

**Endpoint:** `POST /report/generate`

**Request Body:**
```json
{
  "calculationId": "calc_123456",
  "format": "pdf",  // "pdf" | "excel" | "csv"
  "includeCharts": true,
  "includeHistorical": false,
  "language": "th"  // "en" | "th"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "reportId": "report_789012",
    "status": "queued"
  }
}
```

### 6. Download Report
Download a generated report.

**Endpoint:** `GET /report/:reportId/download`

**Response:** Binary file stream with appropriate content type

### 7. Upload Excel File
Upload Excel file for processing (complete ROS calculation).

**Endpoint:** `POST /excel/upload`

**Request:** Multipart form data
- `file`: Excel file (.xlsx, .xlsm)

**Response:**
```json
{
  "success": true,
  "data": {
    "jobId": "job_456789",
    "status": "queued",
    "filename": "คบ.มูลบน_ROS_ฤดูฝน2568.xlsm"
  }
}
```

### 8. Get Processing Status
Check status of Excel processing job.

**Endpoint:** `GET /excel/status/:jobId`

**Response:**
```json
{
  "success": true,
  "data": {
    "jobId": "job_456789",
    "status": "completed",
    "progress": 100,
    "result": {
      "calculationId": "calc_123456",
      "filename": "คบ.มูลบน_ROS_ฤดูฝน2568.xlsm",
      "results": {...}
    }
  }
}
```

### 9. Get Calculation History
Retrieve historical calculations with pagination.

**Endpoint:** `GET /history/calculations`

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Results per page (default: 10, max: 100)
- `startDate`: Filter start date (ISO 8601)
- `endDate`: Filter end date (ISO 8601)
- `cropType`: Filter by crop type

**Response:**
```json
{
  "success": true,
  "data": {
    "calculations": [...],
    "total": 156,
    "page": 1,
    "limit": 10,
    "totalPages": 16
  }
}
```

### 10. Get Available Crops
Get list of available crop types.

**Endpoint:** `GET /crops`

**Response:**
```json
{
  "success": true,
  "data": [
    "ข้าว กข.(นาดำ)",
    "ข้าวหอมมะลิ",
    "ข้าวเหนียว",
    "ข้าวโพด",
    "อ้อย",
    "มันสำปะหลัง"
  ]
}
```

## Error Responses

### Validation Error (400)
```json
{
  "success": false,
  "error": {
    "message": "Validation error: Crop type is required"
  },
  "timestamp": "2024-12-15T10:30:00.000Z"
}
```

### Not Found (404)
```json
{
  "success": false,
  "error": {
    "message": "Calculation not found"
  },
  "timestamp": "2024-12-15T10:30:00.000Z"
}
```

### Rate Limit (429)
```json
{
  "success": false,
  "error": {
    "message": "Too many requests, please try again later.",
    "retryAfter": "2024-12-15T10:35:00.000Z"
  }
}
```

### Server Error (500)
```json
{
  "success": false,
  "error": {
    "message": "Internal server error"
  },
  "timestamp": "2024-12-15T10:30:00.000Z"
}
```

## Rate Limits
- General endpoints: 100 requests per 15 minutes
- File uploads: 10 requests per 15 minutes
- Calculations: 20 requests per 5 minutes

## File Size Limits
- Maximum file size: 50MB
- Allowed formats: .xlsx, .xls, .csv, .xlsm