# Sensor Data Service

This service handles IoT sensor data ingestion, processing, and real-time streaming for the Munbon Irrigation Control System.

## Features

- **Multi-protocol Support**: HTTP API, MQTT, WebSocket
- **Sensor Types**: Water level sensors (RID-R) and Moisture sensors (M2M)
- **AWS Integration**: Lambda functions for data ingestion via API Gateway
- **TimescaleDB**: Time-series data storage with PostGIS for geospatial queries
- **Real-time Streaming**: WebSocket and MQTT for live data updates
- **Mobile Sensor Support**: Track sensor location changes over time
- **Data Quality**: Automatic quality scoring and validation
- **Alerts**: Threshold-based alerting for critical conditions

## Architecture

```
┌─────────────────┐       ┌───────────────────────────────┐       ┌──────────────────┐
│   IoT Devices   │       │        AWS Cloud              │       │  Local Services  │
│                 │       │                               │       │                  │
│ ESP8266/ESP32   │──────►│ API Gateway → Lambda → SQS   │◄──────│ Consumer Service │
│ Water/Moisture  │ HTTP  │                               │ Poll  │ (SQS Poller)     │
└─────────────────┘       └───────────────────────────────┘       └──────────────────┘
                                                                            │
                                                                            ▼
                                                                   ┌──────────────────┐
                                                                   │ Local TimescaleDB│
                                                                   │                  │
                                                                   │ Time-series Data │
                                                                   │ PostGIS Spatial  │
                                                                   └──────────────────┘

Data Flow:
1. IoT devices send data to AWS API Gateway
2. Lambda function validates and puts data into SQS queue
3. Local consumer polls SQS and processes data
4. Consumer saves data to local TimescaleDB
5. Optional: Main sensor service provides APIs for data access
```

## AWS Deployment

### Prerequisites

1. AWS Account with credentials configured
2. Node.js 18.x or later
3. Serverless Framework: `npm install -g serverless`

### Deploy Lambda Functions

```bash
cd services/sensor-data/deployments/aws-lambda

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your AWS credentials and TimescaleDB connection

# Deploy to AWS
npm run deploy

# For production
npm run deploy:prod
```

### AWS Resources Created

- API Gateway with endpoints:
  - POST `/api/v1/{token}/telemetry` - Sensor data ingestion
  - GET `/api/v1/{token}/attributes` - Configuration endpoint
- Lambda Functions:
  - `telemetry` - Validates data and sends to SQS
  - `attributes` - Provides sensor configuration
- SQS Queue for reliable message delivery to local consumer
- Dead Letter Queue for failed messages

## Local Development

### Prerequisites

1. Docker and Docker Compose
2. Node.js 18.x or later
3. TimescaleDB running (via docker-compose)

### Setup

```bash
cd services/sensor-data

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Start TimescaleDB (from project root)
docker-compose up -d timescaledb

# Run the service
npm run dev

# In another terminal, run the SQS consumer
npm run consumer:dev
```

### Service Endpoints

- **Main Service**: http://localhost:3001
  - Health: GET `/health`
  - Sensor Data: GET `/api/v1/sensors/{sensorId}/data`
  - Active Sensors: GET `/api/v1/sensors/active`
  - Nearby Sensors: GET `/api/v1/sensors/nearby?lat=13.7563&lng=100.5018&radius=5`
  
- **Consumer Dashboard**: http://localhost:3002
  - Real-time sensor data visualization
  - Statistics and monitoring

- **MQTT Broker**: 
  - TCP: `mqtt://localhost:1883`
  - WebSocket: `ws://localhost:8083`

## Token Management

Tokens are structured as: `{area}-{manufacturer}-{sensor-type}`

Current tokens for Munbon area:
```
munbon-ridr-water-level  - RID-R water level sensors in Munbon
munbon-m2m-moisture      - M2M moisture sensors in Munbon
munbon-test-devices      - Test and development devices
```

Future expansion will support additional areas:
- `{other-area}-ridr-water-level` - RID-R sensors in other areas
- `{other-area}-m2m-moisture` - M2M sensors in other areas

## Sensor Data Formats

### Water Level Sensor (RID-R)

```json
{
  "deviceID": "7b184f4f-3d97-4c0c-a888-55b839aab7ad",
  "macAddress": "1A2B3C4D5E6F",
  "latitude": 13.7563,
  "longitude": 100.5018,
  "RSSI": -67,
  "voltage": 420,
  "level": 15,
  "timestamp": 1748841346551
}
```

### Moisture Sensor (M2M)

```json
{
  "gateway_id": "00001",
  "msg_type": "interval",
  "date": "2025/06/03",
  "time": "10:30:00",
  "latitude": "13.12345",
  "longitude": "100.54621",
  "gw_batt": "372",
  "sensor": [
    {
      "sensor_id": "00001",
      "flood": "no",
      "amb_humid": "60",
      "amb_temp": "40.50",
      "humid_hi": "50",
      "temp_hi": "25.50",
      "humid_low": "72",
      "temp_low": "25.00",
      "sensor_batt": "395"
    }
  ]
}
```

## Database Schema

The service uses TimescaleDB with PostGIS for efficient time-series and spatial queries:

- `sensor_registry` - Master list of all sensors
- `sensor_readings` - Generic sensor data (hypertable)
- `water_level_readings` - Specific water level data (hypertable)
- `moisture_readings` - Specific moisture data (hypertable)
- `sensor_location_history` - Track mobile sensor movements (hypertable)

## MQTT Topics

### Publishing (Sensors)
- `sensors/water-level/{sensorId}/data`
- `sensors/moisture/{sensorId}/data`
- `sensors/{type}/{sensorId}/status`

### Subscribing (Clients)
- `sensors/+/+/data` - All sensor data
- `sensors/water-level/+/data` - All water level data
- `sensors/moisture/+/data` - All moisture data
- `alerts/#` - All alerts

## WebSocket Events

### Client → Server
- `subscribe`: Subscribe to sensor updates
  ```json
  ["sensor:water-tank-01", "sensorType:water-level"]
  ```
- `unsubscribe`: Unsubscribe from updates

### Server → Client
- `sensorData`: Real-time sensor data
- `alert`: Threshold alerts

## Monitoring and Alerts

The service monitors sensor data and triggers alerts for:

### Water Level
- **Critical High**: > 25 cm
- **Warning Low**: < 5 cm

### Moisture
- **Warning Low**: < 20%
- **Flood Detected**: When flood status is true

## Testing

```bash
# Run tests
npm test

# Test with coverage
npm run test:coverage

# Test AWS Lambda locally
cd deployments/aws-lambda
npm run offline
```

## Production Deployment

### Kubernetes

```bash
# Build Docker image
docker build -t munbon/sensor-data-service:latest .

# Deploy to Kubernetes
kubectl apply -f deployments/k8s/
```

### Environment Variables

See `.env.example` for all configuration options. Key variables:

- `TIMESCALE_*` - TimescaleDB connection
- `AWS_*` - AWS credentials for SQS
- `MQTT_*` - MQTT broker configuration
- `VALID_TOKENS` - Device authentication tokens

## Troubleshooting

### Common Issues

1. **TimescaleDB Connection Failed**
   - Ensure TimescaleDB is running: `docker-compose ps`
   - Check connection settings in `.env`

2. **AWS Lambda Timeout**
   - Increase timeout in `serverless.yml`
   - Check VPC configuration if using private subnets

3. **MQTT Connection Refused**
   - Check MQTT broker is running
   - Verify token authentication

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=debug npm run dev
```

## License

Proprietary - Munbon Irrigation Project