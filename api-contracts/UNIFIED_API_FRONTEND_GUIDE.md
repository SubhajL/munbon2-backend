# Munbon Unified API - Frontend Developer Guide

## Overview

The Munbon Unified API provides access to sensor data from the irrigation system. This API aggregates data from multiple sources:
- **Water Level Sensors** - Real-time water levels in canals
- **Moisture Sensors** - Soil moisture monitoring
- **AOS Weather Stations** - Meteorological data

## Base URL

```
https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com
```

## Authentication

All API requests (except `/health`) require an API key in the header:

```javascript
headers: {
  'x-api-key': 'your-api-key-here'
}
```

## Important Notes

### Buddhist Calendar
- All dates in requests must use Buddhist calendar format: `DD/MM/YYYY` (e.g., `08/07/2568`)
- Response timestamps include both ISO format and Buddhist format

### Response Format
All successful responses follow this structure:
```json
{
  "data_type": "water_level|moisture|aos_meteorological",
  "request_time": "2025-07-08T10:30:00Z",
  "request_time_buddhist": "08/07/2568",
  "sensor_count": 3,
  "sensors": [...]
}
```

## Endpoints

### 1. Water Level Sensors

#### Get Latest Readings
```http
GET /api/v1/sensors/water-level/latest
```

**Response Example:**
```json
{
  "data_type": "water_level",
  "request_time": "2025-07-08T10:30:00Z",
  "request_time_buddhist": "08/07/2568",
  "sensor_count": 3,
  "sensors": [
    {
      "sensor_id": "WL001",
      "sensor_name": "Water Level Station 1",
      "location": {
        "latitude": 14.4512,
        "longitude": 102.1234
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-07-08T10:25:00Z",
        "timestamp_buddhist": "08/07/2568",
        "water_level_m": 2.45,
        "flow_rate_m3s": 0,
        "quality": 95
      }
    }
  ]
}
```

#### Get Time Series Data
```http
GET /api/v1/sensors/water-level/timeseries?date=08/07/2568
```

**Query Parameters:**
- `date` (required) - Date in Buddhist format DD/MM/YYYY

**Response:** Array of readings for each sensor throughout the day

#### Get Statistics
```http
GET /api/v1/sensors/water-level/statistics?date=08/07/2568
```

**Response:** Statistical summary (min, max, avg, stddev) for the day

### 2. Moisture Sensors

#### Get Latest Readings
```http
GET /api/v1/sensors/moisture/latest
```

**Response Example:**
```json
{
  "data_type": "moisture",
  "request_time": "2025-07-08T10:30:00Z",
  "request_time_buddhist": "08/07/2568",
  "sensor_count": 2,
  "sensors": [
    {
      "sensor_id": "MS001",
      "sensor_name": "Moisture Sensor Field 1",
      "location": {
        "latitude": 14.4612,
        "longitude": 102.1334
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-07-08T10:20:00Z",
        "timestamp_buddhist": "08/07/2568",
        "moisture_percentage": 65.5,
        "temperature_celsius": 28.3,
        "quality": 98
      }
    }
  ]
}
```

#### Get Time Series Data
```http
GET /api/v1/sensors/moisture/timeseries?date=08/07/2568
```

### 3. AOS Weather Stations

#### Get Latest Data
```http
GET /api/v1/sensors/aos/latest
```

**Response Example:**
```json
{
  "data_type": "aos_meteorological",
  "request_time": "2025-07-08T10:30:00Z",
  "request_time_buddhist": "08/07/2568",
  "station_count": 1,
  "stations": [
    {
      "station_id": "AOS001",
      "station_name": "Munbon AOS Weather Station",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-07-08T10:00:00Z",
        "timestamp_buddhist": "08/07/2568",
        "rainfall_mm": 0,
        "temperature_celsius": 32.5,
        "humidity_percentage": 75,
        "wind_speed_ms": 2.5,
        "wind_max_ms": 4.2,
        "wind_direction_degrees": 180,
        "solar_radiation_wm2": 850,
        "battery_voltage": 12.8,
        "pressure_hpa": 1013
      }
    }
  ]
}
```

#### Get Time Series Data
```http
GET /api/v1/sensors/aos/timeseries?date=08/07/2568
```

#### Get Statistics
```http
GET /api/v1/sensors/aos/statistics?date=08/07/2568
```

**Response includes statistics for:**
- Rainfall (min, max, avg, total)
- Temperature (min, max, avg, stddev)
- Wind speed (min, max, avg, max_gust)
- Solar radiation
- Battery voltage

### 4. Health Check

```http
GET /health
```

No authentication required. Returns:
```json
{
  "status": "ok",
  "service": "unified-api",
  "timestamp": "2025-07-08T10:30:00Z"
}
```

## Frontend Implementation Examples

### React/Axios Example

```javascript
import axios from 'axios';

const API_BASE = 'https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com';
const API_KEY = 'your-api-key';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'x-api-key': API_KEY
  }
});

// Get latest water levels
async function getLatestWaterLevels() {
  try {
    const response = await api.get('/api/v1/sensors/water-level/latest');
    return response.data;
  } catch (error) {
    console.error('Error fetching water levels:', error);
    throw error;
  }
}

// Get time series data with Buddhist date
async function getWaterLevelHistory(buddhistDate) {
  try {
    const response = await api.get('/api/v1/sensors/water-level/timeseries', {
      params: { date: buddhistDate }
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching history:', error);
    throw error;
  }
}

// Helper function to convert to Buddhist date
function toBuddhistDate(date) {
  const d = new Date(date);
  const year = d.getFullYear() + 543;
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${day}/${month}/${year}`;
}

// Usage
const today = toBuddhistDate(new Date());
const waterLevelHistory = await getWaterLevelHistory(today);
```

### Vue.js Example

```javascript
// api.js
export const munbonAPI = {
  baseURL: 'https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com',
  apiKey: 'your-api-key',
  
  async request(endpoint, params = {}) {
    const url = new URL(this.baseURL + endpoint);
    Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
    
    const response = await fetch(url, {
      headers: {
        'x-api-key': this.apiKey
      }
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    
    return response.json();
  },
  
  getLatestWaterLevels() {
    return this.request('/api/v1/sensors/water-level/latest');
  },
  
  getMoistureTimeSeries(date) {
    return this.request('/api/v1/sensors/moisture/timeseries', { date });
  }
};

// Component
export default {
  data() {
    return {
      waterLevels: [],
      loading: false
    };
  },
  
  async mounted() {
    this.loading = true;
    try {
      const data = await munbonAPI.getLatestWaterLevels();
      this.waterLevels = data.sensors;
    } catch (error) {
      console.error('Failed to load water levels:', error);
    } finally {
      this.loading = false;
    }
  }
};
```

## Error Handling

The API returns standard HTTP status codes:
- `200` - Success
- `400` - Bad Request (e.g., missing date parameter)
- `401` - Unauthorized (missing or invalid API key)
- `500` - Internal Server Error

Error response format:
```json
{
  "error": "Error message describing what went wrong"
}
```

## Best Practices

1. **Cache Data**: Sensor data doesn't change rapidly. Cache responses for 1-5 minutes.
2. **Handle Errors**: Always implement error handling for network failures.
3. **Date Format**: Always use Buddhist calendar format for date parameters.
4. **Timezone**: All timestamps are in UTC. Convert to local time for display.
5. **Loading States**: Show loading indicators while fetching data.

## Data Update Frequency

- **Water Level**: Updates every 5-15 minutes
- **Moisture**: Updates every 30 minutes
- **AOS Weather**: Updates every 10 minutes

## Support

For API keys or technical support, contact the Munbon system administrator.