# AOS Data Integration from MSSQL

## Current Status
✅ Unified API updated with MSSQL integration code
❌ MSSQL connection failing - need correct server IP/hostname
✅ AOS endpoints ready to serve data once connected

## MSSQL Configuration Needed

Please update `.env.local` with the correct MSSQL server details:

```bash
# Current configuration (not working)
MSSQL_HOST=localhost        # ← Need actual IP address or hostname
MSSQL_INSTANCE=SCADA        # Instance name from screenshot
MSSQL_PORT=1433             # Default SQL Server port
MSSQL_DB=Scada2024          # Database name from screenshot
MSSQL_USER=sa               # Username from your input
MSSQL_PASSWORD=bangkok1234  # Password from your input
```

### Possible values for MSSQL_HOST:
- IP address: e.g., `192.168.1.100`
- Hostname: e.g., `RID-SCADA01` (if DNS resolves)
- Fully qualified: e.g., `RID-SCADA01.domain.local`

## Database Structure (from screenshot)

**Table**: `dbo.MoonBonLive`
- `DateTime` - Timestamp of reading
- `TagIndex` - Sensor identifier (1-60+)
- `Val` - Numeric value

## TagIndex Mapping (Assumed)

The API maps TagIndex values to AOS measurements:
- **1-10**: Rainfall (mm)
- **11-20**: Temperature (°C)
- **21-30**: Humidity (%)
- **31-40**: Wind Speed (m/s)
- **41-50**: Wind Direction (degrees)
- **51-60**: Pressure (hPa)

Each group of 10 represents a different station (AOS001, AOS002, etc.)

## AOS API Endpoints

All three endpoints are ready and will work once MSSQL is connected:

### 1. Latest AOS Data
```bash
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest
```

Response format:
```json
{
  "data_type": "aos_meteorological",
  "request_time": "2025-06-30T03:00:00.000Z",
  "request_time_buddhist": "30/06/2568",
  "station_count": 6,
  "stations": [
    {
      "station_id": "AOS001",
      "station_name": "AOS Station 1",
      "location": {
        "latitude": 14.3754,
        "longitude": 102.8756
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-06-30T02:55:00.000Z",
        "timestamp_buddhist": "30/06/2568",
        "rainfall_mm": 0.5,
        "temperature_celsius": 28.5,
        "humidity_percentage": 75.2,
        "wind_speed_ms": 3.2,
        "wind_direction_degrees": 180,
        "pressure_hpa": 1012.3
      }
    }
  ]
}
```

### 2. Time Series Data
```bash
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/timeseries?date=30/06/2568
```

### 3. Statistics
```bash
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/statistics?date=30/06/2568
```

## Next Steps

1. **Get correct MSSQL server IP/hostname**
   - Check if `RID-SCADA01` resolves in your network
   - Or get the IP address of the MSSQL server

2. **Update `.env.local`** with correct `MSSQL_HOST`

3. **Restart the unified API**:
   ```bash
   kill 62073
   source .env.local && nohup node src/unified-api-v2.js > unified-api-v2.log 2>&1 &
   ```

4. **Test AOS endpoints** through the public API

## Testing with curl

Once MSSQL is connected:
```bash
# Test AOS latest data
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest | jq
```