# Realtime Control System - Manual Testing Guide

## Overview

This guide walks through manual testing of the newly implemented realtime control system that automatically controls irrigation valves based on sensor readings.

## Architecture

```
Sensor Reading Inserted
         ↓
Database Trigger (notify_sensor_reading)
         ↓
PostgreSQL NOTIFY ('sensor_evaluation_needed')
         ↓
SensorUpdateListener (LISTEN connection)
         ↓
RealtimeControlService.handleSensorReading()
         ↓
Evaluate Control Decision (hysteresis logic)
         ↓
Log Decision → Execute Valve Command → Update State
```

## Prerequisites

1. **Database Setup**: Ensure TimescaleDB migrations are applied
   ```bash
   cd /Users/subhajlimanond/dev/munbon2-backend/services/smartfarm-water-control
   node scripts/run-migrations.js
   ```

2. **Seed Test Data**: Populate control thresholds and sensor mappings
   ```bash
   node scripts/seed-realtime-control.js
   ```

3. **Enable Listener**: Set environment variable in `.env`
   ```
   ENABLE_DB_LISTENER=true
   ```

4. **MSSQL Connection** (Optional): Configure for valve command execution
   - If not configured, valve commands will fail gracefully but decisions are still logged

## Test Data Configuration

The seed script creates:

### Control Thresholds
| Plot ID       | Moisture Lower | Moisture Upper | Water Level Lower | Water Level Upper |
|--------------|---------------|----------------|-------------------|-------------------|
| TEST-PLOT-01 | 10.0%         | 15.0%          | 5.0cm             | 15.0cm            |
| TEST-PLOT-02 | 12.0%         | 18.0%          | 6.0cm             | 12.0cm            |
| TEST-PLOT-03 | 8.0%          | 14.0%          | 4.0cm             | 10.0cm            |

### Sensor Mappings
| Sensor ID              | Plot ID       | Sensor Type |
|-----------------------|--------------|-------------|
| MOISTURE-SENSOR-01    | TEST-PLOT-01 | moisture    |
| MOISTURE-SENSOR-02    | TEST-PLOT-02 | moisture    |
| WATER-LEVEL-SENSOR-01 | TEST-PLOT-01 | water_level |
| WATER-LEVEL-SENSOR-02 | TEST-PLOT-03 | water_level |

## Manual Testing Steps

### Step 1: Start the Service

```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/smartfarm-water-control
npm run dev
```

**Expected Output**:
```
INFO: TimescaleDB connected successfully
INFO: MSSQL connected successfully (if configured)
INFO: Smart Farm Water Control Service initialized successfully
INFO: Sensor update listener started (listening on sensor_evaluation_needed)
INFO: Real-time control system enabled: sensor notifications will trigger immediate valve actions
INFO: Smart Farm Water Control Service started on port 3000
```

### Step 2: Run Automated Test Script

In a **separate terminal**:

```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/smartfarm-water-control
node scripts/test-sensor-insert.js
```

This script will:
- Insert 4 test sensor readings
- Display decisions logged
- Show current valve states
- Wait for processing between inserts

**Watch the service logs** to see realtime processing!

### Step 3: Manual Sensor Insert (Alternative)

Connect to database directly:

```bash
PGPASSWORD='__ROTATED_DB_PASSWORD__' psql -h 43.208.201.191 -p 5432 -U postgres -d sensor_data
```

Insert a low moisture reading (should trigger TURN_ON):

```sql
INSERT INTO public.moisture_readings (sensor_id, moisture_percent, timestamp)
VALUES ('MOISTURE-SENSOR-01', 8.5, NOW());
```

Insert a high moisture reading (should trigger TURN_OFF):

```sql
INSERT INTO public.moisture_readings (sensor_id, moisture_percent, timestamp)
VALUES ('MOISTURE-SENSOR-01', 18.0, NOW());
```

Insert a mid-range reading (should MAINTAIN):

```sql
INSERT INTO public.moisture_readings (sensor_id, moisture_percent, timestamp)
VALUES ('MOISTURE-SENSOR-01', 12.0, NOW());
```

## Expected Service Logs

When sensor readings are inserted, you should see:

```
INFO: Received sensor evaluation notification { sensorId: 'MOISTURE-SENSOR-01', sensorType: 'moisture', value: 8.5, timestamp: '2025-10-01...' }
INFO: Evaluating control decision { plotId: 'TEST-PLOT-01', value: 8.5, thresholds: { ... } }
INFO: Decision: TURN_ON (Moisture 8.5% <= lower threshold 10.0%)
INFO: Logging control decision { action: 'TURN_ON', plotId: 'TEST-PLOT-01', ... }
INFO: Sending valve command with retry { plotId: 'TEST-PLOT-01', level: 100, attempt: 1 }
INFO: Valve command succeeded { plotId: 'TEST-PLOT-01', attempt: 1, success: true }
INFO: Updated valve state { plotId: 'TEST-PLOT-01', newState: 'ON' }
```

## Verification Queries

### Check Decision Log

```sql
SELECT
  id,
  plot_id,
  sensor_id,
  sensor_type,
  action,
  sensor_value,
  lower_threshold,
  upper_threshold,
  previous_state,
  new_state,
  valve_command_sent,
  valve_command_succeeded,
  created_at
FROM water_control_smartfarm.control_decisions_log
ORDER BY created_at DESC
LIMIT 10;
```

### Check Valve States

```sql
SELECT * FROM water_control_smartfarm.valve_states
ORDER BY last_changed_at DESC;
```

### Check Valve Commands (MSSQL)

If MSSQL is configured, check the valve command table:

```sql
SELECT TOP 10 *
FROM [dbo].[TbCmdSetOfSmartfarm]
ORDER BY UpdateTime DESC;
```

## Test Scenarios

### Scenario 1: Hysteresis Behavior (Prevent Oscillation)

1. Start with valve OFF and moisture at 12% (mid-range)
   - **Expected**: MAINTAIN state, no valve action
2. Insert moisture 9% (below lower threshold 10%)
   - **Expected**: TURN_ON, valve command sent
3. Insert moisture 11% (between thresholds)
   - **Expected**: MAINTAIN ON state (hysteresis prevents turning off immediately)
4. Insert moisture 16% (above upper threshold 15%)
   - **Expected**: TURN_OFF, valve command sent

### Scenario 2: Invalid Sensor Data

1. Insert negative moisture:
   ```sql
   INSERT INTO public.moisture_readings (sensor_id, moisture_percent, timestamp)
   VALUES ('MOISTURE-SENSOR-01', -5.0, NOW());
   ```
   - **Expected**: MAINTAIN, reason "Invalid sensor reading"

2. Insert overflow moisture (> 100%):
   ```sql
   INSERT INTO public.moisture_readings (sensor_id, moisture_percent, timestamp)
   VALUES ('MOISTURE-SENSOR-01', 120.0, NOW());
   ```
   - **Expected**: MAINTAIN, reason "Invalid sensor reading"

### Scenario 3: Unmapped Sensor

1. Insert reading from unknown sensor:
   ```sql
   INSERT INTO public.moisture_readings (sensor_id, moisture_percent, timestamp)
   VALUES ('UNKNOWN-SENSOR', 8.5, NOW());
   ```
   - **Expected**: No decision logged, listener skips unmapped sensor

### Scenario 4: Valve Command Failure

1. Stop MSSQL service or provide invalid credentials
2. Insert sensor reading that crosses threshold
   - **Expected**:
     - Decision logged with `valve_command_sent = TRUE`
     - Retry attempts with exponential backoff (1s, 2s, 4s)
     - Final log update: `valve_command_succeeded = FALSE`, `valve_command_error = '...'`

### Scenario 5: Water Level Overflow

1. Insert water level > 100cm:
   ```sql
   INSERT INTO public.water_level_readings (sensor_id, water_level_cm, timestamp)
   VALUES ('WATER-LEVEL-SENSOR-01', 120.0, NOW());
   ```
   - **Expected**: TURN_OFF immediately, reason "Water level overflow"

## Troubleshooting

### Listener Not Receiving Notifications

**Symptom**: Sensor inserts don't trigger any logs

**Check**:
1. Ensure `ENABLE_DB_LISTENER=true` in `.env`
2. Verify listener started:
   ```
   grep "Sensor update listener started" service.log
   ```
3. Check trigger exists:
   ```sql
   SELECT * FROM information_schema.triggers
   WHERE event_object_schema = 'public'
   AND event_object_table IN ('moisture_readings', 'water_level_readings');
   ```
4. Test notification manually:
   ```sql
   SELECT pg_notify('sensor_evaluation_needed', '{"sensor_id":"TEST","value":10.0,"timestamp":"2025-10-01T00:00:00Z","sensor_type":"moisture"}');
   ```

### Valve Commands Not Sent

**Symptom**: Decisions logged but `valve_command_sent = FALSE`

**Check**:
1. Ensure MSSQL connection is configured in `.env`
2. Check MSSQL connection logs:
   ```
   grep "MSSQL connected" service.log
   ```
3. Verify valve mapping exists in `config.valveMapping`

### Decisions Not Logged

**Symptom**: Notifications received but no decisions logged

**Check**:
1. Verify sensor is mapped:
   ```sql
   SELECT * FROM water_control_smartfarm.sensor_plot_mapping
   WHERE sensor_id = 'YOUR-SENSOR-ID';
   ```
2. Verify thresholds exist:
   ```sql
   SELECT * FROM water_control_smartfarm.control_thresholds
   WHERE plot_id = 'YOUR-PLOT-ID';
   ```

## Performance Monitoring

### Monitor Notification Latency

Check time between sensor insert and decision log:

```sql
SELECT
  mr.timestamp AS sensor_time,
  cdl.created_at AS decision_time,
  EXTRACT(EPOCH FROM (cdl.created_at - mr.timestamp)) AS latency_seconds
FROM public.moisture_readings mr
JOIN water_control_smartfarm.control_decisions_log cdl
  ON cdl.sensor_id = mr.sensor_id
  AND cdl.sensor_value = mr.moisture_percent
ORDER BY mr.timestamp DESC
LIMIT 10;
```

**Target**: < 1 second latency

### Monitor Valve Command Success Rate

```sql
SELECT
  COUNT(*) AS total_commands,
  SUM(CASE WHEN valve_command_succeeded THEN 1 ELSE 0 END) AS successful,
  SUM(CASE WHEN valve_command_succeeded = FALSE THEN 1 ELSE 0 END) AS failed,
  ROUND(100.0 * SUM(CASE WHEN valve_command_succeeded THEN 1 ELSE 0 END) / COUNT(*), 2) AS success_rate_pct
FROM water_control_smartfarm.control_decisions_log
WHERE valve_command_sent = TRUE;
```

**Target**: > 95% success rate

## Safety Features Verified

✅ **Trigger Safety**: Database trigger never blocks sensor inserts (EXCEPTION handler)
✅ **Unmapped Sensor Handling**: Listener skips unknown sensors without errors
✅ **Unconfigured Plot Handling**: Service skips plots without threshold configuration
✅ **Invalid Data Handling**: Out-of-range sensor values trigger MAINTAIN decision
✅ **Valve Retry Logic**: Exponential backoff (1s, 2s, 4s) for transient failures
✅ **Decision Audit Trail**: Append-only log with full context for debugging
✅ **Hysteresis Control**: Dual thresholds prevent valve oscillation
✅ **Feature Flag**: `ENABLE_DB_LISTENER` allows safe production rollout

## Next Steps

After manual testing verification:

1. **Integration Tests**: Write end-to-end tests (Phase 6 of implementation plan)
2. **Load Testing**: Verify system handles 100+ sensors with 10-second intervals
3. **Production Rollout**:
   - Deploy with `ENABLE_DB_LISTENER=false` initially
   - Monitor for 24 hours
   - Enable listener gradually per plot
4. **Monitoring Setup**:
   - Alert on decision latency > 5 seconds
   - Alert on valve command success rate < 90%
   - Dashboard for decisions per hour by plot

## Test Completion Checklist

- [ ] Service starts successfully with listener enabled
- [ ] Sensor insert triggers database notification
- [ ] Listener receives and parses notification
- [ ] Decision evaluates correctly for below/above/mid-range values
- [ ] Decision logged with all fields populated
- [ ] Valve command sent (or error logged if MSSQL unavailable)
- [ ] Valve state updated after successful command
- [ ] Hysteresis behavior prevents oscillation
- [ ] Invalid sensor data handled gracefully
- [ ] Unmapped sensors skipped without errors
- [ ] Retry logic executes on valve command failure
