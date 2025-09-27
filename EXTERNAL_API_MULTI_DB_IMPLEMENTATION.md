# External API V2.0 - Multi-Database Implementation

## Overview

The External API V2.0 now uses **two different databases** to serve data:

1. **TimescaleDB (PostgreSQL)** - For Water Level and Moisture data
2. **MSSQL SCADA Database** - For AOS Weather data

## Database Configuration

### TimescaleDB (EC2)
- **Host**: 43.208.201.191 (localhost on EC2)
- **Port**: 5432
- **Database**: sensor_data
- **Tables**: 
  - `water_level_readings` - Water level sensor data
  - `moisture_readings` - Soil moisture sensor data

### MSSQL SCADA (External)
- **Host**: moonup.hopto.org
- **Database**: db_scada
- **Schema**: dbo
- **Table**: tb_aos
- **Data**: AOS weather station data (dated back to July 2025)

## AOS Data Structure (from SCADA)

Based on the provided table structure, the `dbo.tb_aos` table contains:

| Column | Type | Description |
|--------|------|-------------|
| datetime | DATETIME | Timestamp of reading |
| site_ID | VARCHAR | Weather station ID |
| air_temp | FLOAT | Air temperature (°C) |
| humidity | FLOAT | Relative humidity (%) |
| air_pressure | FLOAT | Atmospheric pressure (hPa) |
| solar_rad | FLOAT | Solar radiation (W/m²) |
| wind_spd_avg | FLOAT | Average wind speed (m/s) |
| wind_direction | FLOAT | Wind direction (degrees) |
| rainfall_1h_tot | FLOAT | Total rainfall in last hour (mm) |
| et0_cal | FLOAT | Calculated evapotranspiration (mm) |

## API Response Mapping

The API transforms SCADA data to match the External API V2.0 specification:

```javascript
// SCADA columns → API response fields
{
  station_id: row.site_ID,
  rainfall_mm: row.rainfall_1h_tot,
  temperature_celsius: row.air_temp,
  humidity_percentage: row.humidity,
  wind_speed_ms: row.wind_spd_avg,
  wind_direction_degrees: row.wind_direction,
  pressure_hpa: row.air_pressure,
  solar_radiation_wm2: row.solar_rad,
  evapotranspiration_mm: row.et0_cal
}
```

## Deployment

```bash
# Deploy the multi-database API
./deploy-external-api-v2-ec2.sh

# Test all endpoints
./test-external-api-v2-ec2.sh
```

## Environment Variables

```env
# PostgreSQL for Water Level & Moisture
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sensor_data
DB_USER=postgres
DB_PASSWORD=__ROTATED_DB_PASSWORD__

# MSSQL for AOS Weather Data
MSSQL_SERVER=moonup.hopto.org
MSSQL_DATABASE=db_scada
MSSQL_USER=sa
MSSQL_PASSWORD=P@ssw0rd

# Server Port
PORT=8080
```

## Testing AOS Data

Since the AOS data is dated back to July 2025, when testing:

1. For latest data: Will show the most recent records (July 2025)
2. For timeseries: Use dates from July 2025, e.g., "15/07/2568"
3. For statistics: Use dates from July 2025

Example test for July 15, 2025:
```bash
curl -H "X-API-Key: rid-ms-prod-key1" \
  "http://43.208.201.191:8080/api/v1/public/aos/timeseries?date=15/07/2568"
```

## Architecture Benefits

1. **Leverages Existing Data**: Uses actual SCADA database with real AOS data
2. **No Data Duplication**: No need to copy AOS data to TimescaleDB
3. **Real-time Access**: Queries live SCADA database
4. **Maintains API Contract**: External users see no difference
5. **Database Specialization**: Each database optimized for its data type

## Notes

- The SCADA database contains historical data (July 2025)
- Location coordinates for AOS stations are not in the SCADA table (returns 0,0)
- The API maintains the exact same response format as specified in External API V2.0
- All authentication and response formats remain unchanged