# TDD Implementation Plan: Fix Sensor Notification LISTEN Connection

## Overview

Replace pooled PostgreSQL connection with dedicated `pg.Client` for LISTEN/NOTIFY to prevent connection recycling that drops the listener after idle timeouts. The dedicated client will explicitly set session timeouts to 0 and use TCP keepalive.

**Root Cause**: `pool.connect()` returns clients that get recycled by the pool after queries, incompatible with long-lived LISTEN connections.

**Solution**: Use dedicated `pg.Client` instance that lives for the entire service lifetime.

---

## Files to Modify

### 1. `src/services/sensorUpdateListener.js` (MAJOR CHANGES)
- Change from pooled connection to dedicated Client
- Update constructor signature
- Modify `start()` to create Client and set session timeouts
- Change `cleanupClient()` to call `end()` instead of `release()`
- Update `stop()` similarly

### 2. `src/index.js` (MINOR CHANGE)
- Update `setupSensorListener()` to pass connection config instead of pool

### 3. `src/services/sensorUpdateListener.spec.js` (NEW FILE)
- Unit tests for listener behavior

---

## Implementation Steps (TDD)

### Phase 1: Update SensorUpdateListener

#### Function: `constructor(connectionConfig, options)`
**What it does**: Accept DB connection parameters instead of pool; store config for creating dedicated Client during `start()`.

**Changes**:
- Replace `pool` parameter with `connectionConfig` object containing `{host, port, database, user, password}`
- Remove `this.pool` assignment
- Store `this.connectionConfig = connectionConfig`

#### Function: `async start()`
**What it does**: Create dedicated Client with keepalive and session timeout overrides; establish LISTEN connection that persists for service lifetime.

**Changes**:
- Import `const { Client } = require('pg')`
- Replace `this.client = await this.pool.connect()` with:
  ```javascript
  this.client = new Client({
    ...this.connectionConfig,
    keepAlive: true,
    statement_timeout: 0,
    query_timeout: 0,
    application_name: 'smartfarm-water-control-listener'
  });
  await this.client.connect();
  ```
- Add session timeout overrides:
  ```javascript
  await this.client.query("SET idle_session_timeout = 0");
  await this.client.query("SET idle_in_transaction_session_timeout = 0");
  ```
- Rest stays same (LISTEN, event handlers, heartbeat)

#### Function: `cleanupClient()`
**What it does**: Terminate dedicated client connection properly when shutting down or reconnecting.

**Changes**:
- Replace `this.client.release()` with `this.client.end()`
- `release()` returns to pool (wrong), `end()` closes connection (correct)

#### Function: `async stop()`
**What it does**: Gracefully shutdown listener by unlisten, cleanup, and ending connection.

**Changes**:
- Replace `this.client.release()` with `this.client.end()`

---

### Phase 2: Update Index.js Caller

#### Function: `async setupSensorListener(timescalePool)`
**Signature change**: `async setupSensorListener()`

**What it does**: Initialize listener with connection config instead of passing pool.

**Changes**:
- Remove `timescalePool` parameter (not used anymore)
- Update listener instantiation:
  ```javascript
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
- Update call site (line 174): `await this.setupSensorListener();`

---

## Test Plan

### Unit Tests: `src/services/__tests__/sensorUpdateListener.spec.js`

#### Test: `start() creates dedicated Client with correct config`
**Covers**: Client instantiation, keepalive, timeouts set.

#### Test: `start() sets session idle timeouts to zero`
**Covers**: Session-level timeout override queries executed.

#### Test: `handleNotification() emits sensor_reading event`
**Covers**: Notification parsing and event emission logic.

#### Test: `validatePayload() rejects invalid payloads`
**Covers**: Required fields, type checking, empty strings.

#### Test: `handleNotification() debounces duplicate notifications`
**Covers**: Duplicate detection by sensor_id + timestamp.

#### Test: `cleanupClient() calls client.end() not release()`
**Covers**: Proper connection termination for dedicated client.

#### Test: `stop() unlistens and ends connection`
**Covers**: UNLISTEN query, removeAllListeners, client.end().

#### Test: `heartbeat detects failed connection and reconnects`
**Covers**: Heartbeat query failure triggers handleError and scheduleReconnect.

#### Test: `scheduleReconnect() retries after delay`
**Covers**: Timeout scheduling and start() retry logic.

### Integration Test: `src/services/__tests__/sensorUpdateListener.integration.spec.js`

#### Test: `listener receives real pg_notify from database`
**Covers**: End-to-end NOTIFY delivery to Node process.

#### Test: `listener connection persists beyond 5 minutes`
**Covers**: Long-lived connection stability (run with timeout).

#### Test: `listener reconnects after connection drop`
**Covers**: Error recovery and automatic reconnection.

---

## Manual Testing Checklist

1. **Listener stays connected > 15 minutes**
   ```sql
   -- Run every minute for 15 minutes
   SELECT pid, application_name, backend_start, state
   FROM pg_stat_activity
   WHERE application_name = 'smartfarm-water-control-listener';
   ```
   Expected: Same `pid` throughout, state = 'idle'

2. **INSERT triggers notification delivery**
   ```sql
   INSERT INTO moisture_readings (sensor_id, moisture_surface_pct, time)
   VALUES ('0001-0001', 79.5, NOW());
   ```
   Expected: Service logs show "Received sensor evaluation notification" within 1 second

3. **sensor_plot_readings updates**
   ```sql
   SELECT plot_id, sensor_id, reading_value, updated_at
   FROM munbon_dev.water_control_smartfarm.sensor_plot_readings
   WHERE sensor_id = '00000001'
   ORDER BY updated_at DESC LIMIT 1;
   ```
   Expected: `updated_at` matches insert time, `reading_value` = 79.5

4. **Heartbeat logs appear every 30s**
   ```bash
   tail -f /tmp/service.log | grep "heartbeat"
   ```
   Expected: Regular "Listener heartbeat successful" entries

5. **Service restart recovers listener**
   - Stop service
   - Wait 30 seconds
   - Start service
   - Verify listener reconnects and works

---

## Success Criteria

- [ ] `SensorUpdateListener` uses `Client` instead of pooled connection
- [ ] Session timeouts explicitly set to 0 in `start()`
- [ ] TCP keepalive enabled in Client config
- [ ] `cleanupClient()` and `stop()` call `client.end()` not `release()`
- [ ] All unit tests pass
- [ ] Integration test confirms notifications received
- [ ] Manual test: listener stays connected > 15 minutes
- [ ] Manual test: INSERT → notification → sensor_plot_readings update < 5s
- [ ] No "Sensor not mapped" or "Failed to upsert" warnings in logs

---

## Rollback Strategy

If critical issues arise:
1. Revert changes to `sensorUpdateListener.js` and `index.js`
2. Original pooled approach available in git history
3. Temporarily disable listener via `ENABLE_DB_LISTENER=false` env var

---

## Notes

- Follow BP-1: This plan confirmed with user before implementation
- Follow C-1 (TDD): Write tests before implementation
- Follow C-2: Use existing vocabulary (`start`, `stop`, `handleNotification`)
- Follow C-4: Keep functions simple and testable
- Follow T-1: Unit tests colocated in `__tests__/` directory
- Follow T-3: Separate unit tests (mocked Client) from integration tests (real DB)
