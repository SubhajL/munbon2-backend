# Outbox Pattern Implementation

## Overview

Implemented a robust outbox pattern for durable sensor notification delivery to ensure zero message loss even during connection drops or system failures.

## Architecture

### Components

1. **Outbox Table** (`water_control_smartfarm.sensor_readings_outbox`)
   - Stores sensor reading events durably in PostgreSQL
   - Schema:
     - `id` (SERIAL PRIMARY KEY)
     - `sensor_id` (TEXT NOT NULL)
     - `sensor_type` (TEXT NOT NULL)
     - `value` (DOUBLE PRECISION NOT NULL)
     - `timestamp` (TIMESTAMPTZ NOT NULL)
     - `created_at` (TIMESTAMPTZ DEFAULT NOW())
     - `processed_at` (TIMESTAMPTZ)
   - Indexed on `created_at` for efficient polling of unprocessed entries

2. **Repository Methods** (`TimescaleRepository`)
   - `fetchUnprocessedOutboxEntries(db, limit)` - Fetches unprocessed outbox entries ordered by creation time
   - `markOutboxEntryProcessed(db, outboxId, processedAt)` - Marks entry as processed
   - `insertOutboxEntry(db, { sensorId, sensorType, value, timestamp })` - Inserts new outbox entry

3. **OutboxPoller Service**
   - Periodically polls outbox table for unprocessed entries
   - Processes each entry via `RealtimeControlService.handleSensorReading()`
   - Marks successfully processed entries with timestamp
   - Continues processing remaining entries even if individual entries fail
   - Configurable:
     - `pollIntervalMs` (default: 5000ms)
     - `batchSize` (default: 100 entries)

### Benefits

1. **Durability** - Events persisted in database survive connection drops
2. **Replay** - Failed entries remain unprocessed and can be retried
3. **Ordering** - Entries processed in chronological order (oldest first)
4. **Resilience** - Individual entry failures don't block subsequent processing
5. **Observability** - Unprocessed entries visible via SQL queries

## Implementation Files

### Database Schema
- `/Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control/src/config/database.js`
  - Added outbox table creation in `createSchemas()`

### Repository Layer
- `/Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control/src/repository/timescaleRepository.js`
  - Added outbox CRUD methods

### Service Layer
- `/Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control/src/services/outboxPoller.js`
  - New service for polling and processing outbox entries

### Tests
- `/Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control/src/repository/__tests__/timescaleRepository.outbox.spec.js` (8 tests)
- `/Users/subhajlimanond/dev/munbon2-backend-smartfarm/services/smartfarm-water-control/src/services/__tests__/outboxPoller.spec.js` (14 tests)

## Test Coverage

### Repository Tests
- ✅ fetchUnprocessedOutboxEntries returns unprocessed rows only
- ✅ fetchUnprocessedOutboxEntries respects limit parameter
- ✅ fetchUnprocessedOutboxEntries returns oldest entries first
- ✅ fetchUnprocessedOutboxEntries returns empty array when no unprocessed entries
- ✅ markOutboxEntryProcessed sets processed_at timestamp
- ✅ markOutboxEntryProcessed is idempotent
- ✅ markOutboxEntryProcessed uses current time when processedAt not provided
- ✅ insertOutboxEntry creates new outbox row

### Service Tests
- ✅ constructor initializes with provided configuration
- ✅ constructor uses default values when not provided
- ✅ start() begins polling at configured interval
- ✅ start() does not start multiple intervals
- ✅ stop() clears polling interval
- ✅ stop() sets isStopped flag
- ✅ stop() handles stop when not started
- ✅ poll() fetches and processes unprocessed entries
- ✅ poll() marks entries processed after successful handling
- ✅ poll() does not mark entries processed on error
- ✅ poll() handles empty outbox gracefully
- ✅ poll() processes entries in order
- ✅ poll() respects batchSize configuration
- ✅ poll() continues processing remaining entries after one fails

## Next Steps

1. **Database Triggers** - Create triggers on `moisture_readings` and `water_level_readings` to insert into outbox table on new readings
2. **Integration** - Wire up `OutboxPoller` in main application entry point
3. **Monitoring** - Add metrics for:
   - Outbox entry processing rate
   - Outbox backlog size
   - Processing latency
   - Error rate
4. **Cleanup** - Implement periodic cleanup of processed entries older than retention period
5. **Alerting** - Alert when outbox backlog exceeds threshold

## Usage Example

```javascript
const { TimescaleRepository } = require('./repository/timescaleRepository');
const OutboxPoller = require('./services/outboxPoller');
const { RealtimeControlService } = require('./services/realtimeControlService');

// Initialize components
const repository = new TimescaleRepository(pool);
const realtimeControlService = new RealtimeControlService(/* ... */);

// Create and start outbox poller
const outboxPoller = new OutboxPoller({
  repository,
  realtimeControlService,
  pollIntervalMs: 5000,
  batchSize: 100,
  logger,
  pool
});

outboxPoller.start();

// Graceful shutdown
process.on('SIGTERM', () => {
  outboxPoller.stop();
});
```

## Monitoring Queries

```sql
-- Check outbox backlog
SELECT COUNT(*) FROM water_control_smartfarm.sensor_readings_outbox 
WHERE processed_at IS NULL;

-- View oldest unprocessed entries
SELECT * FROM water_control_smartfarm.sensor_readings_outbox 
WHERE processed_at IS NULL 
ORDER BY created_at ASC 
LIMIT 10;

-- Processing rate (last hour)
SELECT 
  DATE_TRUNC('minute', processed_at) AS minute,
  COUNT(*) AS processed_count
FROM water_control_smartfarm.sensor_readings_outbox 
WHERE processed_at > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;
```
