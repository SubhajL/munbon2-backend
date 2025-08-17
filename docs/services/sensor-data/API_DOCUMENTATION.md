# Sensor Data Service API Documentation

## Overview
The Sensor Data Service provides REST API endpoints for accessing water level and moisture sensor data from the Munbon Irrigation Project. The API supports real-time data access, historical queries, aggregations, and external system integration.

## Base URLs
- Development: `http://localhost:3001`
- Production: `https://api.munbon.th`

## API Documentation
Interactive API documentation is available at:
- Development: `http://localhost:3001/api-docs`
- Production: `https://api.munbon.th/api-docs`

## Authentication
- **Internal APIs**: No authentication required for development. Production will use JWT tokens.
- **External APIs** (RID-MS): Require API key in `X-API-Key` header

## API Endpoints

### Sensor Management
- `GET /api/v1/sensors` - List all sensors with pagination and filters
- `GET /api/v1/sensors/:sensorId` - Get specific sensor details
- `GET /api/v1/sensors/:sensorId/readings` - Get sensor readings with time range
- `GET /api/v1/sensors/:sensorId/latest` - Get latest reading for a sensor
- `GET /api/v1/sensors/:sensorId/statistics` - Get statistics for a sensor
- `PATCH /api/v1/sensors/:sensorId` - Update sensor configuration

### Water Level Data
- `GET /api/v1/water-levels` - Get water level readings with filters
- `GET /api/v1/water-levels/aggregated` - Get aggregated water level data
- `GET /api/v1/water-levels/alerts` - Get water level alerts/anomalies
- `GET /api/v1/water-levels/comparison` - Compare water levels between sensors

### Moisture Data
- `GET /api/v1/moisture` - Get moisture readings with filters
- `GET /api/v1/moisture/aggregated` - Get aggregated moisture data
- `GET /api/v1/moisture/alerts` - Get moisture alerts
- `GET /api/v1/moisture/flood-history` - Get flood event history

### External System Integration (RID-MS)
- `GET /api/v1/external/rid-ms/sensors` - Get sensors in RID-MS format
- `GET /api/v1/external/rid-ms/readings` - Get readings in RID-MS format
- `GET /api/v1/external/rid-ms/spatial` - Get spatial data as GeoJSON
- `POST /api/v1/external/rid-ms/webhooks` - Register webhook for updates

### Real-time Data
- WebSocket endpoint: `ws://localhost:3001` (or `wss://api.munbon.th` for production)
- MQTT broker: Port 1883 (TCP) or 8083 (WebSocket)

## Common Query Parameters

### Pagination
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 20-100 depending on endpoint)

### Time Range
- `start` - Start time (ISO 8601 format)
- `end` - End time (ISO 8601 format)

### Aggregation
- `interval` - Time bucket interval (e.g., '1h', '1d', '1w')
- `aggregation` - Aggregation method (avg, min, max, sum, count)

## Response Format

### Success Response
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "totalPages": 5
  }
}
```

### Error Response
```json
{
  "error": "Error message",
  "statusCode": 400
}
```

## Data Models

### Sensor
```json
{
  "id": "RIDR001",
  "type": "water-level",
  "name": "Water Level Sensor 1",
  "manufacturer": "RID-R",
  "location": {
    "lat": 13.7563,
    "lng": 100.5018
  },
  "isActive": true,
  "lastSeen": "2024-01-15T10:30:00Z",
  "metadata": {},
  "totalReadings": 1234
}
```

### Water Level Reading
```json
{
  "sensorId": "RIDR001",
  "timestamp": "2024-01-15T10:30:00Z",
  "levelCm": 15.5,
  "voltage": 3.85,
  "rssi": -65,
  "location": {
    "lat": 13.7563,
    "lng": 100.5018
  },
  "qualityScore": 0.95
}
```

### Moisture Reading
```json
{
  "sensorId": "00001-00001",
  "timestamp": "2024-01-15T10:30:00Z",
  "moistureSurfacePct": 45,
  "moistureDeepPct": 58,
  "tempSurfaceC": 28.5,
  "tempDeepC": 27.0,
  "ambientHumidityPct": 65,
  "ambientTempC": 32.5,
  "floodStatus": false,
  "voltage": 3.9,
  "qualityScore": 1.0
}
```

## WebSocket Events

### Subscribe to sensor data
```javascript
socket.emit('subscribe', ['sensor:RIDR001', 'sensorType:water-level']);
```

### Receive sensor data
```javascript
socket.on('sensorData', (data) => {
  console.log('New sensor data:', data);
});
```

### Receive alerts
```javascript
socket.on('alert', (alert) => {
  console.log('Alert:', alert);
});
```

## MQTT Topics

### Sensor Data
- `sensors/water-level/{sensorId}/data`
- `sensors/moisture/{sensorId}/data`

### Location Updates
- `sensors/water-level/{sensorId}/location`
- `sensors/moisture/{sensorId}/location`

### Alerts
- `alerts/critical/{alertType}`
- `alerts/warning/{alertType}`

## Rate Limiting
- Development: No rate limiting
- Production: 100 requests per minute per IP

## Examples

### Get latest water level readings
```bash
curl "http://localhost:3001/api/v1/water-levels?limit=10&sortOrder=desc"
```

### Get aggregated moisture data for last 7 days
```bash
curl "http://localhost:3001/api/v1/moisture/aggregated?interval=1d&layer=both"
```

### Get sensors near a location
```bash
curl "http://localhost:3001/api/v1/sensors/nearby?lat=13.7563&lng=100.5018&radius=5"
```

### External system access (RID-MS)
```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:3001/api/v1/external/rid-ms/sensors?type=water-level"
```