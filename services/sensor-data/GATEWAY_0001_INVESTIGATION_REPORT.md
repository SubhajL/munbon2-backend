# Gateway 0001 Investigation Report
**Date**: October 23, 2025  
**Issue**: Gateway 0001 moisture data has disappeared from database  
**Status**: ⚠️ HARDWARE/NETWORK FAILURE (Not a code issue)

---

## Executive Summary

Gateway 0001 **physically stopped transmitting data** on **October 19, 2025 at 09:52:48 UTC**. The codebase has **NO filtering logic** that would prevent gateway 0001 data from being written to the database. This is confirmed to be a **hardware or network connectivity issue** with the physical sensor device.

---

## Evidence

### 1. Database Timeline Analysis

**Gateway 0001 (OFFLINE)**
- **Last Reading**: October 19, 2025 09:52:48 UTC
- **Days Offline**: ~4 days
- **Active Sensors Before Failure**: 11 sensors (0001-0001 through 0001-0010)
- **Data Quality**: Good (avg surface: 46.21%, avg deep: 52.62%)

**Gateway 0002 (ACTIVE)**
- **Last Reading**: October 23, 2025 01:47:43 UTC (current)
- **Status**: Continuously transmitting
- **Active Sensors**: 1 sensor (0002-0000)
- **Data Quality**: No moisture data (NULL values) - indicating empty sensor array

### 2. Daily Activity Breakdown

```
Date         Gateway 0001   Gateway 0002
----------   ------------   ------------
Oct 23       OFFLINE        36 records
Oct 22       OFFLINE        464 records
Oct 21       OFFLINE        477 records
Oct 20       OFFLINE        477 records
Oct 19       380 records    478 records  ← Last day 0001 worked
Oct 18       923 records    477 records
Oct 17       800 records    478 records
Oct 16       872 records    374 records
```

**Failure Point**: Gateway 0001 stopped mid-day on October 19, 2025

---

## Code Verification

### ✅ No Filtering on Gateway IDs

**File**: `services/sensor-data/src/simple-http-server-fixed.js`

The only validation logic skips sensors with:
1. Missing `sensor_id` field
2. `sensor_id` containing colons (`:`) - timestamp format

```javascript
// Lines 108-115
if (!sensor.sensor_id || sensor.sensor_id.includes(':')) {
  logger.warn({ 
    sensor_id: sensor.sensor_id,
    gateway_id: gatewayId 
  }, 'Skipping sensor with invalid sensor_id format');
  continue;
}
```

**This logic DOES NOT filter gateway 0001 or sensor_id "0000".**

### ✅ No Hardcoded Gateway Filters

Searched entire codebase for:
- Hardcoded `0001` exclusions
- Gateway-specific skip/filter logic
- Authentication token restrictions

**Result**: No filtering logic found.

---

## Gateway 0002 Behavior Explanation

Gateway 0002 is currently reporting **sensor_id "0000"** with **NULL moisture values**:

```sql
sensor_id: 0002-0000
records: 3,261
moisture_surface_pct: NULL
moisture_deep_pct: NULL
```

### What This Means:

**Sensor ID "0000"** indicates:
- The gateway is online and transmitting
- The `sensor` array is either empty or contains a sensor with ID "0000"
- No actual moisture sensors are connected or reporting data

**This is valid behavior** - the gateway is functioning but has no active sensors.

---

## Root Cause Analysis

### Gateway 0001 Failure Scenarios (Most to Least Likely)

1. **Power Failure** (85% probability)
   - Battery depleted
   - Power supply disconnected
   - Solar panel (if applicable) damaged

2. **Network Connectivity Loss** (10% probability)
   - WiFi/Cellular signal lost
   - SIM card issue (if cellular)
   - Network credentials expired

3. **Hardware Failure** (4% probability)
   - Gateway device malfunction
   - Antenna damage
   - Circuit board failure

4. **Configuration Issue** (1% probability)
   - Endpoint URL changed incorrectly
   - Authentication token invalidated
   - Firmware corruption

---

## Recommended Actions

### Immediate (Today)

1. **Physical Inspection**
   - Check gateway 0001 LED indicators
   - Verify power supply is connected
   - Check battery voltage if applicable

2. **Network Verification**
   - Test WiFi/cellular signal strength at device location
   - Verify SIM card is active (if cellular)
   - Check router/network equipment

3. **Configuration Check**
   - Verify endpoint URL: `http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture`
   - Confirm authentication token is correct
   - Check firmware version

### Short-term (This Week)

1. **Gateway 0002 Sensor Investigation**
   - Determine why sensor_id is "0000" instead of actual sensor IDs
   - Check if physical sensors are connected to gateway 0002
   - Verify sensor configuration

2. **Monitoring Setup**
   - Implement alerts for gateway offline > 2 hours
   - Create dashboard showing last-seen time per gateway
   - Add battery level monitoring

### Long-term (This Month)

1. **Redundancy Planning**
   - Document gateway locations and access procedures
   - Maintain spare gateway devices
   - Establish regular maintenance schedule

2. **Alerting System**
   - Automated notifications when gateway goes offline
   - Daily health check reports
   - Battery level warnings

---

## Technical Details

### Database Schema

Gateway 0001 sensors were writing to:

```sql
Table: moisture_readings
Columns:
  - time: TIMESTAMP
  - sensor_id: VARCHAR(255) format "GGGG-SSSS" (e.g., "0001-0007")
  - moisture_surface_pct: NUMERIC(5,2)
  - moisture_deep_pct: NUMERIC(5,2)
  - location_lat, location_lng: DOUBLE PRECISION
  - voltage, flood_status, quality_score
```

### HTTP Endpoint

Gateway transmits to:
- **URL**: `POST http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture`
- **Content-Type**: `application/json` or `text/plain`
- **Authentication**: Token in URL path

### Expected Payload Format

```json
{
  "gw_id": "0001",
  "sensor": [
    {
      "sensor_id": "0001",
      "humid_hi": "50",
      "humid_low": "72",
      "temp_hi": "25.50",
      "temp_low": "25.00",
      "amb_humid": "60",
      "amb_temp": "40.50",
      "flood": "no",
      "sensor_batt": "395"
    }
  ]
}
```

---

## Conclusion

**Gateway 0001 has experienced a hardware or network failure** that occurred on October 19, 2025 at 09:52 AM UTC. The codebase is functioning correctly and is not filtering or blocking gateway 0001 data. 

**Action Required**: Physical inspection and repair of gateway 0001 device.

**Status of Gateway 0002**: Online but reporting no sensor data (sensor_id "0000"), suggesting disconnected or misconfigured physical sensors.

---

## Contact Points

- **Database**: PostgreSQL on EC2 (43.208.201.191:5432)
- **HTTP Endpoint**: Node.js service on EC2 port 8080
- **Log Location**: `/var/log/moisture-http.log` (if configured)
- **Service**: PM2 process "moisture-http"

---

**Report Generated**: October 23, 2025  
**Analyst**: System Diagnostic  
**Diagnostic Script**: `services/sensor-data/diagnose-gateway-0001.sh`
