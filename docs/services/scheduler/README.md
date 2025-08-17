# Weekly Batch Scheduler Service

## Overview

The Weekly Batch Scheduler Service is a core component of the Munbon Irrigation Control System that optimizes water distribution schedules while minimizing field team visits. It generates weekly operation schedules and provides real-time adaptation capabilities to handle unexpected events.

## Key Features

- **MILP Optimization**: Uses Mixed Integer Linear Programming to generate optimal schedules
- **Travel Optimization**: Minimizes field team travel using TSP algorithms
- **Real-time Adaptation**: Handles gate failures, weather changes, and demand variations
- **Field Instructions**: Generates human-readable instructions for field teams
- **WebSocket Monitoring**: Real-time status updates and alerts
- **Multi-team Coordination**: Optimizes operations across multiple field teams

## Architecture

### Core Components

1. **Optimization Engine** (`algorithms/`)
   - Mixed Integer Optimizer (PuLP)
   - Travel Optimizer (OR-Tools)
   - Constraint Builder

2. **Service Layer** (`services/`)
   - Schedule Optimizer
   - Demand Aggregator
   - Field Instruction Generator
   - Real-time Adapter

3. **API Layer** (`api/v1/`)
   - Schedule Management
   - Operations Tracking
   - Team Management
   - Real-time Monitoring
   - Adaptation Endpoints

## API Endpoints

### Schedule Management
- `POST /api/v1/schedule/generate` - Generate new schedule
- `GET /api/v1/schedule/{id}` - Get schedule details
- `POST /api/v1/schedule/{id}/approve` - Approve schedule
- `POST /api/v1/schedule/{id}/activate` - Activate schedule

### Operations
- `GET /api/v1/operations/schedule/{id}` - List operations
- `PATCH /api/v1/operations/{id}/status` - Update operation status
- `GET /api/v1/operations/today` - Get today's operations

### Teams
- `GET /api/v1/teams` - List teams
- `GET /api/v1/teams/{id}/instructions/{date}` - Get team instructions
- `POST /api/v1/teams/{id}/location` - Update team location

### Monitoring
- `GET /api/v1/monitoring/active-schedule` - Get active schedule status
- `GET /api/v1/monitoring/operations/progress` - Get real-time progress
- `WebSocket /api/v1/monitoring/ws` - Real-time updates

### Adaptation
- `POST /api/v1/adaptation/gate-failure` - Handle gate failures
- `POST /api/v1/adaptation/weather-change` - Handle weather changes
- `POST /api/v1/adaptation/reoptimize` - Trigger reoptimization

## Running the Service

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://user:pass@localhost/scheduler_db
export REDIS_URL=redis://localhost:6379
export JWT_SECRET_KEY=your-secret-key

# Run the service
python -m uvicorn src.main:app --reload --port 3021
```

### Docker

```bash
# Build image
docker build -t scheduler-service .

# Run container
docker run -p 3021:3021 \
  -e DATABASE_URL=postgresql://user:pass@db/scheduler_db \
  -e REDIS_URL=redis://redis:6379 \
  scheduler-service
```

## Environment Variables

- `SERVICE_PORT` - Service port (default: 3021)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `JWT_SECRET_KEY` - JWT signing key
- `ROS_SERVICE_URL` - ROS service URL
- `GIS_SERVICE_URL` - GIS service URL
- `FLOW_MONITORING_SERVICE_URL` - Flow monitoring service URL
- `LOG_LEVEL` - Logging level (default: INFO)

## Dependencies

### External Services
- PostgreSQL 15+ with PostGIS
- Redis 7+
- ROS Service (port 3009)
- GIS Service (port 3007)
- Flow Monitoring Service (port 3003)

### Python Libraries
- FastAPI - Web framework
- SQLAlchemy - ORM
- PuLP - MILP solver
- OR-Tools - Routing optimization
- Redis - Caching and pub/sub
- ReportLab - PDF generation

## Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run integration tests
pytest tests/integration/
```

## Optimization Model

The scheduler uses a Mixed Integer Linear Programming model with the following objectives:

### Minimize:
1. Total travel distance for field teams
2. Number of gate changes
3. Water spillage/wastage

### Subject to:
1. Water demand satisfaction constraints
2. Canal capacity constraints
3. Hydraulic relationship constraints
4. Team capacity constraints
5. Gravity flow sequencing
6. Water continuity at nodes

## Real-time Adaptation

The service can adapt to real-time events:

1. **Gate Failures**: Reroutes water through alternative paths
2. **Weather Changes**: Adjusts demands based on rainfall/ET
3. **Emergency Requests**: Handles urgent water needs
4. **Team Unavailability**: Reassigns operations to available teams

## Performance

- Schedule generation: < 30 seconds for 500+ operations
- API response time: < 100ms (p95)
- WebSocket latency: < 50ms
- Handles 10,000+ concurrent connections

## License

Proprietary - Munbon Irrigation Project