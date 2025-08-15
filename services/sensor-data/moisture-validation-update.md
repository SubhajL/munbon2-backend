# Moisture Data Validation Update

## Problem Identified
- HTTP endpoint was receiving empty payloads `{}` every ~100 seconds
- These empty payloads were causing database constraint violations (NULL sensor_id)
- Valid moisture data was being blocked by processing errors

## Solution Implemented

### 1. Updated HTTP Server with Validation
- **File**: `/home/ubuntu/app/moisture-http-server/src/simple-http-server.ts`
- **Deployed**: July 31, 2025 at 16:35 Thailand Time

### 2. New Validation Features
- ✅ Rejects empty data payloads with 400 Bad Request
- ✅ Validates presence of gateway ID (gw_id or gateway_id)
- ✅ Tracks sources of empty payloads
- ✅ Logs warnings for rejected payloads
- ✅ Added statistics endpoint

### 3. New Endpoints
- **Stats**: `http://43.209.22.250:8080/api/stats/empty-payloads`
  - Shows IP addresses sending empty payloads
  - Tracks count and last seen time

### 4. Empty Payload Sources Identified
- IP: 184.22.228.193 (3 empty payloads)
- IP: 49.229.183.255 (1 empty payload)

## Monitoring Tools Created

### 1. `monitor-moisture-flow.sh`
- Real-time monitoring of the entire moisture data pipeline
- Shows HTTP status, empty payload rejections, valid data, SQS queue, consumer activity, and database entries

### 2. `check-moisture-activity.sh`
- Quick snapshot of moisture endpoint activity
- Shows hourly message counts and active gateways

### 3. `watch-moisture-live.sh`
- Live tail of incoming moisture data

### 4. `find-missing-moisture.sh`
- Searches for missing data between HTTP and database

## Results
- Empty payloads are now being rejected at the HTTP layer
- Database constraint violations should stop
- Valid moisture data can now flow through without being blocked
- Sources of empty payloads have been identified for follow-up

## Next Steps
1. Monitor for valid moisture data coming through
2. Contact operators of IPs sending empty payloads
3. Consider rate limiting for problematic sources
4. Add more detailed logging for sensor data patterns