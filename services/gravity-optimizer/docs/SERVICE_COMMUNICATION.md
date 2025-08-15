# Service Discovery and Inter-Service Communication

## Overview

The Gravity Optimizer service implements a comprehensive inter-service communication system that enables it to:
- Discover and connect to other microservices dynamically
- Fetch real-time data from multiple sources
- Coordinate control actions across services
- Report results and maintain system consistency

## Architecture

### Service Registry
- **Backend**: Redis-based service registry with automatic failover to static configuration
- **Service Discovery**: Dynamic service lookup with health checking
- **Heartbeat**: Automatic service registration and heartbeat mechanism
- **TTL**: 5-minute TTL with 1-minute heartbeat interval

### Client Architecture
```
BaseServiceClient (base_client.py)
├── Circuit Breaker Pattern
├── Exponential Backoff Retry
├── Request ID Tracking
└── Async HTTP Client (httpx)
    ├── GISClient
    ├── ROSClient
    ├── SCADAClient
    ├── WeatherClient
    └── SensorDataClient
```

## Service Clients

### 1. GIS Client (`gis_client.py`)
Handles spatial data and network topology:
- **Channel Network**: Get channel geometries and connections
- **Zone Boundaries**: Retrieve irrigation zone boundaries
- **Elevation Data**: Query elevation at specific points
- **Routing**: Find optimal paths through the network

```python
# Example usage
gis_client = GISClient()
channels = await gis_client.get_channel_network()
zones = await gis_client.get_zone_boundaries()
```

### 2. ROS Client (`ros_client.py`)
Interfaces with Resource Optimization Service:
- **Water Allocations**: Get current allocations per zone
- **Demand Forecasts**: Retrieve water demand predictions
- **Schedules**: Access irrigation schedules
- **Reporting**: Report delivery results

```python
# Example usage
ros_client = ROSClient()
allocations = await ros_client.get_current_allocations()
await ros_client.report_delivery_status(zone_id, volume, flow_rate, efficiency, start, end)
```

### 3. SCADA Client (`scada_client.py`)
Controls and monitors physical infrastructure:
- **Gate Control**: Send opening/closing commands
- **Status Monitoring**: Real-time gate positions
- **Batch Operations**: Control multiple gates simultaneously
- **Emergency Stop**: Safety shutdown procedures

```python
# Example usage
scada_client = SCADAClient()
gate_status = await scada_client.get_gate_status("gate_1")
await scada_client.control_gate(GateControl(gate_id="gate_1", target_opening=0.5))
```

### 4. Weather Client (`weather_client.py`)
Provides weather data and forecasts:
- **Current Conditions**: Temperature, humidity, rainfall
- **Forecasts**: Multi-day weather predictions
- **ET Calculations**: Evapotranspiration values
- **Irrigation Suitability**: Weather-based recommendations

```python
# Example usage
weather_client = WeatherClient()
conditions = await weather_client.check_irrigation_conditions()
forecast = await weather_client.get_forecast(days=7)
```

### 5. Sensor Data Client (`sensor_client.py`)
Real-time sensor data access:
- **Water Levels**: Channel water level readings
- **Flow Rates**: Flow meter measurements
- **Gate Sensors**: Position and vibration data
- **Anomaly Detection**: Sensor anomaly alerts

```python
# Example usage
sensor_client = SensorDataClient()
water_levels = await sensor_client.get_water_levels()
flow_rates = await sensor_client.get_flow_rates()
```

## Circuit Breaker Pattern

Each service client implements a circuit breaker to handle failures gracefully:

### States
1. **CLOSED**: Normal operation, requests pass through
2. **OPEN**: Service failing, requests rejected immediately
3. **HALF_OPEN**: Testing if service has recovered

### Configuration
- **Failure Threshold**: 5 consecutive failures trigger circuit open
- **Recovery Timeout**: 60 seconds before attempting reset
- **Retry Logic**: Exponential backoff with max 3 retries

## Request Flow

### Integrated Optimization Flow
```
1. OptimizationRequest arrives at Gravity Optimizer
   │
2. Fetch allocations from ROS
   │
3. Check weather conditions
   │
4. Get real-time sensor data
   │
5. Retrieve current gate positions from SCADA
   │
6. Load network topology from GIS (cached)
   │
7. Run hydraulic optimization algorithm
   │
8. Execute gate controls via SCADA
   │
9. Monitor and verify gate movements
   │
10. Report results back to ROS
```

## API Endpoints

### Integrated Optimization Endpoints
- `POST /api/v1/gravity-optimizer/integrated/optimize/realtime` - Full optimization with real data
- `GET /api/v1/gravity-optimizer/integrated/health` - Check all service connections
- `GET /api/v1/gravity-optimizer/integrated/status` - System-wide status
- `POST /api/v1/gravity-optimizer/integrated/emergency/stop` - Emergency shutdown

## Configuration

### Environment Variables
```bash
# Service URLs (fallback when Redis unavailable)
GIS_SERVICE_URL=http://localhost:3007
ROS_SERVICE_URL=http://localhost:3047
SCADA_SERVICE_URL=http://localhost:3008
WEATHER_SERVICE_URL=http://localhost:3009
SENSOR_DATA_SERVICE_URL=http://localhost:3003

# Redis configuration
REDIS_URL=redis://localhost:6379
SERVICE_REGISTRY_NAMESPACE=munbon:services
SERVICE_REGISTRY_TTL=300
```

### Service Registration
Services automatically register on startup:
```python
service_info = ServiceInfo(
    name='gravity-optimizer',
    version='1.0.0',
    url='http://localhost:3020',
    health_endpoint='/health',
    tags=['optimization', 'hydraulics', 'gravity'],
    metadata={
        'zones': 6,
        'automated_gates': 20
    }
)
```

## Error Handling

### Graceful Degradation
- If a service is unavailable, the optimizer can:
  - Use cached data where appropriate
  - Fall back to default values
  - Continue with partial optimization
  - Log warnings but not fail completely

### Monitoring
- All service calls are logged with request IDs
- Circuit breaker state changes are logged
- Failed requests include retry attempts
- Health checks run periodically

## Testing

### Running the Example
```bash
cd examples
python service_communication_example.py
```

### Mocking Services
For testing without all services running:
```python
# Services will fall back to static configuration
# No actual communication occurs, but structure is preserved
```

## Performance Considerations

### Caching
- Network topology cached for 1 hour
- Service discovery results cached for 30 seconds
- Static fallback configuration always available

### Concurrent Requests
- All service clients use connection pooling
- Max 10 connections per service
- 30-second default timeout (configurable)

### Optimization
- Parallel service calls where possible
- Batch operations for multiple gates
- Async/await throughout for non-blocking I/O

## Security

### Authentication
- Service-to-service authentication via headers
- X-Service-Name header identifies caller
- X-Request-ID for request tracking

### Network Security
- HTTPS recommended for production
- Service mesh integration ready
- API gateway compatible

## Future Enhancements

1. **WebSocket Support**: Real-time updates from SCADA/sensors
2. **GraphQL Integration**: More efficient data fetching
3. **Service Mesh**: Istio/Linkerd integration
4. **Distributed Tracing**: OpenTelemetry support
5. **Message Queue**: Kafka integration for event-driven updates