# External Data API - Current Status Summary

## 1. Are They Working Now?
**PARTIALLY** - The API infrastructure is deployed but experiencing connectivity issues due to Cloudflare tunnel instability.

### Current Status:
- ✅ External API endpoints are deployed on AWS API Gateway
- ✅ API key authentication is working
- ✅ AWS Parameter Store is updated with new tunnel URL
- ❌ Lambda cannot reach the Unified API due to tunnel connectivity issues
- ⚠️ Cloudflare tunnels keep disconnecting ("context canceled" errors)

## 2. System Architecture

```
[Data Sources] → [Unified API] → [Cloudflare Tunnel] → [AWS Lambda] → [API Gateway] → [External Clients]
     ↓                ↓                    ↓                  ↓              ↓               ↓
 TimescaleDB     localhost:3000    *.trycloudflare.com   Proxy Handler   Public API    RID/TMD/Unis
 MSSQL (AOS)                       (Dynamic URL)         (Reads from      Endpoints     Systems
                                                         Parameter Store)
```

### Key Components:
1. **Unified API** (localhost:3000) - Aggregates data from TimescaleDB and MSSQL
2. **Cloudflare Tunnel** - Provides secure access from Lambda to local API
3. **AWS Parameter Store** (`/munbon/tunnel-url`) - Stores current tunnel URL
4. **Lambda Functions** - Read tunnel URL dynamically from Parameter Store
5. **API Gateway** - Public-facing endpoints with API key authentication

## 3. External API Endpoints

### Base URL
`https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1`

### Authentication
Header: `X-API-Key: {api_key}`

Valid Keys:
- `rid-ms-prod-key1` - RID Main System
- `tmd-weather-key2` - Thai Meteorological Department
- `university-key3` - University Research

### Water Level Endpoints
1. **Latest**: `GET /public/water-levels/latest`
2. **Time Series**: `GET /public/water-levels/timeseries?date=DD/MM/YYYY`
3. **Statistics**: `GET /public/water-levels/statistics?date=DD/MM/YYYY`

**Response Example** (Latest):
```json
{
  "data_type": "water_level",
  "request_time": "2025-07-07T10:00:00.000Z",
  "request_time_buddhist": "07/07/2568",
  "sensor_count": 5,
  "sensors": [{
    "sensor_id": "WL001",
    "sensor_name": "Water Level Sensor 001",
    "location": "Main Canal Gate 1",
    "zone": "Zone1",
    "latest_reading": {
      "timestamp": "2025-07-07T09:55:00.000Z",
      "timestamp_buddhist": "07/07/2568",
      "water_level_m": 2.45,
      "flow_rate_m3s": 0,
      "quality": 100
    }
  }]
}
```

### Moisture Endpoints
1. **Latest**: `GET /public/moisture/latest`
2. **Time Series**: `GET /public/moisture/timeseries?date=DD/MM/YYYY`
3. **Statistics**: `GET /public/moisture/statistics?date=DD/MM/YYYY`

**Response Example** (Latest):
```json
{
  "data_type": "moisture",
  "request_time": "2025-07-07T10:00:00.000Z",
  "request_time_buddhist": "07/07/2568",
  "sensor_count": 10,
  "sensors": [{
    "sensor_id": "MS001",
    "sensor_name": "Moisture Sensor 001",
    "location": "Field A Section 1",
    "zone": "Zone2",
    "latest_reading": {
      "timestamp": "2025-07-07T09:50:00.000Z",
      "timestamp_buddhist": "07/07/2568",
      "moisture_percentage": 45.2,
      "temperature_celsius": 28.5,
      "quality": 100
    }
  }]
}
```

### AOS (Weather) Endpoints
1. **Latest**: `GET /public/aos/latest`
2. **Time Series**: `GET /public/aos/timeseries?date=DD/MM/YYYY`
3. **Statistics**: `GET /public/aos/statistics?date=DD/MM/YYYY`

**Response Example** (Latest):
```json
{
  "data_type": "aos_meteorological",
  "request_time": "2025-07-07T10:00:00.000Z",
  "request_time_buddhist": "07/07/2568",
  "station_count": 1,
  "stations": [{
    "station_id": "AOS001",
    "station_name": "Munbon AOS Weather Station",
    "location": {
      "latitude": 14.3754,
      "longitude": 102.8756
    },
    "zone": "Zone1",
    "latest_reading": {
      "timestamp": "2025-07-07T09:55:00",
      "timestamp_buddhist": "07/07/2568",
      "rainfall_mm": 0,
      "temperature_celsius": 32.8,
      "humidity_percentage": 0,
      "wind_speed_ms": 2.1,
      "wind_max_ms": 3.5,
      "wind_direction_degrees": 180,
      "solar_radiation_wm2": 850.5,
      "battery_voltage": 12.1,
      "pressure_hpa": 0
    }
  }]
}
```

**Response Example** (Statistics):
```json
{
  "data_type": "aos_meteorological",
  "request_date": "07/07/2568",
  "station_count": 1,
  "stations": [{
    "station_id": "AOS001",
    "station_name": "Munbon AOS Weather Station",
    "location": {
      "latitude": 14.3754,
      "longitude": 102.8756
    },
    "zone": "Zone1",
    "date_buddhist": "07/07/2568",
    "statistics": {
      "reading_count": 288,
      "rainfall": {
        "min": 0,
        "max": 2.5,
        "avg": 0.15,
        "total": 43.2
      },
      "temperature": {
        "min": 25.2,
        "max": 38.5,
        "avg": 31.8,
        "stddev": 3.2
      },
      "wind_speed": {
        "min": 0,
        "max": 8.5,
        "avg": 2.3,
        "stddev": 1.8,
        "max_gust": 12.1
      },
      "wind_direction": {
        "min": 0,
        "max": 359,
        "avg": 185.5
      },
      "solar_radiation": {
        "min": 0,
        "max": 1050.2,
        "avg": 425.8,
        "stddev": 385.2
      },
      "battery": {
        "min": 11.8,
        "max": 13.2,
        "avg": 12.5
      }
    }
  }]
}
```

## Current Issues & Solutions

### Problem: Cloudflare Tunnel Instability
**Root Cause**: Free-tier "quick tunnels" have no uptime guarantee and change URLs on restart

**Solutions**:
1. **Short-term**: Monitor and auto-update Parameter Store when tunnel URL changes
2. **Medium-term**: Use permanent Cloudflare tunnel with fixed subdomain
3. **Long-term**: Deploy Unified API to cloud (EC2, ECS, App Runner)

### Problem: "Context Canceled" Errors
**Root Cause**: Multiple tunnel instances or network interruptions

**Solutions**:
1. Ensure only ONE tunnel instance per purpose
2. Use process managers (systemd/launchd) for auto-restart
3. Monitor tunnel health and restart when needed

## Testing the API

```bash
# Test AOS latest data
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest

# Test water level time series (Buddhist calendar)
curl -H "X-API-Key: rid-ms-prod-key1" \
  "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/timeseries?date=07/07/2568"

# Test moisture statistics
curl -H "X-API-Key: rid-ms-prod-key1" \
  "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/statistics?date=07/07/2568"
```

## Important Notes
1. All dates use Buddhist calendar (BE = CE + 543)
2. AOS data comes from MSSQL Server at `moonup.hopto.org:1433`
3. Lambda functions read tunnel URL dynamically from Parameter Store
4. No Lambda redeployment needed when tunnel URL changes
5. Unified API requires internal API key for security