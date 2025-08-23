# Unified Mock Server for Water Planning BFF

This mock server provides all external service endpoints needed for Water Planning BFF development in a single server running on port 3099.

## Features

- **Single Server**: All mock services run on one port (3099)
- **Service Prefixes**: Each service is accessible via its prefix:
  - ROS: `/ros/api/v1/*`
  - GIS: `/gis/api/v1/*`
  - AWD: `/awd/api/v1/*`
  - Sensor Data: `/sensor/api/v1/*`
  - Flow Monitoring: `/flow/api/v1/*`
  - Scheduler: `/scheduler/api/v1/*`
  - Weather: `/weather/api/v1/*
- **Interactive API Docs**: Available at http://localhost:3099/docs
- **Realistic Mock Data**: Returns consistent, realistic data for testing

## Quick Start

1. **Install dependencies:**
   ```bash
   cd services/mock-server
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Start the mock server:**
   ```bash
   python src/main.py
   ```

3. **Verify it's running:**
   ```bash
   curl http://localhost:3099/health
   ```

## Using with BFF Service

1. **Configure BFF to use mock server:**
   
   In `services/bff-water-planning/.env`:
   ```env
   USE_MOCK_SERVER=true
   MOCK_SERVER_URL=http://localhost:3099
   ```

2. **Start both services:**
   ```bash
   cd services/bff-water-planning
   ./start_with_mock.sh
   ```

## Available Endpoints

### ROS Service
- `POST /ros/api/v1/water-demand/calculate` - Calculate water demand
- `GET /ros/api/v1/water-demand/weekly/{plot_id}` - Get weekly water demand
- `GET /ros/api/v1/eto/calculate` - Calculate ETo
- `GET /ros/api/v1/crop-coefficient/{crop_type}` - Get crop coefficients

### GIS Service
- `GET /gis/api/v1/plots/{plot_id}` - Get plot information
- `GET /gis/api/v1/sections/{section_id}` - Get section details
- `POST /gis/api/v1/spatial/parcels-in-section` - Find parcels in section
- `GET /gis/api/v1/spatial/nearest-gate` - Find nearest gate

### AWD Service
- `GET /awd/api/v1/awd/plots/{plot_id}/status` - Get AWD status
- `GET /awd/api/v1/awd/recommendations` - Get AWD recommendations
- `POST /awd/api/v1/awd/plots/{plot_id}/activate` - Activate AWD
- `POST /awd/api/v1/awd/moisture-reading` - Update moisture reading

### Sensor Data Service
- `GET /sensor/api/v1/water-levels/{section_id}` - Get water level readings
- `GET /sensor/api/v1/moisture/{plot_id}` - Get moisture readings
- `GET /sensor/api/v1/sensors/status` - Get sensor status
- `GET /sensor/api/v1/telemetry/latest` - Get latest telemetry

### Flow Monitoring Service
- `GET /flow/api/v1/flow/current` - Get current flow readings
- `GET /flow/api/v1/flow/history` - Get flow history
- `GET /flow/api/v1/flow/balance/{section_id}` - Get flow balance
- `GET /flow/api/v1/flow/sensors` - Get flow sensor info

### Scheduler Service
- `GET /scheduler/api/v1/schedules` - Get schedules
- `POST /scheduler/api/v1/schedules` - Create schedule
- `GET /scheduler/api/v1/schedules/{id}/executions` - Get execution history
- `GET /scheduler/api/v1/schedules/conflicts` - Check conflicts

### Weather Service
- `GET /weather/api/v1/weather/current` - Get current weather
- `GET /weather/api/v1/weather/forecast` - Get weather forecast
- `GET /weather/api/v1/weather/historical` - Get historical weather
- `GET /weather/api/v1/weather/et0/calculate` - Calculate ET0

## Testing

Run the integration test suite:
```bash
cd services/bff-water-planning
python test_mock_integration.py
```

## Mock Data Management

- **Reset data**: `GET /api/v1/mock/reset`
- **Check status**: `GET /api/v1/mock/status`

## Development

The mock server is built with FastAPI and includes:
- Automatic API documentation
- Request/response validation
- Consistent error handling
- Realistic data generation

To add new endpoints:
1. Create or update the service mock in `src/services/`
2. Register the router in `src/main.py`
3. Update this README with new endpoints