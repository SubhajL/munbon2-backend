# Munbon Irrigation System - Complete API Documentation

## Base Information
- **API Gateway ID**: `5e3l647kpd`
- **Region**: `ap-southeast-1` (Singapore)
- **Stage**: `prod`
- **Base URL**: `https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1`
- **Authentication**: Required header `X-API-Key: rid-ms-prod-key1`

## Date Format
All dates use Buddhist Era (BE) calendar: `DD/MM/YYYY`
- Example: `30/06/2568` (June 30, 2025 CE)
- Buddhist Era = Common Era + 543

---

## 1. AOS Weather Station Endpoints

### 1.1 Get Latest AOS Data
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest
```

**Response Format:**
```json
{
  "data_type": "aos_meteorological",
  "request_time": "2025-06-30T05:36:26.301Z",
  "request_time_buddhist": "30/06/2568",
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
        "timestamp": "2025-06-24 11:55:00",
        "timestamp_buddhist": "24/06/2568",
        "rainfall_mm": 0,
        "temperature_celsius": 35.2,
        "humidity_percentage": 0,
        "wind_speed_ms": 0,
        "wind_max_ms": 0,
        "wind_direction_degrees": 223,
        "solar_radiation_wm2": 12.38,
        "battery_voltage": 11.99,
        "pressure_hpa": 0
      }
    }
  ]
}
```

### 1.2 Get AOS Time Series Data
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/timeseries?date=24/06/2568
```

**Query Parameters:**
- `date` (required): Date in Buddhist calendar format DD/MM/YYYY

**Response Format:**
```json
{
  "data_type": "aos_meteorological",
  "request_date": "24/06/2568",
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
      "date_buddhist": "24/06/2568",
      "readings": [
        {
          "timestamp": "2025-06-23 17:00:00",
          "rainfall_mm": 0,
          "temperature_celsius": 34.66,
          "humidity_percentage": 0,
          "wind_speed_ms": 0,
          "wind_max_ms": 0,
          "wind_direction_degrees": 191.4,
          "solar_radiation_wm2": 12.28,
          "battery_voltage": 11.9,
          "pressure_hpa": 0
        },
        {
          "timestamp": "2025-06-23 17:05:00",
          "rainfall_mm": 0,
          "temperature_celsius": 34.73,
          "humidity_percentage": 0,
          "wind_speed_ms": 0,
          "wind_max_ms": 0,
          "wind_direction_degrees": 204.3,
          "solar_radiation_wm2": 12.23,
          "battery_voltage": 11.84,
          "pressure_hpa": 0
        }
      ]
    }
  ]
}
```

### 1.3 Get AOS Daily Statistics
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/statistics?date=24/06/2568
```

**Query Parameters:**
- `date` (required): Date in Buddhist calendar format DD/MM/YYYY

**Response Format:**
```json
{
  "data_type": "aos_meteorological",
  "request_date": "24/06/2568",
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
      "date_buddhist": "24/06/2568",
      "statistics": {
        "reading_count": 47,
        "rainfall": {
          "min": 0,
          "max": 0,
          "avg": 0,
          "total": 0
        },
        "temperature": {
          "min": 32.49,
          "max": 35.33,
          "avg": 33.9212,
          "stddev": 0.8046
        },
        "wind_speed": {
          "min": 0,
          "max": 0,
          "avg": 0,
          "stddev": 0,
          "max_gust": 0
        },
        "wind_direction": {
          "min": 151.4,
          "max": 238.8,
          "avg": 200.7404
        },
        "solar_radiation": {
          "min": 11.32,
          "max": 12.61,
          "avg": 11.938,
          "stddev": 0.3184
        },
        "battery": {
          "min": 11.04,
          "max": 12.2,
          "avg": 11.5674
        }
      }
    }
  ]
}
```

---

## 2. Water Level Sensor Endpoints

### 2.1 Get Latest Water Level Data
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest
```

**Response Format:**
```json
{
  "data_type": "water_level",
  "request_time": "2025-06-30T05:40:00.000Z",
  "request_time_buddhist": "30/06/2568",
  "sensor_count": 5,
  "sensors": [
    {
      "sensor_id": "wl001",
      "sensor_name": "Water Level Sensor 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-06-30T05:35:00.000Z",
        "timestamp_buddhist": "30/06/2568",
        "water_level_m": 2.45,
        "flow_rate_m3s": 0,
        "quality": 100
      }
    }
  ]
}
```

### 2.2 Get Water Level Time Series Data
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/timeseries?date=30/06/2568
```

**Query Parameters:**
- `date` (required): Date in Buddhist calendar format DD/MM/YYYY

**Response Format:**
```json
{
  "data_type": "water_level",
  "request_date": "30/06/2568",
  "sensor_count": 5,
  "sensors": [
    {
      "sensor_id": "wl001",
      "sensor_name": "Water Level Sensor 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "date_buddhist": "30/06/2568",
      "readings": [
        {
          "timestamp": "2025-06-30T00:00:00.000Z",
          "water_level_m": 2.35,
          "flow_rate_m3s": 0,
          "quality": 100
        },
        {
          "timestamp": "2025-06-30T00:05:00.000Z",
          "water_level_m": 2.36,
          "flow_rate_m3s": 0,
          "quality": 100
        }
      ]
    }
  ]
}
```

### 2.3 Get Water Level Daily Statistics
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/statistics?date=30/06/2568
```

**Query Parameters:**
- `date` (required): Date in Buddhist calendar format DD/MM/YYYY

**Response Format:**
```json
{
  "data_type": "water_level",
  "request_date": "30/06/2568",
  "sensor_count": 5,
  "sensors": [
    {
      "sensor_id": "wl001",
      "sensor_name": "Water Level Sensor 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "date_buddhist": "30/06/2568",
      "statistics": {
        "count": 288,
        "min": 2.25,
        "max": 2.55,
        "avg": 2.40,
        "stddev": 0.08
      }
    }
  ]
}
```

---

## 3. Moisture Sensor Endpoints

### 3.1 Get Latest Moisture Data
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest
```

**Response Format:**
```json
{
  "data_type": "moisture",
  "request_time": "2025-06-30T05:40:00.000Z",
  "request_time_buddhist": "30/06/2568",
  "sensor_count": 10,
  "sensors": [
    {
      "sensor_id": "ms001",
      "sensor_name": "Moisture Sensor 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-06-30T05:35:00.000Z",
        "timestamp_buddhist": "30/06/2568",
        "moisture_percentage": 65.5,
        "temperature_celsius": 28.3,
        "quality": 100
      }
    }
  ]
}
```

### 3.2 Get Moisture Time Series Data
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/timeseries?date=30/06/2568
```

**Query Parameters:**
- `date` (required): Date in Buddhist calendar format DD/MM/YYYY

**Response Format:**
```json
{
  "data_type": "moisture",
  "request_date": "30/06/2568",
  "sensor_count": 10,
  "sensors": [
    {
      "sensor_id": "ms001",
      "sensor_name": "Moisture Sensor 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "date_buddhist": "30/06/2568",
      "readings": [
        {
          "timestamp": "2025-06-30T00:00:00.000Z",
          "moisture_percentage": 64.2,
          "temperature_celsius": 27.8,
          "quality": 100
        },
        {
          "timestamp": "2025-06-30T00:05:00.000Z",
          "moisture_percentage": 64.5,
          "temperature_celsius": 27.9,
          "quality": 100
        }
      ]
    }
  ]
}
```

### 3.3 Get Moisture Daily Statistics
```
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/statistics?date=30/06/2568
```

**Query Parameters:**
- `date` (required): Date in Buddhist calendar format DD/MM/YYYY

**Response Format:**
```json
{
  "data_type": "moisture",
  "request_date": "30/06/2568",
  "sensor_count": 10,
  "sensors": [
    {
      "sensor_id": "ms001",
      "sensor_name": "Moisture Sensor 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "date_buddhist": "30/06/2568",
      "statistics": {
        "count": 288,
        "min": 62.5,
        "max": 68.2,
        "avg": 65.3,
        "stddev": 1.2
      }
    }
  ]
}
```

---

## Authentication

All endpoints require the API key in the request header:
```bash
X-API-Key: rid-ms-prod-key1
```

Valid API keys:
- `rid-ms-prod-key1` - RID Main System
- `tmd-weather-key2` - Thai Meteorological Department  
- `university-key3` - University Research

---

## Example cURL Commands

```bash
# Get latest AOS weather data
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest

# Get water level time series for today (Buddhist calendar)
curl -H "X-API-Key: rid-ms-prod-key1" \
  "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/timeseries?date=30/06/2568"

# Get moisture statistics for specific date
curl -H "X-API-Key: rid-ms-prod-key1" \
  "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/statistics?date=25/06/2568"
```

---

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
  "error": "Date parameter required"
}
```

### 500 Internal Server Error
```json
{
  "error": "Database error"
}
```

---

## Notes
1. All timestamps in responses are in ISO 8601 format with timezone
2. Buddhist calendar dates are used for all date parameters and date displays
3. Water level is measured in meters (m)
4. Moisture is measured in percentage (%)
5. Temperature is in Celsius (°C)
6. Wind speed is in meters per second (m/s)
7. Solar radiation is in watts per square meter (W/m²)
8. Quality score ranges from 0-100 (100 being best)
9. Flow rate is currently not implemented (always returns 0)
10. AOS humidity and pressure sensors appear to be unavailable (return 0)