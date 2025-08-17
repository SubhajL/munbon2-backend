# Sensor Network Management Service

This service manages the hybrid sensor network for the Munbon irrigation system, optimizing the placement and utilization of limited mobile sensors (6 water level + 1 moisture sensor).

## Features

### Core Functionality
- **Sensor Registry & Tracking**: Real-time tracking of all mobile sensors
- **Placement Optimization**: AI-driven optimal sensor placement based on multiple factors
- **Data Interpolation**: Advanced interpolation for ungauged locations
- **Movement Scheduling**: Optimized weekly movement schedules for field teams
- **Battery Management**: Proactive battery monitoring and alerts

### API Endpoints

#### Sensor Management
- `GET /api/v1/sensors/mobile/status` - Get status of all mobile sensors
- `GET /api/v1/sensors/{sensor_id}` - Get detailed sensor information
- `PUT /api/v1/sensors/{sensor_id}` - Update sensor information
- `GET /api/v1/sensors/battery/low` - Get sensors with low battery
- `POST /api/v1/sensors/register` - Register a new sensor

#### Placement Optimization
- `POST /api/v1/placement/optimize` - Generate optimal placement plan
- `GET /api/v1/placement/recommendations` - Get placement recommendations
- `GET /api/v1/placement/current` - Get current sensor placements
- `GET /api/v1/placement/coverage-analysis` - Analyze sensor coverage

#### Data Interpolation
- `GET /api/v1/interpolation/section/{section_id}` - Get interpolated data for a section
- `POST /api/v1/interpolation/batch` - Batch interpolation for multiple sections
- `GET /api/v1/interpolation/grid` - Get spatial interpolation grid
- `POST /api/v1/interpolation/calibrate` - Calibrate model with actual data

#### Movement Scheduling
- `POST /api/v1/movement/schedule` - Create optimized movement schedule
- `GET /api/v1/movement/schedule/current` - Get current week's schedule
- `GET /api/v1/movement/tasks` - Get movement tasks
- `PUT /api/v1/movement/tasks/{task_id}/status` - Update task status

## Configuration

Environment variables (see `.env.example`):
- `SERVICE_PORT`: Service port (default: 3023)
- `MAX_WATER_LEVEL_SENSORS`: Maximum water level sensors (default: 6)
- `MAX_MOISTURE_SENSORS`: Maximum moisture sensors (default: 1)
- `SENSOR_BATTERY_LOW_THRESHOLD`: Low battery threshold percentage (default: 20)
- `SENSOR_PLACEMENT_UPDATE_INTERVAL_DAYS`: Placement update interval (default: 7)

## Interpolation Methods

The service supports multiple interpolation methods:
1. **Inverse Distance Weighted (IDW)**: For sparse sensor coverage
2. **Kriging**: For better spatial correlation modeling
3. **Hydraulic Model**: Uses hydraulic principles for water level
4. **Machine Learning**: AI-based predictions
5. **Hybrid**: Combines multiple methods for best results

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run the service
python src/main.py
```

## Docker

```bash
# Build image
docker build -t sensor-network-management .

# Run container
docker run -p 3023:3023 --env-file .env sensor-network-management
```

## Integration Points

- **Instance 16 (Core Monitoring)**: Provides interpolated sensor data
- **Instance 17 (Field Ops Scheduler)**: Coordinates sensor movement schedules
- **Instance 18 (ROS/GIS)**: Uses section priorities for placement optimization

## Testing

Test the service with:
```bash
# Check health
curl http://localhost:3023/health

# Get sensor status
curl http://localhost:3023/api/v1/sensors/mobile/status

# Get interpolated data
curl http://localhost:3023/api/v1/interpolation/section/RMC-01
```