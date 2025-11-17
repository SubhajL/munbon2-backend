# Smart Farm Control Service - Fixing Guide

## Current Status

**Service State:** Running but with errors
- ✅ Service starts successfully
- ✅ Connects to all databases (sensor_data, munbon_dev, MSSQL)
- ✅ Loads 4 plot configurations from database
- ✅ Listener connects to `sensor_evaluation_needed` channel
- ❌ Control loops run but throw 8 errors per loop (2 per plot × 4 plots)
- ❌ Logger displays `[object Object]` instead of readable error messages
- ❌ Service eventually crashes after hours of running

## Root Cause Analysis

### Issue 1: Logger Not Displaying Error Objects
**Problem:** Winston's `simple()` console format doesn't expand Error objects properly

**Evidence:** Logs show `[object Object]` for all errors

**Fix Required:**
- Replace `winston.format.simple()` with custom `printf` format
- Custom format should check for `error` property and display `error.message` and `error.stack`

### Issue 2: Control Loop Has No Error Handling
**Problem:** `runControlLoop()` and `runPlanningLoop()` don't catch per-plot errors

**Evidence:** 8 errors per loop execution (2 operations × 4 plots)

**Fix Required:**
- Wrap each plot processing in try-catch
- Log errors with plot context
- Continue processing remaining plots on failure

### Issue 3: Missing Data Validation
**Problem:** Code assumes sensor data always exists and is fresh

**Likely Causes of Errors:**
1. `sensorData.getSensorReading()` returns null (no data)
2. Thresholds not configured for some plots
3. Sensor readings are stale (beyond freshness window)
4. plotConfig missing required fields

**Fix Required:**
- Add null checks before accessing data
- Validate data freshness
- Return early with warning logs for missing data

### Issue 4: MSSQL Pool May Be Null
**Problem:** Service gracefully handles MSSQL connection failure at startup, but valve command service may not handle null pool

**Fix Required:**
- Add null check in `ValveCommandService.sendCommand()`
- Return graceful error instead of throwing
- Log warning about unavailable MSSQL

## Detailed Fix Implementation

### Fix 1: Logger (src/utils/logger.js)

```javascript
const winston = require('winston');
const path = require('path');

const logLevel = process.env.LOG_LEVEL || 'info';

// Custom format to properly display errors
const consoleFormat = winston.format.printf(({ level, message, timestamp, service, error, ...meta }) => {
  let logMessage = `${level}: ${message}`;

  // Display error properly
  if (error && error instanceof Error) {
    logMessage += `\n  Error: ${error.message}`;
    if (error.stack) {
      logMessage += `\n  Stack: ${error.stack.split('\n').slice(0, 3).join('\n')}`;
    }
  }

  // Display metadata
  const metaKeys = Object.keys(meta).filter(key => !['timestamp', 'service'].includes(key));
  if (metaKeys.length > 0) {
    logMessage += ` ${JSON.stringify(meta)}`;
  }

  return logMessage;
});

const logger = winston.createLogger({
  level: logLevel,
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'smartfarm-water-control' },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        consoleFormat
      )
    })
  ]
});

// Add file transport in production
if (process.env.NODE_ENV === 'production') {
  logger.add(
    new winston.transports.File({
      filename: path.join('logs', 'error.log'),
      level: 'error'
    })
  );
  logger.add(
    new winston.transports.File({
      filename: path.join('logs', 'combined.log')
    })
  );
}

module.exports = logger;
```

### Fix 2: Control Loop (src/controllers/waterController.js)

**Add after line 224 (in runControlLoop method):**

```javascript
async runControlLoop() {
  try {
    logger.info('Starting control loop');

    const plots = this.config.plots;
    let successCount = 0;
    let errorCount = 0;

    // Process each plot independently with error handling
    for (const plotConfig of plots) {
      try {
        await this.processPlot(plotConfig);
        successCount++;
      } catch (error) {
        errorCount++;
        logger.error(
          {
            error,
            plotId: plotConfig.plotId,
            sensorId: plotConfig.moistureSensorId
          },
          `Failed to process plot ${plotConfig.plotId.substring(0,8)}`
        );
        // Continue to next plot
      }
    }

    logger.info(`Control loop completed: ${successCount} succeeded, ${errorCount} failed`);
  } catch (error) {
    logger.error({ error }, 'Control loop failed');
  }
}
```

**Add after line 206 (in runPlanningLoop method):**

```javascript
async runPlanningLoop() {
  try {
    logger.info('Starting planning loop');

    const plots = this.config.plots;
    let successCount = 0;
    let errorCount = 0;

    for (const plotConfig of plots) {
      try {
        await this.planPlot(plotConfig);
        successCount++;
      } catch (error) {
        errorCount++;
        logger.error(
          { error, plotId: plotConfig.plotId },
          `Failed to plan plot ${plotConfig.plotId.substring(0,8)}`
        );
        // Continue to next plot
      }
    }

    logger.info(`Planning loop completed: ${successCount} succeeded, ${errorCount} failed`);
  } catch (error) {
    logger.error({ error }, 'Planning loop failed');
  }
}
```

### Fix 3: Data Validation (src/controllers/waterController.js)

**Update processPlot method (lines 17-88) to add validation:**

```javascript
async processPlot(plotConfig) {
  try {
    const { plotId, moistureSensorId } = plotConfig;

    // Validate plot has sensor ID
    if (!moistureSensorId) {
      logger.warn({ plotId }, 'Plot has no moisture sensor configured, skipping');
      return null;
    }

    // Get control mode from database
    const controlMode = this.controlMode.getMode(plotId);

    if (!controlMode) {
      logger.warn({ plotId }, 'No control mode configured, skipping');
      return null;
    }

    logger.info({ plotId, controlMode }, 'Processing plot');

    // Get current sensor reading
    const sensorReading = await this.sensorData.getSensorReading(moistureSensorId);

    if (!sensorReading) {
      logger.warn({ plotId, sensorId: moistureSensorId }, 'No sensor reading available');
      return null;
    }

    // Validate sensor reading freshness (within last 15 minutes)
    const readingAge = Date.now() - new Date(sensorReading.timestamp).getTime();
    const maxAge = 15 * 60 * 1000; // 15 minutes
    if (readingAge > maxAge) {
      logger.warn(
        { plotId, sensorId: moistureSensorId, ageMinutes: Math.round(readingAge / 60000) },
        'Sensor reading is stale, skipping'
      );
      return null;
    }

    // Get current valve status
    const currentValveStatus = await this.valveCommand.getValveStatus(plotId);

    // Get thresholds from database
    const thresholds = await this.repository.getControlThresholds(
      this.repository.pool,
      plotId
    );

    if (!thresholds) {
      logger.warn({ plotId }, 'No thresholds configured for plot');
      return {
        action: 'MAINTAIN',
        reason: 'No thresholds configured'
      };
    }

    let decision;
    if (controlMode === 'MOISTURE') {
      decision = await this.processMoistureControl(
        plotConfig,
        sensorReading,
        currentValveStatus,
        thresholds
      );
    } else if (controlMode === 'AWD') {
      decision = await this.processAWDControl(
        plotConfig,
        sensorReading,
        currentValveStatus,
        thresholds
      );
    } else {
      logger.warn({ plotId, controlMode }, 'Unknown control mode');
      return {
        action: 'MAINTAIN',
        reason: `Unknown control mode: ${controlMode}`
      };
    }

    // Execute valve command if needed
    if (decision.action !== 'MAINTAIN') {
      await this.executeValveCommand(plotConfig, decision, {
        controlMode,
        sensorReading,
        thresholds,
        valveState: currentValveStatus
      });
    }

    return decision;
  } catch (error) {
    // Log error but don't throw (let caller handle it)
    logger.error(
      { error, plotId: plotConfig.plotId },
      'Error processing plot'
    );
    throw error; // Re-throw so control loop can catch and continue
  }
}
```

### Fix 4: Valve Command Service (src/services/valveCommandService.js)

**Update sendCommand method to handle null pool:**

```javascript
async sendCommand(valveName, level, plotId = null) {
  try {
    // Check if MSSQL pool is available
    if (!this.mssqlPool) {
      logger.warn(
        { valveName, level, plotId },
        'MSSQL unavailable, valve command not sent'
      );
      return {
        success: false,
        error: 'MSSQL connection not available'
      };
    }

    // ... rest of existing code

  } catch (error) {
    logger.error({ error, valveName, level }, 'Failed to send valve command');
    return {
      success: false,
      error: error.message
    };
  }
}
```

## Testing Plan

### 1. Test Logger Fix
```bash
# Restart service and check if errors are readable
npm start

# Trigger an error and check logs show proper stack traces
```

### 2. Test Control Loop Fix
```bash
# Service should continue running without crashing
# Check logs show "Control loop completed: X succeeded, Y failed"
# Verify all 4 plots are attempted even if some fail
```

### 3. Test Data Validation
```bash
# Verify plots without sensors are skipped gracefully
# Verify stale sensor data is detected and skipped
# Check logs show appropriate warnings
```

### 4. Test End-to-End Trigger Flow
```bash
# Run the test script
node scripts/test-trigger-listener.js

# Insert test moisture reading
# Verify audit log is created
# Verify valve command is sent to MSSQL
```

## Implementation Steps

1. **Kill all running service instances**
   ```bash
   pkill -f "node src/index.js"
   ```

2. **Apply logger fix**
   - Edit `src/utils/logger.js`
   - Add custom console format

3. **Apply control loop fix**
   - Edit `src/controllers/waterController.js`
   - Update `runControlLoop()` and `runPlanningLoop()`

4. **Apply data validation fix**
   - Edit `src/controllers/waterController.js`
   - Update `processPlot()` method

5. **Apply valve command fix**
   - Edit `src/services/valveCommandService.js`
   - Add null check for `mssqlPool`

6. **Restart service**
   ```bash
   npm start
   ```

7. **Monitor logs**
   - Watch for readable error messages
   - Verify control loops complete successfully
   - Check for warnings about missing data

8. **Test trigger flow**
   ```bash
   node scripts/test-trigger-listener.js
   ```

## Expected Results After Fixes

1. ✅ Logger displays readable error messages with stack traces
2. ✅ Control loops complete without crashing service
3. ✅ Plots with missing data are skipped with warning logs
4. ✅ Service runs continuously without errors
5. ✅ Trigger → Listener → Control flow works end-to-end
6. ✅ Audit logs are created for control decisions
7. ✅ Valve commands are sent to MSSQL (or warning logged if unavailable)

## Known Limitations

1. **Plots without sensor mappings** - Will be skipped (expected behavior)
2. **Stale sensor data** - Will be skipped until fresh data arrives
3. **MSSQL unavailable** - Valve commands logged but not sent (audit trail still created)
4. **No thresholds configured** - Plot will maintain current state

These are design decisions, not bugs.

---

**Last Updated:** 2025-10-12
**Status:** Fixes identified, ready to implement
