# Munbon External API Documentation

## Overview
This API provides access to water level, soil moisture, and meteorological (AOS) data from the Munbon Irrigation System. The API uses Buddhist calendar dates (BE) for all date parameters.

## Base URL
```
https://munbon-api.YOUR_DOMAIN.com/api/v1/public
```

## Authentication
All endpoints require API key authentication via the `X-API-Key` header:
```
X-API-Key: your-api-key-here
```

## Date Format
All dates use Buddhist calendar format: `DD/MM/YYYY`
- Example: `10/06/2568` (10th June 2025 CE)
- Buddhist Era (BE) = Common Era (CE) + 543

## Endpoints

### Water Level Data

#### 1. Get Water Level Time Series
```
GET /water-levels/timeseries?date=DD/MM/YYYY
```

Returns all water level readings for all sensors on the specified date.

**Parameters:**
- `date` (required): Date in Buddhist calendar format

**Response:**
```json
{
  "data_type": "water_level",
  "request_date": "10/06/2568",
  "sensor_count": 5,
  "sensors": [
    {
      "sensor_id": "wl001",
      "sensor_name": "Water Level Sensor 1",
      "location": {...},
      "zone": "Zone 1",
      "date_buddhist": "10/06/2568",
      "readings": [
        {
          "timestamp": "2025-06-10T00:00:00Z",
          "water_level_m": 12.5,
          "flow_rate_m3s": 1.2,
          "quality": 100
        }
      ]
    }
  ]
}
```

#### 2. Get Latest Water Level
```
GET /water-levels/latest
```

Returns the most recent water level reading for all active sensors.

**Response:**
```json
{
  "data_type": "water_level",
  "request_time": "2025-06-10T15:30:00Z",
  "request_time_buddhist": "10/06/2568",
  "sensor_count": 5,
  "sensors": [
    {
      "sensor_id": "wl001",
      "sensor_name": "Water Level Sensor 1",
      "location": {...},
      "zone": "Zone 1",
      "latest_reading": {
        "timestamp": "2025-06-10T15:00:00Z",
        "timestamp_buddhist": "10/06/2568",
        "water_level_m": 12.5,
        "flow_rate_m3s": 1.2,
        "quality": 100
      }
    }
  ]
}
```

#### 3. Get Water Level Statistics
```
GET /water-levels/statistics?date=DD/MM/YYYY
```

Returns statistical summary of water level data for the specified date.

**Parameters:**
- `date` (required): Date in Buddhist calendar format

**Response:**
```json
{
  "data_type": "water_level",
  "request_date": "10/06/2568",
  "sensor_count": 5,
  "sensors": [
    {
      "sensor_id": "wl001",
      "sensor_name": "Water Level Sensor 1",
      "location": {...},
      "zone": "Zone 1",
      "date_buddhist": "10/06/2568",
      "statistics": {
        "count": 1440,
        "min": 10.2,
        "max": 15.8,
        "avg": 12.5,
        "stddev": 1.2
      }
    }
  ]
}
```

### Moisture Data

#### 1. Get Moisture Time Series
```
GET /moisture/timeseries?date=DD/MM/YYYY
```

Returns all moisture readings for all sensors on the specified date.

**Parameters:**
- `date` (required): Date in Buddhist calendar format

**Response:**
```json
{
  "data_type": "moisture",
  "request_date": "10/06/2568",
  "sensor_count": 10,
  "sensors": [
    {
      "sensor_id": "m001",
      "sensor_name": "Moisture Sensor 1",
      "location": {...},
      "zone": "Zone 1",
      "date_buddhist": "10/06/2568",
      "readings": [
        {
          "timestamp": "2025-06-10T00:00:00Z",
          "moisture_percentage": 65.5,
          "temperature_celsius": 28.3,
          "quality": 100
        }
      ]
    }
  ]
}
```

#### 2. Get Latest Moisture
```
GET /moisture/latest
```

Returns the most recent moisture reading for all active sensors.

#### 3. Get Moisture Statistics
```
GET /moisture/statistics?date=DD/MM/YYYY
```

Returns statistical summary of moisture data for the specified date.

### AOS (Meteorological) Data

#### 1. Get AOS Time Series
```
GET /aos/timeseries?date=DD/MM/YYYY
```

Returns all meteorological readings for all stations on the specified date.

**Parameters:**
- `date` (required): Date in Buddhist calendar format

**Response:**
```json
{
  "data_type": "aos_meteorological",
  "request_date": "10/06/2568",
  "station_count": 3,
  "stations": [
    {
      "station_id": "aos001",
      "station_name": "AOS Station 1",
      "location": {...},
      "zone": "Zone 1",
      "date_buddhist": "10/06/2568",
      "readings": [
        {
          "timestamp": "2025-06-10T00:00:00Z",
          "rainfall_mm": 2.5,
          "temperature_celsius": 28.5,
          "humidity_percentage": 75,
          "wind_speed_ms": 3.2,
          "wind_direction_degrees": 180,
          "pressure_hpa": 1013.25
        }
      ]
    }
  ]
}
```

#### 2. Get Latest AOS Data
```
GET /aos/latest
```

Returns the most recent meteorological reading for all active stations.

#### 3. Get AOS Statistics
```
GET /aos/statistics?date=DD/MM/YYYY
```

Returns statistical summary of meteorological data for the specified date.

**Response includes:**
- Total rainfall for the day
- Temperature min/max/average
- Average humidity, wind speed, and pressure

## Error Responses

### 401 Unauthorized
```json
{
  "error": "Invalid API key"
}
```

### 400 Bad Request
```json
{
  "error": "Date parameter is required (dd/mm/yyyy in Buddhist calendar)"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "message": "Error details..."
}
```

## Rate Limiting
- Default: 1000 requests per hour per API key
- Burst: 100 requests per minute

## Example Usage

### cURL
```bash
# Get latest water level data
curl -H "X-API-Key: your-api-key" \
  https://munbon-api.example.com/api/v1/public/water-levels/latest

# Get moisture data for specific date
curl -H "X-API-Key: your-api-key" \
  "https://munbon-api.example.com/api/v1/public/moisture/timeseries?date=10/06/2568"
```

### Python
```python
import requests

headers = {"X-API-Key": "your-api-key"}
base_url = "https://munbon-api.example.com/api/v1/public"

# Get water level statistics
response = requests.get(
    f"{base_url}/water-levels/statistics",
    params={"date": "10/06/2568"},
    headers=headers
)
data = response.json()
```

### JavaScript
```javascript
const headers = { 'X-API-Key': 'your-api-key' };
const baseUrl = 'https://munbon-api.example.com/api/v1/public';

// Get latest AOS data
fetch(`${baseUrl}/aos/latest`, { headers })
  .then(res => res.json())
  .then(data => console.log(data));
```

## Data Update Frequency
- Water Level: Every 1 minute
- Moisture: Every 5 minutes  
- AOS/Weather: Every 10 minutes

## Support
For API support or to request additional API keys, contact:
- Email: support@munbon-irrigation.th
- Phone: +66 XX XXX XXXX