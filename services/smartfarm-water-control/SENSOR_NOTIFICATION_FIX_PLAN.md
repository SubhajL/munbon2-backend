# Sensor Notification System Fix - Implementation Plan

## Expert Diagnosis Summary

**Root Causes Identified:**
1. ✅ Direct-to-Columnstore: OFF (confirmed safe)
2. ✅ Triggers exist on hypertable and propagate to chunks
3. ✅ session_replication_role: 'origin' (correct)
4. ✅ Server timeouts: disabled (0ms)
5. ⚠️ **Listener uses pooled connection** - should use dedicated client
6. ⚠️ **No idle_session_timeout override in session** - need explicit SET

## Immediate Fixes Required

### Fix #1: Replace Pooled Listener with Dedicated Client

**Current Code** (`src/services/sensorUpdateListener.js` line 25):
```javascript
this.client = await this.pool.connect();  // BAD: uses pool
```

**New Implementation**:
```javascript
// src/services/sensorUpdateListener.js
const { Client } = require('pg');

class SensorUpdateListener extends EventEmitter {
  constructor(connectionConfig, config = {}) {  // Take config, not pool
    super();
    this.connectionConfig = connectionConfig;
    this.client = null;
    // ... rest
  }

  async start() {
    if (this.isConnected) return;

    try {
      // Create dedicated client (NOT from pool)
      this.client = new Client({
        host: this.connectionConfig.host,
        port: this.connectionConfig.port,
        database: this.connectionConfig.database,
        user: this.connectionConfig.user,
        password: this.connectionConfig.password,
        keepAlive: true,
        statement_timeout: 0,
        query_timeout: 0,
        application_name: 'smartfarm-water-control-listener'
      });

      await this.client.connect();

      // CRITICAL: Set session timeout to 0
      await this.client.query("SET idle_session_timeout = 0");
      await this.client.query("SET idle_in_transaction_session_timeout = 0");

      await this.client.query('LISTEN sensor_evaluation_needed');

      this.client.on('notification', this.handleNotification.bind(this));
      this.client.on('error', this.handleError.bind(this));

      this.startHeartbeat();

      logger.info('Sensor update listener started (dedicated connection)');
    } catch (error) {
      logger.error({ error }, 'Failed to start sensor update listener');
      this.isConnected = false;
      this.cleanupClient();
      throw error;
    }
  }

  cleanupClient() {
    if (this.client) {
      try {
        this.client.removeAllListeners();
        this.client.end();  // Use end(), not release()
      } catch (error) {
        logger.debug({ error }, 'Error during client cleanup');
      } finally {
        this.client = null;
      }
    }
  }
}
```

**Update Caller** (`src/index.js` line 202):
```javascript
// OLD:
this.listener = new SensorUpdateListener(timescalePool, {...});

// NEW:
this.listener = new SensorUpdateListener(
  {
    host: config.timescale.host,
    port: config.timescale.port,
    database: config.timescale.database,
    user: config.timescale.user,
    password: config.timescale.password
  },
  {
    reconnectDelay: config.listener.reconnectDelay,
    debounceWindow: config.listener.debounceWindow,
  }
);
```

### Fix #2: Implement Outbox Pattern for Robustness

**Create Outbox Table**:
```sql
-- Run on sensor_data DB
CREATE TABLE IF NOT EXISTS water_control_smartfarm.readings_outbox (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  src_table TEXT NOT NULL,
  sensor_id TEXT NOT NULL,
  sensor_type TEXT NOT NULL,
  value NUMERIC NOT NULL,
  reading_time TIMESTAMPTZ NOT NULL,
  processed BOOLEAN NOT NULL DEFAULT FALSE,
  processed_at TIMESTAMPTZ
);

CREATE INDEX idx_readings_outbox_unprocessed 
ON water_control_smartfarm.readings_outbox(processed, ts) 
WHERE NOT processed;
```

**Update Trigger Function**:
```sql
CREATE OR REPLACE FUNCTION water_control_smartfarm.notify_sensor_reading()
RETURNS TRIGGER AS $$
DECLARE
  sensor_type_value TEXT;
  sensor_value NUMERIC;
  outbox_id BIGINT;
BEGIN
  IF TG_TABLE_NAME = 'moisture_readings' THEN
    sensor_type_value := 'moisture';
    sensor_value := NEW.moisture_surface_pct;
  ELSIF TG_TABLE_NAME = 'water_level_readings' THEN
    sensor_type_value := 'water_level';
    sensor_value := NEW.water_level_cm;
  ELSE
    RETURN NEW;
  END IF;

  -- Insert to outbox (durable)
  INSERT INTO water_control_smartfarm.readings_outbox(
    src_table, sensor_id, sensor_type, value, reading_time
  )
  VALUES (
    TG_TABLE_NAME, NEW.sensor_id, sensor_type_value, sensor_value, NEW.time
  )
  RETURNING id INTO outbox_id;

  -- Send lightweight notification with just the ID
  PERFORM pg_notify('sensor_evaluation_needed', 
    json_build_object('outbox_id', outbox_id, 'type', sensor_type_value)::text
  );

  RETURN NEW;
EXCEPTION
  WHEN OTHERS THEN
    -- Log but don't block insert
    RAISE WARNING 'Sensor notification failed for %: %', NEW.sensor_id, SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**Update Service to Fetch from Outbox** (`src/services/realtimeControlService.js`):
```javascript
async handleSensorReading(event) {
  // If event has outbox_id, fetch from outbox
  if (event.outbox_id) {
    const result = await this.repository.pool.query(
      `SELECT sensor_id, sensor_type, value, reading_time as timestamp
       FROM water_control_smartfarm.readings_outbox
       WHERE id = $1 AND NOT processed`,
      [event.outbox_id]
    );

    if (result.rows.length === 0) {
      logger.warn({ outbox_id: event.outbox_id }, 'Outbox entry already processed or not found');
      return;
    }

    event = {
      sensorId: result.rows[0].sensor_id,
      sensorType: result.rows[0].sensor_type,
      value: parseFloat(result.rows[0].value),
      timestamp: result.rows[0].timestamp
    };
  }

  // ... rest of handleSensorReading logic ...

  // Mark as processed at the end
  if (event.outbox_id) {
    await this.repository.pool.query(
      `UPDATE water_control_smartfarm.readings_outbox
       SET processed = TRUE, processed_at = NOW()
       WHERE id = $1`,
      [event.outbox_id]
    );
  }
}
```

### Fix #3: Add Periodic Outbox Cleanup Job

```javascript
// src/jobs/outboxCleanup.js
async function cleanupOutbox(repository) {
  const result = await repository.pool.query(`
    DELETE FROM water_control_smartfarm.readings_outbox
    WHERE processed = TRUE 
      AND processed_at < NOW() - INTERVAL '24 hours'
    RETURNING id
  `);
  
  logger.info({ count: result.rowCount }, 'Cleaned up processed outbox entries');
}

// Schedule in src/index.js
cron.schedule('0 */6 * * *', async () => {  // Every 6 hours
  try {
    await cleanupOutbox(this.services.timescaleRepository);
  } catch (error) {
    logger.error({ error }, 'Outbox cleanup failed');
  }
});
```

## Testing Plan

### Test 1: Verify Trigger Fires
```sql
-- Should see entry in outbox
INSERT INTO moisture_readings (sensor_id, moisture_surface_pct, time)
VALUES ('TEST-001', 77.7, NOW());

SELECT * FROM water_control_smartfarm.readings_outbox 
WHERE sensor_id = 'TEST-001' 
ORDER BY ts DESC LIMIT 1;
```

### Test 2: Verify Listener Stays Connected
```sql
-- Check after 15 minutes
SELECT pid, application_name, backend_start, state, query
FROM pg_stat_activity
WHERE application_name = 'smartfarm-water-control-listener';
-- Should show: idle | LISTEN sensor_evaluation_needed
```

### Test 3: End-to-End Flow
```sql
INSERT INTO moisture_readings (sensor_id, moisture_surface_pct, time)
VALUES ('0001-0001', 78.5, NOW());

-- Wait 5 seconds, then check:
SELECT plot_id, sensor_id, reading_value, updated_at
FROM munbon_dev.water_control_smartfarm.sensor_plot_readings
WHERE sensor_id = '00000001'
ORDER BY updated_at DESC LIMIT 1;
-- Should show fresh updated_at timestamp
```

## Rollback Plan

If issues occur:
1. Keep old pooled approach in git branch
2. Can quickly revert to polling mechanism:
   ```javascript
   setInterval(async () => {
     const unprocessed = await fetchUnprocessedFromOutbox();
     for (const entry of unprocessed) {
       await handleSensorReading(entry);
     }
   }, 5000);  // Poll every 5 seconds
   ```

## Alternative: Statement-Level Trigger (Future Enhancement)

For high-volume inserts, switch to statement-level trigger:
```sql
CREATE OR REPLACE FUNCTION water_control_smartfarm.notify_sensor_reading_stmt()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO water_control_smartfarm.readings_outbox(
    src_table, sensor_id, sensor_type, value, reading_time
  )
  SELECT 
    TG_TABLE_NAME,
    NEW_TABLE.sensor_id,
    CASE WHEN TG_TABLE_NAME = 'moisture_readings' 
         THEN 'moisture' ELSE 'water_level' END,
    COALESCE(NEW_TABLE.moisture_surface_pct, NEW_TABLE.water_level_cm),
    NEW_TABLE.time
  FROM NEW TABLE AS NEW_TABLE;

  PERFORM pg_notify('sensor_evaluation_needed',
    json_build_object('type', 'batch', 'table', TG_TABLE_NAME)::text);

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Replace row-level trigger
DROP TRIGGER trg_moisture_readings_notify ON moisture_readings;
CREATE TRIGGER trg_moisture_stmt
AFTER INSERT ON moisture_readings
REFERENCING NEW TABLE AS NEW_TABLE
FOR EACH STATEMENT
EXECUTE FUNCTION water_control_smartfarm.notify_sensor_reading_stmt();
```

## Priority Order

1. **CRITICAL**: Implement Fix #1 (dedicated client) - do this first
2. **HIGH**: Implement Fix #2 (outbox pattern) - provides durability
3. **MEDIUM**: Add monitoring for listener connection health
4. **LOW**: Optimize with statement-level trigger if needed

## Success Criteria

- [ ] Listener connection stays alive > 1 hour
- [ ] Real INSERT statements trigger notifications
- [ ] sensor_plot_readings updates within 5 seconds of INSERT
- [ ] No lost notifications during brief disconnections (outbox provides replay)
- [ ] Heartbeat logs show successful pings every 30s
