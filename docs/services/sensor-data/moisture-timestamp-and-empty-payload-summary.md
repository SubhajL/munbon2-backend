# Moisture Data Processing Summary

## 1. Timestamp Processing Confirmation

### Moisture Sensors
- **Time Format**: UTC time string (e.g., "17:06:24")
- **Date Format**: "YYYY/MM/DD" (e.g., "2025/07/31")
- **Processing**: Combined into full timestamp using `parseTimestamp()` function
- **Code Location**: `/src/services/sqs-processor-helpers.ts` lines 51-56
```typescript
const sensorTimestamp = parseTimestamp(
  sensorData.sensor_date,    // e.g., "2025/07/31"
  sensorData.sensor_utc,      // e.g., "17:06:24"
  timestamp,                  // fallback
  logger
);
```

### Water Level Sensors
- **Time Format**: Epoch timestamp (milliseconds since Jan 1, 1970)
- **Processing**: Already handled correctly in existing code
- **Example**: `timestamp: 1738340580000`

## 2. Empty Payload Handling Update

### Previous Behavior (Problematic)
- Empty payloads `{}` were sent to SQS
- Consumer tried to process them
- Database constraint violations due to NULL sensor_id
- Blocked valid data processing

### New Behavior (Fixed)
- Empty payloads are **accepted** with 200 OK response
- They are **NOT** sent to SQS queue
- They are **NOT** written to database
- Valid data continues normal processing
- Empty payload sources are tracked for monitoring

### Implementation Details
- **Updated File**: `/home/ubuntu/app/moisture-http-server/src/simple-http-server.ts`
- **Deployed**: July 31, 2025 at 16:49 Thailand Time
- **Key Logic**:
  ```typescript
  if (isEmptyPayload || hasNoGatewayId) {
    // Log for monitoring
    // Return 200 OK
    // Do NOT send to SQS
  }
  ```

## 3. Empty Payload Sources
- IP: 184.22.228.193 (sending every ~100 seconds)
- IP: 49.229.183.255 (intermittent)
- Likely keepalive/heartbeat messages from sensors or gateways

## 4. Monitoring Endpoints
- **Statistics**: `http://43.209.22.250:8080/api/stats/empty-payloads`
- **Health Check**: `http://43.209.22.250:8080/health`

## 5. Result
- ✅ Database errors from empty payloads: **FIXED**
- ✅ Valid moisture data can now flow through unblocked
- ✅ Empty payloads accepted gracefully (no errors for sensors)
- ✅ Monitoring in place to track patterns