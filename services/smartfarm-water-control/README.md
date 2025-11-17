# Smart Farm Water Control Service

A GIS-based water planning and control system for smart farms with automated irrigation control based on sensor readings.

## Features

- **Dual Control Modes**:
  - **AWD (Alternate Wetting and Drying)**: Controls irrigation based on water level sensors
  - **Moisture-Based Control**: Uses dual-threshold system for moisture sensors
  - **Database-Driven**: Control modes stored in TimescaleDB, runtime reconfigurable

- **ROS Integration**: Daily water demand calculation using ROS algorithm
- **Real-time Control**: Automated valve control based on sensor readings
- **Water Balance Tracking**: Comprehensive tracking of water usage and efficiency
- **Multi-Database Support**: TimescaleDB for time-series data, MSSQL for valve commands

## System Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│ Sensor Network  │────▶│ Control Loop │────▶│   Valves    │
└─────────────────┘     └──────────────┘     └─────────────┘
                               │
                               ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  ROS Service    │────▶│Planning Loop │────▶│ TimescaleDB │
└─────────────────┘     └──────────────┘     └─────────────┘
```

## Configuration

### GeoJSON-Based Plot Configuration

Plot geometries and areas are loaded from `data/smartfarm-plots.geojson`, which contains 12 plots with areas ranging from 1.13 to 5.37 rai (sourced from the authoritative smart farm shapefile).

**Benefits:**

- Plot areas come from actual GIS survey data
- Plot geometries available for ROS integration
- Single source of truth for plot boundaries
- Easy to update by regenerating GeoJSON from shapefile

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Plot Configuration (GeoJSON-based)
# Format: plotId:sensorId:valveName
# Plot IDs must match crop_id values in data/smartfarm-plots.geojson
# Control modes are managed via database (see below)
#
# Example with 2 plots:
PLOT_CONFIGS=fbd7920c-1a05-487c-a79e-a4003ab30be9:AWD-SF01:SV_SF01,535d0d0b-afdb-49f2-85dd-74c13ee7b561:MOIST-SF02:SV_SF02

# Moisture Control Parameters
MOISTURE_THRESHOLD_LOW_PERCENT=50    # Turn ON below this
MOISTURE_THRESHOLD_HIGH_PERCENT=69   # Turn OFF above this

# AWD Control Parameters
AWD_MIN_WATER_LEVEL_CM=-10
AWD_MAX_WATER_LEVEL_CM=10
AWD_DRYING_PERIOD_DAYS=7

# Database Configuration
TIMESCALE_HOST=your-timescale-host
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=your-password

MSSQL_HOST=moonup.hopto.org
MSSQL_DB=db_scada
MSSQL_USER=your-user
MSSQL_PASSWORD=your-password

# ROS Integration
ROS_API_URL=http://ros-service:3001/api
ROS_API_KEY=your-api-key
```

### Control Mode Management

Control modes (AWD/MOISTURE) are stored in the `water_control_smartfarm.control_modes` table in TimescaleDB, allowing runtime reconfiguration without service restart.

#### Setting Control Modes via Seed Script

Use the provided seed script to populate or update control modes:

```bash
# Seed control modes for plots
node scripts/seed-control-modes.js \
  fbd7920c-1a05-487c-a79e-a4003ab30be9:AWD \
  535d0d0b-afdb-49f2-85dd-74c13ee7b561:MOISTURE

# The script will:
# - Validate control modes (AWD or MOISTURE only)
# - Upsert records (safe to run multiple times)
# - Display summary of all control modes
```

#### Manual Database Updates

You can also update control modes directly via SQL:

```sql
-- Update a plot's control mode
UPDATE water_control_smartfarm.control_modes
SET control_mode = 'MOISTURE',
    updated_at = NOW(),
    updated_by = 'admin',
    notes = 'Switched to moisture control for better efficiency'
WHERE plot_id = 'fbd7920c-1a05-487c-a79e-a4003ab30be9';

-- View all current control modes
SELECT plot_id, control_mode, updated_at, updated_by
FROM water_control_smartfarm.control_modes
ORDER BY plot_id;
```

#### Cache Behavior

- Control modes are cached in memory for performance (default TTL: 5 minutes)
- Cache is automatically refreshed every hour via cron job
- Manual refresh can be triggered by calling `/api/control/refresh-modes`
- Changes take effect within 5 minutes or on next scheduled refresh

### Regenerating GeoJSON from Shapefile

If the source shapefile is updated:

```bash
ogr2ogr -f GeoJSON -t_srs EPSG:4326 \
  data/smartfarm-plots.geojson \
  GIS_moonbon/Smart\ Farm/ridmb_shp/ridmb.shp \
  -select crop_id,area_rai,stage_oae
```

## Installation

```bash
npm install
```

## Running the Service

### Development

```bash
npm run dev
```

### Production

```bash
npm start
```

## CLI: Print plot→valve map (no server)

Use this utility to audit plot→valve mapping and SCADA names without starting the service.

Commands:

```
# table output
npm run print:plot-valves

# filter by plots
node scripts/print-plot-valve-map.js --plots "SF-U*,SF-L*"

# JSON output
npm run print:plot-valves:json

# SCADA names only
node scripts/print-plot-valve-map.js --only-scada --plots "SF-U*"
```

It reads config/device-mapping.json and applies SF-* overrides. No DB or cron is started.

## API Endpoints

### Plot Management

- `GET /api/plots` - Get status of all plots
- `GET /api/plots/:plotId` - Get status of specific plot
- `POST /api/plots/:plotId/valve` - Manual valve control

### Control & Planning

- `POST /api/control/run` - Trigger control loop manually
- `POST /api/planning/run` - Trigger planning loop manually
- `POST /api/progress/update` - Update daily progress

### Metrics

- `GET /api/plots/:plotId/balance` - Get water balance for a plot
- `GET /api/metrics/usage` - Get aggregated usage metrics

## Control Logic

### Moisture Control (Dual-Threshold)

```
IF moisture < MOISTURE_THRESHOLD_LOW_PERCENT:
    Turn ON valve
ELSE IF moisture > MOISTURE_THRESHOLD_HIGH_PERCENT:
    Turn OFF valve
ELSE:
    Maintain current state
```

### AWD Control

```
IF water_level < AWD_MIN_WATER_LEVEL_CM:
    Turn ON valve
ELSE IF water_level >= AWD_MAX_WATER_LEVEL_CM:
    Turn OFF valve
ELSE:
    Maintain current state
```

## Automated Schedules

- **Control Loop**: Every 5 minutes (configurable)
- **Planning Loop**: Daily at 6 AM
- **Progress Update**: Daily at 11 PM
- **Control Mode Cache Refresh**: Hourly (auto-refresh if stale)

## Database Schemas

### TimescaleDB Schemas

#### ros_gis_smartfarm

- `daily_water_demands` - Planned water requirements
- `daily_progress` - Actual vs planned usage

#### water_control_smartfarm

- `control_modes` - Plot control mode configuration (AWD/MOISTURE)
- `valve_status` - Current valve states
- `irrigation_cycles` - Irrigation history
- `water_balance` - Water usage records

### MSSQL Tables

- `tb_valve_command_v2` - Valve control commands

## Testing

Run all tests:

```bash
npm test
```

Run specific test suite:

```bash
npm test tests/services/moistureControlService.spec.js
```

## Project Structure

```
smartfarm-water-control/
├── src/
│   ├── config/           # Database and service configurations
│   ├── services/         # Core business logic
│   │   ├── moistureControlService.js
│   │   ├── awdControlService.js
│   │   ├── valveCommandService.js
│   │   ├── waterPlanningService.js
│   │   └── waterBalanceService.js
│   ├── controllers/      # Request handlers
│   ├── routes/          # API routes
│   └── utils/           # Utilities
├── tests/               # Test suites
└── package.json
```

## Dependencies

- **express** - Web framework
- **pg** - PostgreSQL client for TimescaleDB
- **mssql** - Microsoft SQL Server client
- **axios** - HTTP client for ROS integration
- **node-cron** - Task scheduling
- **winston** - Logging

## License

ISC

## Integration with Real Services

### Quick Start

```bash
# Run the quick start script to verify all integrations
npm run setup
```

### Testing Integrations

```bash
# Test all integrations
npm run test:integration

# Test database connections only
npm run test:db

# Test ROS service integration
npm run test:ros

# Test sensor data service integration
npm run test:sensors
```

### Required Services

1. **External API Service** (Port 3015)
   - Provides authenticated sensor data access
   - Required for real-time sensor readings

2. **ROS Service** (Port 3001)
   - Calculates daily water demands
   - Required for planning functionality

3. **Databases**
   - TimescaleDB: Time-series sensor data
   - MSSQL: Valve command storage

See [docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) for detailed setup instructions.
