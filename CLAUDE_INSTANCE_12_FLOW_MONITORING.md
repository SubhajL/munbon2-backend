# Claude Instance 12: Flow/Volume/Level Monitoring Service

## Overview
I am responsible for implementing the Flow/Volume/Level Monitoring Service, a Python-based microservice for comprehensive hydraulic monitoring including flow rates, water volumes, and levels across the entire irrigation network with advanced analytics.

## My Services

### Primary Service
- **Flow Monitoring Service** (Port 3011)
  - Path: `/services/flow-monitoring`
  - Multi-parameter sensor fusion
  - Real-time flow rate calculations
  - Volume integration and water balance
  - Hydraulic modeling for ungauged locations
  - Anomaly detection and predictive analytics

### Database Connections
- **InfluxDB** (Port 8086) - High-frequency sensor data
- **TimescaleDB** (Port 5433) - Aggregated hydraulic data
- **PostgreSQL** (Port 5434) - Configuration and metadata

## My Responsibilities

### 1. Sensor Data Integration
- Support multiple sensor types:
  - Ultrasonic flow meters
  - Electromagnetic flow meters
  - Mechanical flow meters
  - Pressure transducers
  - Water level sensors
- Implement sensor fusion algorithms
- Handle different data protocols and formats
- Validate and calibrate sensor readings

### 2. Flow Rate Calculations
- Instantaneous flow rate computation
- Velocity-area method implementation
- Manning's equation for open channels
- Weir and orifice flow calculations
- Rating curve applications
- Real-time flow estimation

### 3. Volume Integration
- Cumulative volume calculations
- Time-based integration algorithms
- Handle data gaps and interpolation
- Daily/monthly/seasonal volumes
- Water accounting and budgeting

### 4. Hydraulic Modeling
- Model flow in ungauged locations
- Saint-Venant equations implementation
- HEC-RAS integration capabilities
- Network hydraulic simulation
- Backwater effect calculations
- Flood routing algorithms

### 5. Water Balance & Loss Detection
- Inflow vs outflow analysis
- Seepage and evaporation estimates
- Leak detection algorithms
- Network efficiency calculations
- Loss localization techniques
- Real-time balance monitoring

### 6. API Endpoints
```
GET  /api/v1/flow/realtime                    - Current flow rates
GET  /api/v1/flow/history                     - Historical flow data
GET  /api/v1/volume/cumulative                - Cumulative volumes
GET  /api/v1/volume/balance                   - Water balance analysis
GET  /api/v1/level/current                    - Current water levels
GET  /api/v1/level/forecast                   - Level predictions
POST /api/v1/sensors/calibrate                - Sensor calibration
GET  /api/v1/hydraulics/model                 - Hydraulic model results
GET  /api/v1/analytics/efficiency             - Network efficiency
GET  /api/v1/analytics/losses                 - Loss analysis
GET  /api/v1/alerts/anomalies                 - Anomaly detections
POST /api/v1/model/propagation                - Water propagation simulation
```

### 7. Analytics & Predictions
- Flow forecasting using ML models
- Pattern recognition for demand
- Seasonal trend analysis
- Anomaly detection algorithms
- Predictive maintenance alerts
- Optimization recommendations

## Technical Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Async**: asyncio, aiohttp
- **Numerical**: NumPy, SciPy, Pandas
- **ML/AI**: scikit-learn, TensorFlow/PyTorch
- **Visualization**: Matplotlib, Plotly
- **Databases**: 
  - InfluxDB (time-series)
  - TimescaleDB (aggregated)
  - Redis (caching)
- **Message Queue**: Kafka for sensor streams

## Key Algorithms

### Flow Calculation
```python
# Manning's Equation
Q = (1/n) * A * R^(2/3) * S^(1/2)
# Q = flow rate, n = roughness, A = area, R = hydraulic radius, S = slope

# Continuity Equation
Q_in = Q_out + ΔStorage/Δt

# Velocity-Area Method
Q = Σ(v_i * A_i) for all subsections
```

### Water Propagation
```python
# Saint-Venant Equations (1D)
∂A/∂t + ∂Q/∂x = q_l  # Continuity
∂Q/∂t + ∂(Q²/A)/∂x + gA(∂h/∂x) = gA(S_0 - S_f) # Momentum
```

### Anomaly Detection
- Statistical process control (SPC)
- Isolation Forest for outliers
- LSTM for temporal anomalies
- Kalman filtering for sensor fusion

## Development Guidelines
1. Use type hints and pydantic models
2. Implement comprehensive error handling
3. Follow PEP 8 style guide
4. Write unit tests with pytest
5. Document all algorithms
6. Use async/await for I/O operations
7. Implement data validation

## Integration Points
- **Sensor Data Service**: Raw sensor feeds
- **GIS Service**: Network topology
- **Weather Monitoring**: Rainfall data
- **ROS Service**: Runoff predictions
- **Alert Service**: Anomaly notifications
- **Dashboard BFF**: Visualization data

## Performance Requirements
- Process 10,000+ sensor readings/second
- Sub-second flow calculations
- 5-minute forecast updates
- 99.9% data capture rate
- < 100ms API response time
- Real-time anomaly detection

## Monitoring & Metrics
- Sensor data ingestion rate
- Calculation latency
- Model accuracy metrics
- Water balance closure
- Anomaly detection rate
- API response times

## Environment Variables
```bash
# Service Configuration
SERVICE_NAME=flow-monitoring
PORT=3011

# Database Connections
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=local-dev-token
INFLUXDB_ORG=munbon
INFLUXDB_BUCKET=flow-data

TIMESCALE_URL=postgresql://postgres:postgres@localhost:5433/munbon_timescale
POSTGRES_URL=postgresql://postgres:postgres@localhost:5434/munbon_dev

# Redis Configuration
REDIS_URL=redis://localhost:6379/12

# Kafka Configuration
KAFKA_BROKERS=localhost:9092
KAFKA_TOPIC_SENSORS=flow.sensor.data
KAFKA_TOPIC_ANALYTICS=flow.analytics.results

# Model Configuration
MODEL_UPDATE_INTERVAL=300  # 5 minutes
ANOMALY_THRESHOLD=3.0  # Standard deviations
FORECAST_HORIZON=24  # hours
```

## Data Schema

### InfluxDB (Time-Series)
```
measurement: flow_data
tags:
  - sensor_id
  - sensor_type
  - location_id
  - channel_id
fields:
  - flow_rate (m³/s)
  - velocity (m/s)
  - water_level (m)
  - pressure (kPa)
  - quality_flag
time: timestamp
```

### TimescaleDB (Aggregated)
```sql
CREATE TABLE flow_aggregates (
  time TIMESTAMPTZ NOT NULL,
  location_id UUID NOT NULL,
  avg_flow_rate DECIMAL(10,3),
  max_flow_rate DECIMAL(10,3),
  min_flow_rate DECIMAL(10,3),
  total_volume DECIMAL(12,3),
  water_level DECIMAL(8,3),
  PRIMARY KEY (time, location_id)
);
```

## Success Criteria
1. Real-time flow monitoring for entire network
2. < 5% measurement uncertainty
3. 95% accuracy in loss detection
4. 85% accuracy in 24-hour forecasts
5. Automated anomaly detection
6. Complete water balance accounting

## Related Documentation
- Task #50: Implement Flow/Volume/Level Monitoring Service
- Hydraulic Modeling Guidelines
- Sensor Calibration Procedures
- Water Balance Methodology