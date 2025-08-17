# Flow Monitoring Service

Comprehensive hydraulic monitoring service for the Munbon Irrigation System, providing real-time flow rates, water volumes, and level monitoring with advanced analytics.

## Overview

The Flow Monitoring Service is a Python-based microservice that:
- Processes real-time sensor data from multiple flow meters
- Calculates flow rates, velocities, and cumulative volumes
- Performs water balance analysis and loss detection
- Provides hydraulic modeling for ungauged locations
- Detects anomalies using machine learning algorithms
- Offers predictive analytics for flow forecasting

## Features

### Core Capabilities
- **Multi-sensor Fusion**: Combines data from ultrasonic, electromagnetic, and mechanical flow meters
- **Real-time Processing**: Handles 10,000+ sensor readings per second
- **Flow Calculations**: Implements Manning's equation, velocity-area method, and rating curves
- **Volume Integration**: Time-based integration with gap handling
- **Water Balance**: Inflow vs outflow analysis with loss detection
- **Hydraulic Modeling**: Saint-Venant equations for ungauged locations
- **Anomaly Detection**: Statistical and ML-based anomaly detection
- **Predictive Analytics**: Flow forecasting using time-series models

## Architecture

### Technology Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Databases**: 
  - InfluxDB (time-series data)
  - TimescaleDB (aggregated data)
  - PostgreSQL (configuration)
  - Redis (caching)
- **Message Queue**: Apache Kafka
- **Monitoring**: Prometheus metrics

### Service Ports
- **API**: 3011
- **Metrics**: 3011/metrics

## API Endpoints

### Flow Data
- `GET /api/v1/flow/realtime` - Real-time flow rates
- `GET /api/v1/flow/history` - Historical flow data
- `POST /api/v1/flow/ingest` - Ingest sensor data
- `GET /api/v1/flow/latest/{location_id}` - Latest reading
- `GET /api/v1/flow/statistics/{location_id}` - Flow statistics

### Volume Data
- `GET /api/v1/volume/cumulative` - Cumulative volumes
- `GET /api/v1/volume/balance` - Water balance analysis
- `GET /api/v1/volume/daily` - Daily volume totals

### Water Level
- `GET /api/v1/level/current` - Current water levels
- `GET /api/v1/level/forecast` - Level predictions

### Analytics
- `GET /api/v1/analytics/efficiency` - Network efficiency
- `GET /api/v1/analytics/losses` - Loss analysis
- `GET /api/v1/alerts/anomalies` - Anomaly detections

### Sensors
- `POST /api/v1/sensors/calibrate` - Sensor calibration
- `GET /api/v1/sensors/health` - Sensor health metrics

### Hydraulic Modeling
- `GET /api/v1/hydraulics/model` - Model results
- `POST /api/v1/model/propagation` - Water propagation

## Installation

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Access to required databases

### Local Development

1. Clone the repository
2. Copy environment file:
   ```bash
   cp .env.example .env
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the service:
   ```bash
   cd src
   python main.py
   ```

### Docker Deployment

```bash
docker build -t flow-monitoring:latest .
docker run -p 3011:3011 --env-file .env flow-monitoring:latest
```

## Configuration

Key environment variables:

```bash
# Service
SERVICE_NAME=flow-monitoring
PORT=3011
LOG_LEVEL=INFO

# InfluxDB
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=munbon
INFLUXDB_BUCKET=flow-data

# TimescaleDB
TIMESCALE_URL=postgresql://user:pass@localhost:5433/munbon_timescale

# Redis
REDIS_URL=redis://localhost:6379/12

# Kafka
KAFKA_BROKERS=localhost:9092
KAFKA_TOPIC_SENSORS=flow.sensor.data

# Model Configuration
MODEL_UPDATE_INTERVAL=300
ANOMALY_THRESHOLD=3.0
FORECAST_HORIZON=24
```

## Data Flow

1. **Sensor Data Ingestion**
   - Sensors → Kafka → Flow Monitoring Service → InfluxDB

2. **Real-time Processing**
   - InfluxDB → Flow calculations → Redis cache → API response

3. **Aggregation Pipeline**
   - InfluxDB → Aggregation → TimescaleDB → Analytics

4. **Anomaly Detection**
   - Real-time data → ML models → Anomaly flags → Alert service

## Algorithms

### Flow Rate Calculation
- **Manning's Equation**: Q = (1/n) × A × R^(2/3) × S^(1/2)
- **Velocity-Area Method**: Q = Σ(v_i × A_i)
- **Rating Curves**: Q = a × (h - h₀)^b

### Water Propagation
- **Saint-Venant Equations**: 
  - Continuity: ∂A/∂t + ∂Q/∂x = q_l
  - Momentum: ∂Q/∂t + ∂(Q²/A)/∂x + gA(∂h/∂x) = gA(S₀ - Sf)

### Anomaly Detection
- Statistical Process Control (SPC)
- Isolation Forest for outliers
- LSTM for temporal patterns
- Kalman filtering for sensor fusion

## Monitoring

### Health Check
```bash
curl http://localhost:3011/health
```

### Prometheus Metrics
- `flow_monitoring_sensor_readings_total`
- `flow_monitoring_current_flow_rate`
- `flow_monitoring_water_level`
- `flow_monitoring_anomalies_detected_total`
- `flow_monitoring_model_accuracy`

## Performance

- Process 10,000+ sensor readings/second
- Sub-second flow calculations
- 5-minute forecast updates
- 99.9% data capture rate
- < 100ms API response time

## Integration

### Upstream Dependencies
- Sensor Data Service: Raw sensor feeds
- GIS Service: Network topology
- Weather Monitoring: Rainfall data

### Downstream Services
- Alert Service: Anomaly notifications
- Dashboard BFF: Visualization data
- Water Control Service: Optimization inputs

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
black src/
flake8 src/
mypy src/
```

## License

Proprietary - Munbon Irrigation Project