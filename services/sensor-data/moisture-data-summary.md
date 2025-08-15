# Moisture Data Analysis Summary

## Current Status (as of 18:30 Thailand Time)

### 1. HTTP Endpoint Activity
- **Endpoint**: `http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture`
- **Status**: Active and receiving data
- **Pattern**: Data arriving approximately every 100 seconds

### 2. Data Pattern Observed

#### Valid Data (Successfully Processed)
- **Gateway 0001**:
  - Sensor 000D
  - Last valid data: 17:06:24 (with moisture values: 45.5% surface, 52.3% deep)
  - Successfully saved to database

- **Gateway 0002** (Test data):
  - Sensors 001A and 001B
  - Last data: 17:30:00
  - Successfully saved to database

#### Empty Data Payloads
- Many requests coming with empty data: `{}`
- These cause processing errors (NULL sensor_id)
- Occurring every ~100 seconds
- Source IPs: 202.176.124.172, 49.230.136.36

### 3. Database Status
- **Latest moisture data in DB**: 
  - 0002-001B: 10:25:30 (72.5% surface, 85.3% deep)
  - 0002-001A: 10:25:00 (38.2% surface, 48.7% deep)
  - 0001-000D: 10:03:33 (45.5% surface, 52.3% deep)

### 4. Issues Identified

1. **Empty Payloads**: Many HTTP requests contain empty data `{}`, causing database constraint violations
2. **Network Issues**: Consumer had SQS connectivity issues earlier but recovered
3. **Timezone Confusion**: Data timestamps (e.g., "17:06:24") appear to be in the future but are actually local Thailand time

### 5. Recommendations

1. **Filter Empty Payloads**: Update HTTP server to reject or skip empty data payloads
2. **Add Validation**: Ensure `gw_id` is present before sending to SQS
3. **Monitor Pattern**: The 100-second interval suggests automated polling, possibly from misconfigured sensors
4. **Check Sensor Configuration**: Some sensors may be sending heartbeat/keepalive messages without actual data

## Next Steps
1. Update HTTP server to validate incoming data
2. Add logging to identify sources of empty payloads
3. Contact sensor operators about empty data transmissions