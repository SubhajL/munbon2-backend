# Water Level-Based Irrigation Control API Documentation

## Overview
The new water level-based irrigation control system provides real-time monitoring and intelligent control of irrigation based on actual sensor feedback, replacing the previous time-based estimation approach.

## Base URL
```
http://localhost:3013/api/v1/awd
```

## Authentication
All endpoints require JWT authentication token in the Authorization header:
```
Authorization: Bearer <token>
```

## API Endpoints

### 1. Irrigation Control

#### Start Irrigation
**POST** `/control/fields/:fieldId/irrigation/start`

Start irrigation with water level-based control and real-time monitoring.

**Parameters:**
- `fieldId` (path, UUID, required): Field identifier

**Request Body:**
```json
{
  "targetLevelCm": 10,           // Required: Target water level (1-20cm)
  "toleranceCm": 1.0,            // Optional: Tolerance for target level (0.1-2cm)
  "maxDurationHours": 24,        // Optional: Maximum duration (1-48 hours)
  "emergencyStopLevel": 15       // Optional: Emergency stop level (10-25cm)
}
```

**Response:**
```json
{
  "success": true,
  "scheduleId": "123e4567-e89b-12d3-a456-426614174000",
  "status": {
    "scheduleId": "123e4567-e89b-12d3-a456-426614174000",
    "fieldId": "field-123",
    "status": "active",
    "startTime": "2024-01-15T08:00:00Z",
    "currentLevelCm": 2.5,
    "targetLevelCm": 10,
    "flowRateCmPerMin": 0,
    "anomaliesDetected": 0
  },
  "method": "water_level_based",
  "prediction": {
    "duration": 360,
    "flowRate": 0.028,
    "waterVolume": 75000,
    "confidence": 0.85,
    "basedOnSamples": 15
  },
  "recommendation": {
    "startTime": "2024-01-15T06:00:00Z",
    "confidence": 0.9
  }
}
```

#### Get Irrigation Status
**GET** `/control/fields/:fieldId/irrigation/status`

Get real-time irrigation status with monitoring data.

**Query Parameters:**
- `includeHistory` (boolean, optional): Include historical patterns

**Response:**
```json
{
  "active": true,
  "scheduleId": "123e4567-e89b-12d3-a456-426614174000",
  "fieldId": "field-123",
  "status": "active",
  "startTime": "2024-01-15T08:00:00Z",
  "currentLevelCm": 5.8,
  "targetLevelCm": 10,
  "flowRateCmPerMin": 0.027,
  "estimatedCompletionTime": "2024-01-15T10:35:00Z",
  "anomaliesDetected": 0,
  "currentWaterLevel": 5.8,
  "currentPhase": "wetting",
  "patterns": [
    {
      "pattern": "time_dependent_efficiency",
      "description": "Best performance at 6:00, worst at 14:00",
      "frequency": 45,
      "impact": "positive",
      "recommendations": [
        "Schedule irrigations around 6:00 for best efficiency"
      ]
    }
  ]
}
```

#### Stop Irrigation
**POST** `/control/fields/:fieldId/irrigation/stop`

Stop active irrigation with reason.

**Request Body:**
```json
{
  "reason": "Manual stop - field inspection needed"
}
```

**Response:**
```json
{
  "success": true,
  "scheduleId": "123e4567-e89b-12d3-a456-426614174000",
  "reason": "Manual stop - field inspection needed"
}
```

### 2. Predictions and Recommendations

#### Get Irrigation Recommendation
**GET** `/control/fields/:fieldId/irrigation/recommendation`

Get AI-based irrigation recommendations.

**Query Parameters:**
- `targetLevel` (number, optional): Target water level (default: 10cm)

**Response:**
```json
{
  "estimatedDuration": 240,
  "recommendedStartTime": "2024-01-16T06:00:00Z",
  "expectedFlowRate": 0.025,
  "confidence": 0.87
}
```

#### Predict Irrigation Performance
**POST** `/control/fields/:fieldId/irrigation/predict`

Predict irrigation performance based on conditions.

**Request Body:**
```json
{
  "initialLevel": 2.5,
  "targetLevel": 10,
  "temperature": 28,
  "humidity": 65,
  "soilType": "clay",
  "lastIrrigationDays": 5,
  "season": "dry"
}
```

**Response:**
```json
{
  "fieldId": "field-123",
  "conditions": {
    "initialLevel": 2.5,
    "targetLevel": 10,
    "soilType": "clay",
    "temperature": 28,
    "humidity": 65,
    "lastIrrigationDays": 5,
    "concurrentIrrigations": 2,
    "season": "dry"
  },
  "predictions": {
    "estimatedDuration": 420,
    "expectedFlowRate": 0.018,
    "waterVolume": 75000,
    "confidenceLevel": 0.82,
    "confidenceIntervalLower": 360,
    "confidenceIntervalUpper": 480
  },
  "modelVersion": "1.0.0",
  "basedOnSamples": 23
}
```

### 3. Analytics

#### Get Performance Analytics
**GET** `/control/fields/:fieldId/irrigation/analytics`

Get irrigation performance analytics and insights.

**Query Parameters:**
- `days` (number, optional): Number of days to analyze (1-365, default: 30)

**Response:**
```json
{
  "fieldId": "field-123",
  "period": "Last 30 days",
  "patterns": [
    {
      "pattern": "high_flow_variability",
      "description": "Flow rate varies significantly between irrigations",
      "frequency": 15,
      "impact": "negative",
      "recommendations": [
        "Check for partial gate blockages",
        "Verify water pressure consistency"
      ]
    }
  ],
  "optimalParameters": {
    "sensorCheckInterval": 300,
    "minFlowRateThreshold": 0.02,
    "maxDurationMinutes": 480,
    "toleranceCm": 0.5
  },
  "insights": [
    "High flow rate variability detected - consider maintenance",
    "Tight tolerance recommended due to past anomalies"
  ]
}
```

### 4. Monitoring Dashboard

#### Get Real-time Monitoring Data
**GET** `/monitoring/irrigation/:scheduleId/realtime`

Get real-time sensor readings for active irrigation.

**Query Parameters:**
- `limit` (number, optional): Number of data points (1-1000, default: 100)

**Response:**
```json
{
  "scheduleId": "123e4567-e89b-12d3-a456-426614174000",
  "dataPoints": [
    {
      "timestamp": "2024-01-15T08:05:00Z",
      "water_level_cm": 2.8,
      "flow_rate_cm_per_min": 0.025,
      "sensor_id": "SENSOR-001",
      "sensor_reliability": 0.95
    }
  ],
  "count": 100
}
```

#### Get Field Performance Summary
**GET** `/monitoring/fields/:fieldId/performance`

Get comprehensive performance metrics for a field.

**Query Parameters:**
- `days` (number, optional): Analysis period (1-365, default: 30)

**Response:**
```json
{
  "fieldId": "field-123",
  "period": "30 days",
  "summary": {
    "totalIrrigations": 15,
    "avgEfficiency": "0.85",
    "avgDurationHours": "5.2",
    "avgWaterVolume": 68000,
    "totalWaterUsed": 1020000,
    "avgWaterSaved": "22.5",
    "highEfficiencyRate": "73.3",
    "totalAnomalies": 3
  },
  "anomalies": [
    {
      "anomaly_type": "low_flow",
      "severity": "warning",
      "count": 2
    }
  ],
  "trend": [
    {
      "date": "2024-01-01",
      "efficiency": "0.82",
      "avgDurationHours": "5.5",
      "count": 2
    }
  ]
}
```

#### Get Anomaly Details
**GET** `/monitoring/anomalies`

Get detailed anomaly information with filtering.

**Query Parameters:**
- `fieldId` (UUID, optional): Filter by field
- `type` (string, optional): Anomaly type (low_flow, no_rise, rapid_drop, sensor_failure, overflow_risk)
- `severity` (string, optional): Severity level (warning, critical)
- `resolved` (boolean, optional): Filter by resolution status
- `days` (number, optional): Time period (default: 7)
- `limit` (number, optional): Results per page (default: 50)
- `offset` (number, optional): Pagination offset

**Response:**
```json
{
  "anomalies": [
    {
      "id": "anomaly-123",
      "schedule_id": "schedule-456",
      "field_id": "field-123",
      "field_name": "Rice Field A",
      "detected_at": "2024-01-15T09:30:00Z",
      "anomaly_type": "low_flow",
      "severity": "warning",
      "description": "Flow rate (0.015 cm/min) below minimum",
      "metrics": {
        "flowRate": 0.015,
        "threshold": 0.05
      },
      "resolution_action": "increase_gate_opening",
      "resolved_at": "2024-01-15T09:35:00Z",
      "irrigation_start": "2024-01-15T08:00:00Z"
    }
  ],
  "pagination": {
    "total": 23,
    "limit": 50,
    "offset": 0,
    "hasMore": false
  },
  "filters": {
    "days": 7,
    "severity": "warning"
  }
}
```

#### Get Water Usage Analytics
**GET** `/monitoring/water-usage`

Get water usage analytics grouped by various dimensions.

**Query Parameters:**
- `groupBy` (string, optional): Grouping dimension (field, day, week, month)
- `days` (number, optional): Analysis period (default: 30)

**Response:**
```json
{
  "data": [
    {
      "period": "2024-01-15",
      "irrigation_count": 3,
      "total_water": 210000,
      "avg_water": 70000,
      "avg_efficiency": "0.86",
      "fields_irrigated": 2
    }
  ],
  "summary": {
    "period": "30 days",
    "groupBy": "day",
    "totalWaterUsed": 3150000,
    "totalIrrigations": 45,
    "avgEfficiency": "0.84"
  }
}
```

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "errors": [
    {
      "type": "field",
      "msg": "Invalid field ID",
      "path": "fieldId",
      "location": "params"
    }
  ]
}
```

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "message": "Invalid or missing authentication token"
}
```

### 409 Conflict
```json
{
  "success": false,
  "reason": "Field AWD control not active",
  "decision": {
    "fieldId": "field-123",
    "action": "maintain",
    "reason": "Field AWD control not active"
  }
}
```

### 500 Internal Server Error
```json
{
  "error": "Failed to start irrigation",
  "message": "Internal server error"
}
```

## Webhook Events

The system publishes events via Kafka for real-time updates:

### irrigation_started
```json
{
  "type": "irrigation_started",
  "fieldId": "field-123",
  "scheduleId": "schedule-456",
  "targetLevel": 10,
  "estimatedDuration": 360,
  "method": "water_level_based",
  "timestamp": "2024-01-15T08:00:00Z"
}
```

### irrigation_anomaly
```json
{
  "type": "irrigation_anomaly",
  "scheduleId": "schedule-456",
  "fieldId": "field-123",
  "anomaly": {
    "type": "low_flow",
    "severity": "warning",
    "description": "Flow rate below minimum threshold"
  },
  "timestamp": "2024-01-15T09:30:00Z"
}
```

### irrigation_completed
```json
{
  "type": "irrigation_completed",
  "fieldId": "field-123",
  "scheduleId": "schedule-456",
  "achievedLevel": 9.8,
  "totalDuration": 355,
  "waterVolume": 73500,
  "efficiency": 0.88,
  "timestamp": "2024-01-15T13:55:00Z"
}
```

## Rate Limiting

- 100 requests per minute per API key
- 1000 requests per hour per API key
- Monitoring endpoints: 300 requests per minute

## Best Practices

1. **Sensor Check Intervals**: Use 5-minute intervals for most fields, 3-minute for quick irrigations
2. **Tolerance Settings**: Use 1.0cm for normal conditions, 0.5cm for precision irrigation
3. **Emergency Stop Levels**: Set 5cm above target level to prevent overflow
4. **Monitoring**: Always monitor active irrigations via real-time endpoints
5. **Error Handling**: Implement exponential backoff for failed requests
6. **Webhooks**: Subscribe to Kafka topics for real-time updates instead of polling