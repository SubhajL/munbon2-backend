# AOS Weather Station Data Integration - SUCCESS ✅

## Summary
Successfully integrated AOS weather station data from MSSQL Server into the Munbon Data API.

## MSSQL Connection Details
- **Host**: moonup.hopto.org
- **Port**: 1433
- **Database**: db_scada
- **Table**: tb_aos
- **Authentication**: SQL Server Authentication
- **Username**: sa
- **Password**: bangkok1234

## AOS Data Structure
The `tb_aos` table contains the following columns:
- `id` - Record ID
- `data_datetime` - Timestamp of measurement
- `battery` - Station battery voltage
- `windspeed` - Wind speed (m/s)
- `windmax` - Maximum wind speed (m/s)
- `raingauge` - Rainfall amount (mm)
- `temp` - Temperature (°C)
- `winddirect` - Wind direction (degrees)
- `solar` - Solar radiation (W/m²)

## API Endpoints

### 1. Latest AOS Data
```bash
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest
```

**Example Response:**
```json
{
  "data_type": "aos_meteorological",
  "request_time": "2025-06-30T05:27:12.886Z",
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

### 2. Time Series Data
```bash
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/timeseries?date=24/06/2568
```

Returns all AOS readings for the specified date (Buddhist calendar).

### 3. Daily Statistics
```bash
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/statistics?date=24/06/2568
```

**Example Response:**
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

## Testing Commands

```bash
# Test with API key
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest | jq

# Get timeseries for specific date (Buddhist calendar)
curl -H "X-API-Key: rid-ms-prod-key1" \
  "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/timeseries?date=30/06/2568" | jq

# Get statistics for specific date
curl -H "X-API-Key: rid-ms-prod-key1" \
  "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/statistics?date=30/06/2568" | jq
```

## Notes
1. The AOS station appears to have no humidity sensor (always returns 0)
2. Wind speed sensors may be inactive (always returns 0 in sample data)
3. Data collection interval appears to be 5 minutes
4. All dates use Buddhist calendar (BE = CE + 543)
5. The station is currently assigned to Zone1 by default

## Architecture
```
[MSSQL Server] ---> [Unified API] ---> [Cloudflare Tunnel] ---> [AWS Lambda] ---> [API Gateway]
moonup.hopto.org    localhost:3000     *.cfargotunnel.com       Proxy Handler     Public API
```

## Status
✅ MSSQL connection established
✅ AOS data successfully retrieved
✅ All three endpoints working
✅ Public API accessible with API key authentication