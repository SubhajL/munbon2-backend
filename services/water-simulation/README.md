# Water Simulation Service

A comprehensive simulation service for modeling and optimizing water distribution in irrigation systems.

## Features

- **Scenario-based Simulation**: Create and manage multiple simulation scenarios with different parameters
- **Multi-objective Optimization**: Optimize for water efficiency, fairness, or energy consumption
- **Service Integration**: Integrates with ROS, Flow Monitoring, Gate Control, and GIS services
- **Comprehensive Analysis**: Detailed performance analysis and recommendations
- **What-if Analysis**: Compare multiple scenarios to find optimal strategies

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   API Routes    │────▶│ Simulation      │────▶│    Database     │
│   (FastAPI)     │     │    Engine       │     │  (PostgreSQL)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Service Clients │     │   Optimizers    │
│ (ROS/Flow/Gate) │     │ (Multi-objective)│
└─────────────────┘     └─────────────────┘
```

## Quick Start

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export SIMULATION_POSTGRES_HOST=localhost
export SIMULATION_POSTGRES_USER=postgres
export SIMULATION_POSTGRES_PASSWORD=postgres
export SIMULATION_POSTGRES_DB=water_simulation
```

3. Run database migrations:
```bash
alembic upgrade head
```

4. Start the service:
```bash
python -m src.main
```

### Docker

```bash
docker-compose up -d
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8090/docs
- ReDoc: http://localhost:8090/redoc

### Key Endpoints

#### Scenarios
- `POST /api/v1/scenarios` - Create a new scenario
- `GET /api/v1/scenarios` - List all scenarios
- `GET /api/v1/scenarios/{id}` - Get scenario details
- `PUT /api/v1/scenarios/{id}` - Update scenario
- `DELETE /api/v1/scenarios/{id}` - Delete scenario

#### Simulations
- `POST /api/v1/simulations` - Start a new simulation
- `GET /api/v1/simulations/{id}` - Get simulation status
- `PUT /api/v1/simulations/{id}/cancel` - Cancel simulation
- `GET /api/v1/simulations/{id}/states` - Get simulation states

#### Analysis
- `POST /api/v1/simulations/{id}/analyze` - Run analysis
- `GET /api/v1/simulations/{id}/analysis` - Get analysis results
- `POST /api/v1/scenarios/compare` - Compare multiple scenarios

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| SIMULATION_POSTGRES_HOST | PostgreSQL host | localhost |
| SIMULATION_POSTGRES_PORT | PostgreSQL port | 5432 |
| SIMULATION_POSTGRES_DB | Database name | water_simulation |
| SIMULATION_REDIS_HOST | Redis host | localhost |
| SIMULATION_REDIS_PORT | Redis port | 6379 |
| SIMULATION_ROS_SERVICE_URL | ROS service URL | http://localhost:8001 |
| SIMULATION_FLOW_SERVICE_URL | Flow service URL | http://localhost:8002 |
| SIMULATION_GATE_SERVICE_URL | Gate service URL | http://localhost:8003 |
| SIMULATION_GIS_SERVICE_URL | GIS service URL | http://localhost:8004 |

### Simulation Parameters

- **Time Step**: Configurable from 15 minutes to 24 hours
- **Duration**: Up to 365 days
- **Optimization**: Water efficiency, fairness, energy, or multi-objective

## Testing

Run unit tests:
```bash
pytest tests/unit/
```

Run integration tests:
```bash
pytest tests/integration/
```

Run all tests with coverage:
```bash
pytest --cov=src tests/
```

## Database Schema

The service uses PostgreSQL with the following main tables:

- `scenarios` - Simulation scenario configurations
- `runs` - Individual simulation run instances
- `states` - Time-series simulation states
- `section_demands` - Section-specific demand overrides
- `gate_operations` - Scheduled gate operations
- `optimization_results` - Optimization algorithm results
- `analysis_results` - Post-simulation analysis

## Integration with Other Services

### ROS (River Operation System)
- Water demand calculations
- Crop coefficients
- Water level data

### Flow Monitoring Service
- Gate flow calculations
- Hydraulic modeling
- Job order creation

### Gate Control Service
- Gate status and control
- Discrete control levels
- Maintenance schedules

### GIS Service
- Section spatial data
- Network topology
- Service area calculations

## Optimization Algorithms

### Water Efficiency
Maximizes the ratio of water delivered to water used, minimizing losses.

### Fairness (Jain's Index)
Ensures equitable distribution among all sections using max-min fairness.

### Energy Minimal
Minimizes gate movements and pumping energy consumption.

### Multi-objective
Balances efficiency (40%), fairness (40%), and energy (20%).

## Performance Considerations

- Uses async/await for non-blocking I/O
- Implements connection pooling for database
- Caches frequently accessed data (network topology, gate properties)
- Supports horizontal scaling via Kubernetes HPA

## Monitoring

- Health check endpoint: `/health`
- Prometheus metrics: `/metrics` (when enabled)
- Structured logging with correlation IDs
- Performance tracking for optimization algorithms

## Contributing

1. Create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Submit pull request

## License

Proprietary - Munbon Irrigation Project