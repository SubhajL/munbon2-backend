# Smart Farm Service Refactoring Summary

## Overview

The Smart Farm Water Control Service has been refactored to use the repository pattern with pure dependency injection, eliminating hidden environment dependencies and ensuring consistent database access patterns.

## Refactoring Goals (Completed ✅)

1. ✅ Fix `TimescaleRepository` constructor to accept pool directly
2. ✅ Remove `process.env` fallback from `WaterPlanningService` (enforce pure DI)
3. ✅ Refactor all test suites to use repository doubles instead of raw pool mocks
4. ✅ Remove unused `sensorClient.js` file
5. ✅ Update documentation and clean up obsolete files

## Key Changes

### 1. Repository Pattern Implementation

- Created `TimescaleRepository` class for centralized database access
- Repository accepts initialized pool instead of creating its own
- All database queries are handled through repository methods
- No external API calls for sensor data

### 2. Service Refactoring

#### TimescaleRepository (FIXED)

**Constructor Change:**

```javascript
// BEFORE (BROKEN):
constructor(config) {
  this.pool = new Pool(config); // Tried to create pool from undefined config
}

// AFTER (FIXED):
constructor(pool, schemas = { planning: 'ros_gis_smartfarm', control: 'water_control_smartfarm' }) {
  this.pool = pool; // Accepts already-initialized pool
  this.schemas = schemas;
}
```

#### SensorDataService (NEW)

- Replaces the deprecated API-based `SensorClient`
- Uses `TimescaleRepository` for direct database queries
- Maintains the same interface: `getSensorReading(sensorId)`

#### WaterBalanceService

- Now uses `timescaleRepository` instead of raw pool
- Repository methods: `recordIrrigationCycle()`, `getDailyWaterBalance()`, `getAggregatedUsageMetrics()`

#### WaterPlanningService (REFACTORED)

- **Added explicit `rosEndpoint` parameter** to constructor (no more `process.env` fallback)
- Uses `timescaleRepository` for storing water demand data
- Still uses ROS API for demand calculations (as required)
- All database operations go through repository

#### ValveCommandService

- Uses `timescaleRepository` for valve status updates and irrigation cycle recording
- Maintains direct MSSQL connection for SCADA valve commands

### 3. Architecture Pattern

```
┌─────────────────────┐
│   Controller        │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Services Layer    │
│  - SensorDataService│
│  - WaterBalance     │
│  - WaterPlanning    │
│  - ValveCommand     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│ TimescaleRepository │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Database Layer    │
│  - TimescaleDB      │
│  - MSSQL            │
└─────────────────────┘
```

### 4. Test Suite Refactoring (COMPLETE)

All test files refactored to use repository doubles instead of raw database mocks:

#### ✅ waterPlanningService.spec.js (18 tests)

- Replaced `mockTimescalePool` with `mockRepository`
- Added test for ROS endpoint injection
- Repository methods: `saveWaterDemand`, `getPlannedDemand`, `saveDailyProgress`

#### ✅ waterBalanceService.spec.js (18 tests)

- Uses repository doubles for all database operations
- Tests validate repository method calls instead of SQL strings
- Repository methods: `recordIrrigationCycle`, `getDailyWaterBalance`, `getAggregatedUsageMetrics`

#### ✅ valveCommandService.spec.js (19 tests)

- Split between MSSQL (valve commands) and repository (state tracking)
- Repository methods: `updateValveStatus`, `recordIrrigationCycle`

#### ✅ controlLoop.spec.js (7 integration tests)

- End-to-end tests with repository pattern
- Mock sensor data service (no real SensorClient dependency)
- Tests full control loops for AWD and moisture control modes

**Test Results:** All 93 tests passing ✅

## Database Tables Used

### TimescaleDB Tables (via Repository)

- `${schemas.control}.moisture_readings` - Moisture sensor data
- `${schemas.control}.water_level_readings` - AWD water level sensor data
- `${schemas.control}.water_balance` - Irrigation history with volume tracking
- `${schemas.control}.valve_status` - Real-time valve state history
- `${schemas.planning}.daily_water_demands` - ROS-calculated water demands
- `${schemas.planning}.daily_progress` - Actual vs planned usage tracking

### MSSQL Tables (Direct Connection)

- `tb_valve_command_v2` - SCADA valve command interface

## Benefits of This Refactoring

1. **Explicit Configuration**: No hidden `process.env` dependencies
2. **Testability**: Repository pattern enables pure unit tests without database
3. **Type Safety**: Clear service contracts and interfaces
4. **Maintainability**: Single source of truth for database queries
5. **Consistency**: All services follow same dependency injection pattern
6. **Reliability**: Startup failures caught immediately (no runtime surprises)

## Files Modified

- ✅ `src/repository/timescaleRepository.js` - Fixed constructor
- ✅ `src/services/waterPlanningService.js` - Added rosEndpoint parameter
- ✅ `src/index.js` - Updated service initialization
- ✅ `tests/services/waterPlanningService.spec.js` - Repository doubles
- ✅ `tests/services/waterBalanceService.spec.js` - Repository doubles
- ✅ `tests/services/valveCommandService.spec.js` - Repository doubles
- ✅ `tests/integration/controlLoop.spec.js` - Repository integration tests
- ❌ `src/services/sensorClient.js` - **REMOVED** (deprecated)

## Running Tests

```bash
# Run all tests
npm test

# Run specific test suite
npm test -- tests/services/waterPlanningService.spec.js
npm test -- tests/integration/controlLoop.spec.js
```

## GeoJSON-Based Plot Configuration (Latest Refactoring)

### Motivation

Replace hard-coded plot entries in `.env` with GIS-derived metadata from the actual smart farm shapefile. This ensures:

- Plot areas come from authoritative GIS data (area_rai from shapefile)
- Plot geometries are available for future ROS integration
- Single source of truth for plot boundaries and characteristics
- Easier to add/remove plots without modifying code

### Implementation

#### GeoJSON Generation

- Converted `GIS_moonbon/Smart Farm/ridmb_shp/ridmb.shp` to `data/smartfarm-plots.geojson`
- Extracted key attributes: `crop_id`, `area_rai`, `stage_oae`
- 12 plots total with areas ranging from 1.13 to 5.37 rai
- Preserves WGS84 (EPSG:4326) coordinate system

#### New Configuration Pattern

**Before (hard-coded in .env):**

```bash
SMART_FARM_PLOTS=SF01,SF02,SF03
PLOT_AREA_RAI=2.5  # Same for all plots
SF01_SENSORS=AWD:AWD-SF01
SF01_VALVE=SV_SF01
```

**After (GeoJSON + simple mapping):**

```bash
# Plots and areas from data/smartfarm-plots.geojson
# Format: plotId:sensorId:valveName:controlMode
PLOT_CONFIGS=fbd7920c-1a05-487c-a79e-a4003ab30be9:AWD-SF01:SV_SF01:AWD,535d0d0b-afdb-49f2-85dd-74c13ee7b561:MOIST-SF02:SV_SF02:MOISTURE
```

#### Code Changes

- ✅ `src/utils/plotConfigLoader.js` - Load/merge GeoJSON with env config
- ✅ `src/config/index.js` - Updated to use plotConfigLoader
- ✅ `data/smartfarm-plots.geojson` - Authoritative plot geometry/area source
- ✅ `tests/utils/plotConfigLoader.spec.js` - Full test coverage (12 tests)
- ✅ `tests/config/index.spec.js` - Config integration tests (4 tests)
- ✅ `.env.example` - Updated with new format and all 12 plot IDs listed

#### Benefits

1. **Accuracy**: Areas from actual surveyed GIS data (not estimates)
2. **Geometry Available**: Full polygon coordinates for ROS demand calculation
3. **Simplified Config**: One line per plot instead of 3+ env variables
4. **Validation**: Errors if env references non-existent plot or vice versa
5. **Flexibility**: Easy to regenerate GeoJSON if shapefile updated

#### Test Coverage

- **plotConfigLoader**: 13 tests (load, merge, validate)
- **config integration**: 4 tests
- **All existing tests**: Still passing (110 total)

### GeoJSON Structure

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "crop_id": "fbd7920c-1a05-487c-a79e-a4003ab30be9",
        "area_rai": 2.51,
        "stage_oae": "4"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lng, lat], ...]]
      }
    }
  ]
}
```

## Database-Driven Control Modes (December 2024)

### Motivation

Move control mode configuration from static environment variables to database storage for runtime reconfigurability without service restart.

**Before (Environment-Based):**

- Control modes hard-coded in PLOT_CONFIGS: `plotId:sensorId:valveName:controlMode`
- Changing control mode required .env update and service restart
- No audit trail of control mode changes

**After (Database-Driven):**

- Control modes stored in `water_control_smartfarm.control_modes` table
- Changes take effect within cache TTL (5 minutes) or next hourly refresh
- Full audit trail with updated_at, updated_by, and notes fields

### Implementation Details

#### Database Schema

```sql
CREATE TABLE water_control_smartfarm.control_modes (
  plot_id VARCHAR(50) PRIMARY KEY,
  control_mode TEXT NOT NULL CHECK (control_mode IN ('AWD', 'MOISTURE')),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  updated_by VARCHAR(100),
  notes TEXT
);
```

#### Repository Layer

Added to `TimescaleRepository`:

- `getControlModes()` - Returns all control modes
- `getControlMode(plotId)` - Returns mode for specific plot

#### Service Layer

New `ControlModeService` with:

- In-memory Map cache for fast lookups
- TTL-based staleness detection (default: 5 minutes)
- Auto-refresh capability
- Startup mode loading
- Hourly cron job for cache refresh

#### Configuration Changes

Updated `PLOT_CONFIGS` format:

```bash
# OLD FORMAT (3 fields + control mode):
PLOT_CONFIGS=plotId:sensorId:valveName:controlMode

# NEW FORMAT (3 fields only):
PLOT_CONFIGS=plotId:sensorId:valveName
```

Control modes now managed separately via database.

#### Controller Integration

`WaterController` now fetches control mode dynamically:

```javascript
// OLD (from config):
const { plotId, controlMode } = plotConfig;

// NEW (from service):
const { plotId } = plotConfig;
const controlMode = this.controlMode.getMode(plotId);
```

#### Seed Script

Created `scripts/seed-control-modes.js`:

```bash
# Usage
node scripts/seed-control-modes.js \
  fbd7920c-1a05-487c-a79e-a4003ab30be9:AWD \
  535d0d0b-afdb-49f2-85dd-74c13ee7b561:MOISTURE

# Features:
# - Validates modes against AWD/MOISTURE
# - Upsert pattern (safe to run multiple times)
# - Displays table summary after seeding
```

#### Manual Database Updates

Control modes can be updated via SQL:

```sql
UPDATE water_control_smartfarm.control_modes
SET control_mode = 'MOISTURE',
    updated_at = NOW(),
    updated_by = 'admin',
    notes = 'Switched to moisture control'
WHERE plot_id = 'fbd7920c-1a05-487c-a79e-a4003ab30be9';
```

### Cache & Propagation

**Cache Strategy:**

- In-memory Map cache for O(1) lookups
- TTL: 5 minutes (configurable)
- Hourly cron job calls `refreshIfStale()`
- Startup: `loadModes()` called immediately

**Propagation Delay:**

- Database update → immediate persistence
- Cache refresh → within 5 minutes (TTL) or next hourly cron
- Control loop sees new mode → next iteration (5-minute interval)
- Maximum delay: ~10 minutes in worst case

### Test Coverage

**New Test Suites:**

- `timescaleRepository.spec.js`: 7 tests for repository methods
- `controlModeService.spec.js`: 13 tests for service layer

**Updated Test Suites:**

- `controlLoop.spec.js`: 7 integration tests (added mock controlMode service)
- `config/index.spec.js`: 3 tests (removed controlMode from env parsing)
- `plotConfigLoader.spec.js`: 11 tests (removed controlMode validation)

**Final Test Results:** 127 tests passing across 10 test suites

### Benefits

1. **Runtime Reconfiguration**: Change control modes without service restart
2. **Audit Trail**: Track who changed what and when
3. **Operational Notes**: Add context to control mode changes
4. **Centralized Management**: Single source of truth in database
5. **Performance**: Fast in-memory cache with periodic refresh
6. **Reliability**: Startup fails fast if modes not configured

### Files Modified

- ✅ `src/config/database.js` - Added control_modes table
- ✅ `src/repository/timescaleRepository.js` - Added getControlModes/getControlMode
- ✅ `src/services/controlModeService.js` - New caching service
- ✅ `src/config/index.js` - Removed controlMode from PLOT_CONFIGS parsing
- ✅ `src/utils/plotConfigLoader.js` - Removed controlMode from merge/validation
- ✅ `src/index.js` - Initialize service, load modes, add cron job
- ✅ `src/controllers/waterController.js` - Fetch mode from service
- ✅ `scripts/seed-control-modes.js` - New seed utility
- ✅ All test files updated
- ✅ Documentation updated (.env.example, README.md)

## Next Steps

1. ✅ ~~Fix repository constructor bug~~
2. ✅ ~~Remove process.env fallbacks~~
3. ✅ ~~Refactor test suite~~
4. ✅ ~~Remove deprecated files~~
5. ✅ ~~Implement GeoJSON-based plot configuration~~
6. ✅ ~~Move control modes to database~~
7. ⏳ Update production .env with new PLOT_CONFIGS format
8. ⏳ Seed production control_modes table
9. ⏳ Test service startup with real plot configurations
10. ⏳ Integrate plot geometries with ROS demand calculation API
