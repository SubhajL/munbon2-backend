# Water Planning BFF Service

Backend for Frontend service that optimizes water demand planning with AWD (Alternate Wetting and Drying) integration for the Munbon Irrigation System.

## Overview

The Water Planning BFF Service acts as an intelligent orchestration layer between frontend applications (web, mobile, API clients) and backend microservices. It provides:

- **Client-specific data transformation** - Optimized responses for mobile vs web clients
- **Request aggregation** - Combines multiple backend calls into single GraphQL queries
- **AWD Integration** - Smart water conservation through AWD control
- **Real-time updates** - GraphQL subscriptions for live data
- **Performance optimization** - DataLoader pattern prevents N+1 queries

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Web App    │     │ Mobile App  │     │  API Client │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                          │
                    ┌─────▼──────┐
                    │            │
                    │  BFF Water │◄─── GraphQL API
                    │  Planning   │
                    │            │
                    └─────┬──────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
   │   ROS   │      │   GIS   │      │   AWD   │
   │ Service │      │ Service │      │ Control │
   └─────────┘      └─────────┘      └─────────┘
```

## Features

### 1. GraphQL API
- Flexible query language
- Type-safe schema
- Real-time subscriptions
- GraphiQL interface in development

### 2. Client-Specific Optimizations
- **Mobile**: Lightweight responses, reduced data transfer
- **Web**: Full detailed data with charting support
- **API**: Raw data format for integrations

### 3. AWD Integration
- Real-time moisture monitoring
- Automated AWD recommendations
- Water savings calculations
- Plot-level and section-level aggregation

### 4. Performance Features
- DataLoader for batch loading
- Connection pooling
- Redis caching
- Request deduplication

## API Examples

### Query Section with AWD Status
```graphql
query GetSectionDetails {
  section(id: "1A-001") {
    sectionId
    sectionName
    currentDemand {
      volumeM3
      method
      calculatedAt
    }
    awdStatus {
      isActive
      plotsWithAwd
      expectedSavingsM3
    }
    plots {
      plotId
      cropType
      areaRai
      moistureLevel
    }
  }
}
```

### Aggregate Water Demand Dashboard
```graphql
query WaterDashboard {
  waterDemandDashboard(zoneId: "1A") {
    totalDemandM3
    awdAdjustedDemandM3
    potentialSavingsM3
    sectionsWithHighDemand {
      sectionId
      demandM3
      priority
    }
    recommendations {
      type
      message
      impactM3
    }
  }
}
```

### Subscribe to Real-time Updates
```graphql
subscription DemandUpdates {
  demandUpdates(sectionId: "1A-001") {
    sectionId
    grossDemandM3
    netDemandM3
    calculationTime
    trigger
  }
}
```

### AWD Activation
```graphql
mutation ActivateAWD {
  activateAwdMode(input: {
    plotId: "1A-001-P01",
    dryThreshold: 15.0,
    wetThreshold: 5.0,
    monitoringIntervalHours: 24
  }) {
    success
    message
    estimatedAnnualSavingsM3
  }
}
```

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose

### Development Setup

1. Clone the repository
```bash
cd services/bff-water-planning
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run migrations
```bash
psql -U postgres -d munbon_dev -f migrations/001_create_tables.sql
```

6. Start the service
```bash
python -m uvicorn src.main:app --reload --port 3002
```

7. Access GraphiQL interface
```
http://localhost:3002/graphql
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f bff-water-planning

# Stop services
docker-compose down
```

### Production Deployment

```bash
# Deploy to production
./scripts/deploy.sh --production

# Deploy to Kubernetes
kubectl apply -f k8s/
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_NAME` | Service identifier | bff-water-planning |
| `PORT` | HTTP port | 3002 |
| `ENVIRONMENT` | development/production | development |
| `LOG_LEVEL` | Logging level | INFO |
| `POSTGRES_URL` | Main database URL | - |
| `GIS_DATABASE_URL` | GIS database URL | - |
| `TIMESCALE_URL` | TimescaleDB URL | - |
| `REDIS_URL` | Redis connection URL | redis://localhost:6379/0 |
| `ROS_SERVICE_URL` | ROS service endpoint | http://localhost:3012 |
| `GIS_SERVICE_URL` | GIS service endpoint | http://localhost:3007 |
| `AWD_CONTROL_URL` | AWD control endpoint | http://localhost:3010 |
| `DB_POOL_MIN_SIZE` | Min DB connections | 10 |
| `DB_POOL_MAX_SIZE` | Max DB connections | 20 |
| `CORS_ORIGINS` | Allowed origins | http://localhost:3000 |

## Monitoring

### Health Check
```bash
curl http://localhost:3002/health
```

### Metrics
```bash
curl http://localhost:3002/metrics
```

### Performance Monitoring
- DataLoader statistics via logging
- Connection pool metrics
- GraphQL query complexity analysis
- Redis cache hit rates

## Testing

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/unit/test_dataloaders.py -v
```

## Development Guidelines

### Adding New Queries
1. Define schema in `schemas/`
2. Implement DataLoader if needed
3. Add query to `api/graphql_enhanced.py`
4. Add client-specific transformations
5. Write tests

### Adding AWD Features
1. Update AWD client in `clients/awd_client.py`
2. Add integration logic in `services/awd_integration.py`
3. Create mutations in `api/awd_mutations.py`
4. Update GraphQL schema
5. Test with mock AWD service

### Performance Best Practices
- Always use DataLoader for database queries
- Implement pagination for large datasets
- Cache frequently accessed data
- Use field-level resolvers sparingly
- Monitor query complexity

## Troubleshooting

### Common Issues

1. **Connection Pool Exhausted**
   - Increase `DB_POOL_MAX_SIZE`
   - Check for connection leaks
   - Review query complexity

2. **High Memory Usage**
   - Reduce DataLoader batch sizes
   - Implement pagination
   - Check for memory leaks in subscriptions

3. **Slow Queries**
   - Enable query logging
   - Add database indexes
   - Use DataLoader for N+1 prevention
   - Implement caching

### Debug Mode
```bash
LOG_LEVEL=DEBUG python -m uvicorn src.main:app --reload
```

## License

Copyright (c) 2024 Munbon. All rights reserved.