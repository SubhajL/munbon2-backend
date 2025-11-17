# Smart Farm Trigger & Listener System Status

## Executive Summary

**Status: ⚠️ PARTIALLY WORKING** - Triggers exist, listener can start, but service has errors in control loops.

---

## 1. Database Triggers (✅ WORKING)

### Location
- **Database**: AWS `sensor_data` (43.208.201.191:5432)
- **Schema**: `public`
- **Tables**: `moisture_readings`, `water_level_readings`

### Trigger Details

**Trigger on moisture_readings:**
```sql
CREATE TRIGGER trg_moisture_readings_notify
AFTER INSERT ON public.moisture_readings
FOR EACH ROW
EXECUTE FUNCTION water_control_smartfarm.notify_sensor_reading()
```

**Trigger on water_level_readings:**
```sql
CREATE TRIGGER trg_water_level_readings_notify
AFTER INSERT ON public.water_level_readings
FOR EACH ROW
EXECUTE FUNCTION water_control_smartfarm.notify_sensor_reading()
```

### Notification Function
```sql
water_control_smartfarm.notify_sensor_reading()
```

**What it does:**
1. Detects which table triggered it (moisture or water_level)
2. Extracts sensor_id, value, timestamp
3. Sends PostgreSQL NOTIFY on channel: **`sensor_evaluation_needed`**
4. Payload format:
```json
{
  "sensor_id": "0001-0001",
  "value": 84.5,
  "timestamp": "2025-10-10T12:00:00Z",
  "sensor_type": "moisture"
}
```

### Verification Commands
```bash
# Check if triggers exist
node scripts/test-trigger-listener.js

# Manual verification
psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT t.tgname, c.relname
FROM pg_trigger t
JOIN pg_class c ON t.tgrelid = c.oid
WHERE c.relname IN ('moisture_readings', 'water_level_readings')
  AND t.tgname NOT LIKE 'RI_%'
  AND t.tgname NOT LIKE 'ts_%';
"
```

---

## 2. Listener Service (⚠️ STARTS BUT HAS ERRORS)

### Service Configuration
- **File**: `src/services/sensorUpdateListener.js`
- **Channel**: `sensor_evaluation_needed`
- **Database Connection**: sensor_data (43.208.201.191:5432)

### Startup Evidence
From service logs:
```
[32minfo[39m: Sensor update listener started (listening on sensor_evaluation_needed)
[32minfo[39m: Real-time control system enabled: sensor notifications will trigger immediate valve actions
```

### Current Issues
1. ❌ **Service crashes with errors** - Multiple `[object Object]` errors in control loops
2. ❌ **No active listener connections found** when querying `pg_stat_activity`
3. ⚠️ **Service needs to be restarted** due to crashes

### How to Start Service
```bash
cd /Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control
npm start
```

### Check if Listener is Active
```bash
# Check service logs
tail -f /path/to/service.log

# Check database connections
psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT pid, usename, application_name, state
FROM pg_stat_activity
WHERE application_name LIKE '%smartfarm%';
"
```

---

## 3. Complete Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. SENSOR DATA INSERTION                                    │
│     New row added to moisture_readings or water_level_readings│
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  2. TRIGGER FIRES (AFTER INSERT)                            │
│     trg_moisture_readings_notify                            │
│     trg_water_level_readings_notify                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  3. NOTIFICATION FUNCTION EXECUTES                          │
│     water_control_smartfarm.notify_sensor_reading()         │
│     Calls: pg_notify('sensor_evaluation_needed', payload)   │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  4. LISTENER RECEIVES NOTIFICATION                          │
│     SensorUpdateListener (src/services/sensorUpdateListener.js)│
│     Connected to channel: 'sensor_evaluation_needed'        │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  5. REALTIME CONTROL SERVICE PROCESSES                      │
│     RealtimeControlService.handleSensorReading()            │
│     - Looks up plot from sensor_id                          │
│     - Gets control thresholds                               │
│     - Makes control decision                                │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  6. VALVE COMMAND ISSUED                                    │
│     ValveCommandService.sendCommand()                       │
│     Writes to: MSSQL db_scada.tb_valve_command_v2_test     │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  7. AUDIT LOG CREATED                                       │
│     ValveAuditService.logControlDecision()                  │
│     Writes to: sensor_data.valve_control_audit              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Testing the Flow

### Test Script
Run the comprehensive test:
```bash
cd /Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control

# This script will:
# 1. Check if triggers exist
# 2. Insert a test moisture reading
# 3. Verify if listener processed it
# 4. Check audit log for new entries
node scripts/test-trigger-listener.js
```

### Manual Testing
```bash
# 1. Start the service in one terminal
npm start

# 2. In another terminal, insert test data
psql -h 43.208.201.191 -U postgres -d sensor_data -c "
INSERT INTO public.moisture_readings
  (sensor_id, moisture_percent, timestamp, lat, lng)
VALUES
  ('0001-0001', 25.0, NOW(), 0, 0);
"

# 3. Check audit log
psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT * FROM water_control_smartfarm.valve_control_audit
ORDER BY created_at DESC LIMIT 5;
"

# 4. Check valve commands in MSSQL
# Connect to moonup.hopto.org MSSQL and check tb_valve_command_v2_test
```

---

## 5. Current Problems and Solutions

### Problem 1: Service Crashes with Errors
**Symptom:** Multiple `[object Object]` errors in control loops

**Possible Causes:**
1. Logger not serializing error objects properly
2. Control loop trying to access data that doesn't exist
3. Database connection issues in loops

**Solution:**
1. Check service logs with better error serialization
2. Debug control loop logic
3. Add try-catch with proper error logging

### Problem 2: No Active Listener Connections
**Symptom:** `pg_stat_activity` shows no smartfarm connections

**Possible Causes:**
1. Service crashed and disconnected
2. Listener using different app name
3. Connection to wrong database

**Solution:**
1. Restart service and immediately check connections
2. Verify listener is using correct database (sensor_data, not munbon_dev)

### Problem 3: Triggers Work but Listener Doesn't React
**Symptom:** Triggers fire but no audit logs created

**Possible Causes:**
1. Listener not running or crashed
2. Listener listening to wrong channel name
3. Control logic filtering out the readings

**Solution:**
1. Verify service is running: `ps aux | grep "node src/index.js"`
2. Check channel name matches: `sensor_evaluation_needed`
3. Check control thresholds are configured

---

## 6. Database Schema Reference

### sensor_data Database
```
public.moisture_readings
├── sensor_id (varchar)
├── moisture_percent (numeric)
├── timestamp (timestamptz)
├── lat (numeric)
└── lng (numeric)

public.water_level_readings
├── sensor_id (varchar)
├── level_cm (numeric)
├── timestamp (timestamptz)
├── lat (numeric)
└── lng (numeric)

water_control_smartfarm.valve_control_audit
├── id (serial)
├── plot_id (uuid)
├── sensor_id (varchar)
├── sensor_value (numeric)
├── decision_action (varchar) -- TURN_ON, TURN_OFF, NO_ACTION
├── valve_command_level (integer) -- 1=ON, 0=OFF
├── created_at (timestamptz)
└── ... (25+ more columns)
```

### munbon_dev Database
```
water_control_smartfarm.plot_configurations
├── plot_id (uuid)
├── crop_type (varchar)
├── control_mode (varchar) -- MOISTURE, AWD
├── created_at (timestamptz)
└── updated_at (timestamptz)

water_control_smartfarm.sensor_plot_mapping
├── sensor_id (varchar)
├── plot_id (uuid)
├── sensor_type (varchar) -- moisture, water_level
├── created_at (timestamptz)
└── updated_at (timestamptz)

water_control_smartfarm.control_thresholds
├── plot_id (uuid)
├── moisture_lower_threshold (numeric)
├── moisture_upper_threshold (numeric)
├── water_level_lower_threshold (numeric)
├── water_level_upper_threshold (numeric)
└── updated_at (timestamptz)
```

---

## 7. Next Steps

1. **FIX SERVICE ERRORS** - Debug and fix the control loop errors causing crashes
2. **RESTART SERVICE** - Get a clean service running without crashes
3. **TEST FLOW** - Run `test-trigger-listener.js` to verify end-to-end
4. **MONITOR** - Watch audit logs to confirm triggers are working
5. **DOCUMENT** - Update this file with test results

---

## 8. Quick Reference Commands

```bash
# Start service
npm start

# Check triggers
node scripts/test-trigger-listener.js

# Monitor status
node scripts/monitor-smartfarm-status.js

# View service logs
tail -f /path/to/service.log

# Insert test data
psql -h 43.208.201.191 -U postgres -d sensor_data -c "
INSERT INTO public.moisture_readings (sensor_id, moisture_percent, timestamp, lat, lng)
VALUES ('0001-0001', 25.0, NOW(), 0, 0);
"

# Check audit log
psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT plot_id, sensor_value, decision_action, valve_command_level, created_at
FROM water_control_smartfarm.valve_control_audit
ORDER BY created_at DESC LIMIT 10;
"
```

---

**Last Updated:** 2025-10-12
**Status:** Triggers working ✅, Listener partially working ⚠️, Needs debugging ❌
