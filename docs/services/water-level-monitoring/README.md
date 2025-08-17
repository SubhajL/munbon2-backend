# Water Level Monitoring Service

This service provides dedicated water level monitoring, analytics, alerting, and gate control recommendations for the Munbon Irrigation Control System.

## Features

- **Real-time Water Level Tracking**: Monitor water levels in canals and reservoirs
- **Rate of Change Analysis**: Detect rapid rises or falls in water level
- **Gate Control Recommendations**: AI-driven recommendations for gate operations
- **Critical Alerts**: Flood warnings and low water alerts
- **Trend Analysis**: Historical trends and predictions
- **WebSocket Support**: Real-time data streaming
- **MQTT Integration**: IoT device communication
- **SCADA Integration**: Gate control coordination

## Architecture

This service reads water level data from TimescaleDB (populated by the sensor-data service) and provides:
- REST API for data access and control
- WebSocket for real-time monitoring
- MQTT for sensor and gate communication
- Integration with SCADA for gate control

## API Endpoints

### Water Level Readings
- `GET /api/v1/water-levels/readings/latest` - Get latest readings
- `GET /api/v1/water-levels/sensors/:sensorId/readings` - Historical data
- `GET /api/v1/water-levels/sensors/:sensorId/aggregated` - Aggregated data
- `GET /api/v1/water-levels/sensors/:sensorId/analytics` - Analytics
- `GET /api/v1/water-levels/sensors/:sensorId/rate-of-change` - Rate of change

### Sensors
- `GET /api/v1/water-levels/sensors/active` - List active sensors
- `GET /api/v1/water-levels/sensors/nearby` - Find by location

### Alerts
- `GET /api/v1/water-levels/sensors/:sensorId/alerts` - Active alerts
- `POST /api/v1/water-levels/alerts/:alertId/acknowledge` - Acknowledge

### Gate Control
- `GET /api/v1/water-levels/gates/:gateId/recommendation` - Get recommendation
- `GET /api/v1/water-levels/gates/:gateId/status` - Gate status

## Configuration

See `.env.example` for all configuration options.

Key settings:
- `ALERT_HIGH_WATER_THRESHOLD` - High water warning level (cm)
- `ALERT_CRITICAL_HIGH_WATER_THRESHOLD` - Critical flood risk level
- `GATE_CONTROL_ENABLED` - Enable gate control recommendations
- `GATE_CONTROL_MIN_LEVEL` - Target minimum water level
- `GATE_CONTROL_MAX_LEVEL` - Target maximum water level

## Alert Types

1. **CRITICAL_HIGH_WATER** - Immediate flood risk
2. **HIGH_WATER** - Approaching dangerous levels
3. **LOW_WATER** - Water conservation needed
4. **CRITICAL_LOW_WATER** - Irrigation at risk
5. **RAPID_INCREASE** - Sudden water rise detected
6. **RAPID_DECREASE** - Sudden water drop detected

## WebSocket Events

### Client → Server
- `subscribe:sensor` - Subscribe to sensor updates
- `subscribe:alerts` - Subscribe to alerts
- `subscribe:gates` - Subscribe to gate recommendations

### Server → Client
- `water-level:reading` - New water level data
- `water-level:alert` - New alert
- `gate:recommendation` - Gate control recommendation

## MQTT Topics

### Publishing
- `water-level/sensors/{sensorId}/data` - Sensor readings
- `water-level/alerts/{severity}` - Alerts
- `water-level/gates/{gateId}/recommendations` - Gate recommendations

### Subscribing
- `sensors/water-level/+/data` - Raw sensor data
- `gates/+/commands` - Gate control commands

## Gate Control Logic

The service provides intelligent gate control recommendations based on:
1. Current water level
2. Rate of change
3. Target levels (min/max)
4. Historical patterns

Recommendations include:
- Action: open/close/maintain
- Percentage: 0-100% opening
- Confidence: 0-1 score
- Estimated time to reach target

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

```bash
# Build Docker image
docker build -t munbon/water-level-monitoring:latest .

# Run with Docker
docker run -p 3046:3046 munbon/water-level-monitoring:latest
```

## Integration

- **Kong API Gateway**: Exposed at `/api/v1/water-levels`
- **SCADA Service**: Sends gate recommendations when enabled
- **Notification Service**: Sends critical alerts
- **TimescaleDB**: Reads sensor data (read-only access)