# Service Health Dashboard Implementation

## Overview

Enhanced the existing health monitoring system with:
1. **Service Management Panel** - Real-time PM2 service control with uptime tracking
2. **Sensor Data Visualization** - Live charts for moisture and water level readings

## Files Created/Modified

### Backend

#### New Files
- `services/sensor-data/src/services/service-manager.service.ts` - PM2 service management
- `services/sensor-data/src/routes/service-management.routes.ts` - Service control API endpoints
- `services/sensor-data/test/services/service-manager.service.spec.ts` - Service manager tests (11 tests)
- `services/sensor-data/test/routes/service-management.routes.spec.ts` - Route tests (6 tests)
- `services/sensor-data/test/routes/chart-endpoints.spec.ts` - Chart endpoint tests (6 tests)

#### Modified Files
- `services/sensor-data/src/routes/index.ts` - Mounted service management routes
- `services/sensor-data/src/routes/moisture.routes.ts` - Added `/moisture/chart` endpoint
- `services/sensor-data/src/routes/water-level.routes.ts` - Added `/water-levels/chart` endpoint

### Frontend
- `frontend-health-dashboard.html` - Complete dashboard with service panels and charts

## API Endpoints

### Service Management
```
GET  /api/v1/services/status          - List all PM2 services with metrics
POST /api/v1/services/:name/start     - Start a service
POST /api/v1/services/:name/stop      - Stop a service
```

### Chart Data (15-minute aggregation, last 24 hours)
```
GET  /api/v1/moisture/chart           - Moisture sensor data
GET  /api/v1/water-levels/chart       - Water level sensor data
```

## Features

### Service Management Panel
- **Real-time status** monitoring (online/stopped/errored)
- **Uptime tracking** with formatted display (Xd Xh Xm)
- **Resource metrics** (CPU %, Memory MB, Restart count)
- **Start/Stop controls** with loading states
- **Auto-refresh** every 10 seconds

### Sensor Data Charts
- **Moisture levels** - Surface and deep layer visualization
- **Water levels** - All sensors on single chart
- **Time-series data** - Last 24 hours with 15-minute aggregation
- **Multiple sensors** - Color-coded for easy identification
- **Auto-refresh** every 30 seconds

## Test Coverage

**Total: 23 passing tests**

- Service Manager: 11 tests
  - PM2 connection and listing
  - Service start/stop operations
  - Uptime calculation
  - Error handling

- Service Management Routes: 6 tests
  - Status endpoint
  - Start/stop endpoints
  - Error responses

- Chart Endpoints: 6 tests
  - Data aggregation
  - Field validation
  - Empty data handling

## Dependencies Added

```json
{
  "dependencies": {
    "pm2": "^5.x"
  },
  "devDependencies": {
    "supertest": "^7.x",
    "@types/supertest": "^6.x"
  }
}
```

## Usage

### Start the Backend
```bash
cd services/sensor-data
npm install
npm run dev
```

### Access the Dashboard
Open `frontend-health-dashboard.html` in a web browser or serve via:
```bash
python3 -m http.server 8080
# Navigate to http://localhost:8080/frontend-health-dashboard.html
```

### PM2 Services Required
The dashboard manages these services:
- munbon-scheduler
- munbon-flow-monitoring
- munbon-bff-water-planning
- munbon-ros-gis-integration
- munbon-water-accounting
- munbon-awd-control
- munbon-gis
- smartfarm-water-control

## Technical Implementation

### Service Manager
- Wraps PM2 API in promise-based functions
- Handles connection pooling (connect/disconnect per operation)
- Type-safe with TypeScript
- Calculates uptime from Unix timestamps

### Chart Data Aggregation
- Uses TimescaleDB `time_bucket` for efficient 15-minute intervals
- Aggregates avg/min/max for trend analysis
- Supports multiple sensors per chart
- Optimized queries with proper indexing

### Frontend Architecture
- Vanilla JavaScript (no framework dependencies)
- Chart.js 4.x for visualizations
- Responsive grid layout (CSS Grid)
- State management via Map for service tracking
- Async/await for all API calls

## Performance Considerations

- **Polling intervals** optimized to balance freshness and load
- **Chart updates** use incremental updates, not full re-render
- **Database queries** use hypertable aggregations for speed
- **PM2 operations** include proper connection cleanup

## Security Notes

- Service management endpoints should be behind authentication in production
- Consider adding rate limiting to prevent PM2 overload
- Chart endpoints are read-only (safe for public access with data filtering)

## Future Enhancements

Potential improvements:
- Authentication/authorization for service controls
- Configurable time ranges for charts
- Export chart data as CSV
- Alert threshold configuration
- Service logs viewer
- Historical uptime statistics
