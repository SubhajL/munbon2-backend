# AWD Control Service

Alternate Wetting and Drying (AWD) Control Service for the Munbon Irrigation System. This service manages automated irrigation control for rice fields using AWD technique to optimize water usage while maintaining crop yield.

## Features

- Real-time AWD sensor integration and monitoring
- Growth stage-aware irrigation scheduling
- Automated gate/pump control based on water level thresholds
- Water savings analytics and reporting
- Multi-field coordination and priority-based allocation
- Emergency irrigation overrides

## Technology Stack

- **Runtime**: Node.js 18 with TypeScript
- **Framework**: Express.js
- **Databases**: 
  - PostgreSQL (configuration and field data)
  - TimescaleDB (time-series sensor data)
  - Redis DB 11 (state management and caching)
- **Message Broker**: Apache Kafka
- **Logging**: Pino

## Quick Start

### Prerequisites

- Node.js 18+
- PostgreSQL 14+
- TimescaleDB 2.9+
- Redis 7+
- Apache Kafka 3.0+

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Run in development mode
npm run dev
```

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Generate coverage report
npm run test:coverage
```

### Building for Production

```bash
# Build TypeScript
npm run build

# Run production build
npm start
```

## API Endpoints

### Field Management
- `GET /api/v1/awd/fields` - List AWD-enabled fields
- `GET /api/v1/awd/fields/:fieldId/status` - Current AWD status
- `GET /api/v1/awd/fields/:fieldId/sensors` - Field sensor readings
- `GET /api/v1/awd/fields/:fieldId/history` - AWD cycle history
- `POST /api/v1/awd/fields/:fieldId/control` - Manual control override
- `PUT /api/v1/awd/fields/:fieldId/config` - Update AWD parameters

### Analytics
- `GET /api/v1/awd/analytics/water-savings` - Water savings reports
- `GET /api/v1/awd/analytics/yield-impact` - Yield impact analysis

### System
- `GET /health` - Service health check
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

## Configuration

Key environment variables:

```bash
# Service
PORT=3010
NODE_ENV=development

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=munbon_awd

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=munbon_timeseries

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=11

# Kafka
KAFKA_BROKERS=localhost:9092
KAFKA_CLIENT_ID=awd-control-service

# AWD Parameters
DEFAULT_DRYING_DEPTH=15
SAFE_AWD_DEPTH=10
EMERGENCY_THRESHOLD=25
```

## AWD Control Algorithm

The service implements a sophisticated AWD control algorithm that considers:

1. **Growth Stage Management**
   - Vegetative stage: Flexible AWD (15-20cm below surface)
   - Reproductive stage: Safe AWD (10cm below surface)
   - Maturation stage: Terminal drying

2. **Water Level Monitoring**
   - Real-time sensor data processing
   - Predictive irrigation timing
   - Emergency threshold detection

3. **Irrigation Optimization**
   - Queue-based scheduling
   - Priority allocation
   - Water availability coordination

## Docker Support

```bash
# Build image
docker build -t awd-control-service .

# Run container
docker run -p 3010:3010 --env-file .env awd-control-service
```

## Monitoring

The service exposes metrics including:
- AWD adoption rate by zone
- Water savings per field
- Irrigation event frequency
- Sensor reliability metrics
- System performance metrics

## License

MIT