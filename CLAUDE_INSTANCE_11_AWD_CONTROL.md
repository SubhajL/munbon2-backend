# Claude Instance 11: AWD Control Service

## Overview
I am responsible for implementing the Alternate Wetting and Drying (AWD) Control Service, a specialized microservice for automated AWD irrigation control in rice fields. This technique optimizes water usage while maintaining crop yield through intelligent irrigation scheduling.

## My Services

### Primary Service
- **AWD Control Service** (Port 3010)
  - Path: `/services/awd-control`
  - AWD sensor integration and monitoring
  - Automated irrigation control based on water level thresholds
  - Growth stage-aware irrigation scheduling
  - Water savings optimization
  - Integration with gate/pump control systems

### Shared Services
- **Sensor Data Service** (Port 3003) - For AWD sensor data ingestion
- **Water Distribution Control** - For gate/valve operations

## My Responsibilities

### 1. AWD Sensor Management
- Integrate AWD-Series sensors from RID-R
- Process real-time water level measurements
- Validate sensor readings and handle failures
- Maintain sensor calibration data
- Track sensor health and reliability

### 2. AWD Control Algorithm
- Implement standard AWD thresholds (15-20 cm below soil surface)
- Configure field-specific drying depths
- Manage growth stage transitions:
  - Vegetative stage (flexible AWD)
  - Reproductive stage (safe AWD)
  - Maturation stage (terminal drying)
- Dynamic threshold adjustments based on weather
- Multi-field coordination for water distribution

### 3. Irrigation Control
- Automated gate/valve control signals
- Pump operation scheduling
- Queue-based irrigation management
- Priority-based water allocation
- Conflict resolution for concurrent requests
- Emergency irrigation overrides

### 4. API Endpoints
```
GET  /api/v1/awd/fields                    - List AWD-enabled fields
GET  /api/v1/awd/fields/:fieldId/status    - Current AWD status
GET  /api/v1/awd/fields/:fieldId/sensors   - Field sensor readings
GET  /api/v1/awd/fields/:fieldId/history   - AWD cycle history
POST /api/v1/awd/fields/:fieldId/control   - Manual control override
PUT  /api/v1/awd/fields/:fieldId/config    - Update AWD parameters
GET  /api/v1/awd/analytics/water-savings   - Water savings reports
GET  /api/v1/awd/analytics/yield-impact    - Yield impact analysis
POST /api/v1/awd/schedules                 - Create irrigation schedules
GET  /api/v1/awd/recommendations           - AWD recommendations
```

### 5. Water Savings Analytics
- Track water usage per AWD cycle
- Compare with traditional flooding baseline
- Calculate cumulative water savings
- Generate efficiency reports
- Monitor yield impact correlations

### 6. Integration Points
- **Sensor Data Service**: AWD sensor data stream
- **Water Level Monitoring**: Canal water availability
- **Water Distribution Control**: Gate/pump operations
- **Weather Monitoring**: Rainfall and ET data
- **Crop Management**: Growth stage information
- **Alert Service**: Threshold breach notifications

## Technical Stack
- **Language**: Node.js with TypeScript
- **Framework**: Express.js
- **Database**: 
  - TimescaleDB for time-series sensor data
  - PostgreSQL for configuration and field data
- **Queue**: Redis for irrigation scheduling
- **Cache**: Redis DB 11 for AWD state management
- **Message Broker**: Kafka topics:
  - `awd.sensor.data`
  - `awd.control.commands`
  - `awd.irrigation.events`

## Key Features

### AWD Cycle Management
1. **Wetting Phase**
   - Flood field to 5-10 cm depth
   - Monitor filling rate
   - Track water consumption
   
2. **Drying Phase**
   - Monitor water depletion rate
   - Track soil moisture levels
   - Predict next irrigation timing

3. **Cycle Optimization**
   - Adjust based on weather forecasts
   - Consider crop water demand
   - Optimize for water availability

### Safety Features
- Critical growth stage protection
- Emergency irrigation triggers
- Manual override capabilities
- Sensor failure fallbacks
- Water stress prevention

## Development Guidelines
1. Follow TypeScript best practices
2. Implement comprehensive error handling
3. Use dependency injection patterns
4. Write extensive unit tests
5. Document all control algorithms
6. Implement circuit breakers for external services
7. Use structured logging with correlation IDs

## Testing Requirements
- Unit tests for control algorithms
- Integration tests with mock sensors
- Load tests for multi-field scenarios
- Failover and recovery tests
- Water savings calculation validation

## Monitoring & Metrics
- AWD adoption rate by zone
- Water savings per field
- Irrigation event frequency
- Sensor reliability metrics
- Control response times
- System error rates

## Environment Variables
```bash
# Service Configuration
SERVICE_NAME=awd-control-service
PORT=3010

# Database Connections
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=11

# Kafka Configuration
KAFKA_BROKERS=localhost:9092

# AWD Parameters
DEFAULT_DRYING_DEPTH=15
SAFE_AWD_DEPTH=10
EMERGENCY_THRESHOLD=25

# Integration Services
SENSOR_DATA_URL=http://localhost:3003
WATER_DISTRIBUTION_URL=http://localhost:3020
```

## Success Criteria
1. Automated AWD control for 1000+ fields
2. 20-30% water savings vs traditional flooding
3. < 5% yield impact
4. 99.9% sensor data capture rate
5. < 1 minute irrigation response time
6. Zero critical stage water stress events

## Related Documentation
- Task #57: Implement AWD Control Service
- AWD Best Practices Guide
- Sensor Integration Specifications
- Water Distribution API Documentation