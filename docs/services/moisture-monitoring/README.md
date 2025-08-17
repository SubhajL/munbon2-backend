# Moisture Monitoring Service

This service provides dedicated moisture sensor monitoring, analytics, and alerting for the Munbon Irrigation Control System.

## Features

- **Real-time Monitoring**: Track surface and deep soil moisture levels
- **Flood Detection**: Alert on flood conditions detected by sensors
- **Multi-layer Analytics**: Analyze moisture at different soil depths
- **Smart Alerts**: Configurable thresholds for moisture levels
- **WebSocket Support**: Real-time data streaming to clients
- **MQTT Integration**: Publish/subscribe for IoT communication
- **Field-level Analytics**: Aggregate data across multiple sensors

## Architecture

This service reads moisture data from TimescaleDB (populated by the sensor-data service) and provides:
- REST API for data access
- WebSocket for real-time updates
- MQTT for IoT integration
- Redis caching for performance

## API Endpoints

### Moisture Readings
- `GET /api/v1/moisture/readings/latest` - Get latest readings
- `GET /api/v1/moisture/sensors/:sensorId/readings` - Get historical data
- `GET /api/v1/moisture/sensors/:sensorId/aggregated` - Get aggregated data
- `GET /api/v1/moisture/sensors/:sensorId/analytics` - Get analytics

### Sensors
- `GET /api/v1/moisture/sensors/active` - List active sensors
- `GET /api/v1/moisture/sensors/nearby` - Find sensors by location

### Alerts
- `GET /api/v1/moisture/sensors/:sensorId/alerts` - Get active alerts
- `POST /api/v1/moisture/alerts/:alertId/acknowledge` - Acknowledge alert

## Configuration

See `.env.example` for all configuration options.

Key settings:
- `ALERT_LOW_MOISTURE_THRESHOLD` - Trigger warning when moisture drops below this
- `ALERT_FLOOD_DETECTION_ENABLED` - Enable/disable flood detection alerts
- `ANALYTICS_RETENTION_DAYS` - How long to keep analytics data

## WebSocket Events

### Client → Server
- `subscribe:sensor` - Subscribe to specific sensor
- `subscribe:sensors` - Subscribe to multiple sensors
- `subscribe:all` - Subscribe to all moisture data
- `subscribe:alerts` - Subscribe to alerts

### Server → Client
- `moisture:reading` - New moisture reading
- `moisture:alert` - New alert
- `moisture:analytics` - Analytics update

## MQTT Topics

### Publishing
- `moisture/sensors/{sensorId}/data` - Sensor readings
- `moisture/alerts/{severity}` - Alerts by severity
- `moisture/analytics/{sensorId}` - Analytics data

### Subscribing
- `sensors/moisture/+/data` - Raw sensor data from ingestion

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Build for production
npm run build

# Run tests
npm test
```

## Deployment

The service is containerized and can be deployed to Kubernetes:

```bash
# Build Docker image
docker build -t munbon/moisture-monitoring:latest .

# Run with Docker
docker run -p 3044:3044 munbon/moisture-monitoring:latest
```

## Integration with Kong

This service is exposed through Kong API Gateway at `/api/v1/moisture`.