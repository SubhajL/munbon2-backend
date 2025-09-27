# Smart Farm Water Control Service

A GIS-based water planning and control system for smart farms with automated irrigation control based on sensor readings.

## Features

- **Dual Control Modes**:
  - **AWD (Alternate Wetting and Drying)**: Controls irrigation based on water level sensors
  - **Moisture-Based Control**: Uses dual-threshold system for moisture sensors

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

The system is configured for 10-11 plots (~2.5 rai each):
- Plots SF01-SF05: AWD control with water level sensors
- Plots SF06-SF11: Moisture-based control

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Plot Configuration
SMART_FARM_PLOTS=SF01,SF02,SF03,SF04,SF05,SF06,SF07,SF08,SF09,SF10,SF11

# Moisture Control Parameters
MOISTURE_THRESHOLD_LOW_PERCENT=10    # Turn ON below this
MOISTURE_THRESHOLD_HIGH_PERCENT=15   # Turn OFF above this

# AWD Control Parameters
AWD_MIN_WATER_LEVEL_CM=5
AWD_MAX_WATER_LEVEL_CM=15
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

## Database Schemas

### TimescaleDB Schemas

#### ros_gis_smartfarm
- `daily_water_demands` - Planned water requirements
- `daily_progress` - Actual vs planned usage

#### water_control_smartfarm
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