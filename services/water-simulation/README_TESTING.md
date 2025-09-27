# Water Simulation Service Testing Guide

## Overview

The water simulation service supports both **mock-based unit tests** and **real service integration tests**.

## Test Structure

```
tests/
├── unit/                     # Mock-based unit tests
├── integration/              # API integration tests (can use mocks)
└── real_services/           # Real external service tests
```

## Running Tests

### Unit Tests (with mocks)
```bash
# Run all unit tests
make test-unit

# Run specific test file
pytest tests/unit/test_simulation_engine.py -v
```

### Integration Tests (mock-based)
```bash
# Run API integration tests
make test-integration
```

### Real Service Tests
```bash
# Run with real external services
make test-real

# Run with verbose output (shows print statements)
make test-real-verbose

# Run specific real service test
USE_REAL_SERVICES=true pytest tests/real_services/test_real_simulation_engine.py -v
```

## Configuration

### 1. Create Test Environment File
```bash
cp .env.test.example .env.test
```

### 2. Configure Service Endpoints
Edit `.env.test`:
```env
# Enable real services
USE_REAL_SERVICES=true

# Service URLs (adjust to your environment)
TEST_ROS_URL=http://localhost:8004
TEST_FLOW_URL=http://localhost:8005
TEST_GATE_URL=http://localhost:8006
TEST_GIS_URL=http://localhost:8007

# Database
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/munbon_test

# Test data
TEST_ZONE_ID=1
TEST_SECTION_IDS=["Zone_1_Section_A", "Zone_1_Section_B"]
TEST_GATE_IDS=["GATE001", "GATE002", "GATE003"]
```

## Prerequisites for Real Service Tests

1. **All services must be running:**
   - ROS Service (port 8004)
   - Flow Monitoring Service (port 8005)
   - Gate Control Service (port 8006)
   - GIS Service (port 8007)

2. **Database must be accessible:**
   - PostgreSQL with PostGIS
   - Test database created
   - Migrations applied

3. **Test data must exist:**
   - Zones, sections, and gates referenced in config
   - Valid crop patterns and water demands

## Test Categories

### Real Service Client Tests
- `test_real_service_clients.py` - Tests individual service endpoints
- Verifies API contracts and response formats
- Tests data retrieval from each service

### Real Simulation Engine Tests
- `test_real_simulation_engine.py` - Tests core simulation with real data
- Verifies demand calculations
- Tests hydraulic simulations
- Runs short simulation scenarios

### Real Optimization Tests
- `test_real_optimization.py` - Tests optimization algorithms
- Uses real network topology
- Tests with actual gate constraints
- Verifies job order generation

## Troubleshooting

### Services Not Available
If tests fail with "Services not available":
1. Check all services are running
2. Verify URLs in `.env.test`
3. Check service health endpoints

### Missing Test Data
If tests fail with missing sections/gates:
1. Update test IDs in `.env.test`
2. Ensure test data exists in services
3. Run data seeding scripts if needed

### Database Connection Issues
1. Verify PostgreSQL is running
2. Check database credentials
3. Ensure test database exists
4. Apply migrations: `alembic upgrade head`

## Best Practices

1. **Start with unit tests** - Quick feedback, no dependencies
2. **Run real tests locally first** - Ensure services are ready
3. **Use specific test data** - Don't test with production data
4. **Clean up after tests** - Tests should be idempotent

## CI/CD Considerations

For CI pipelines, you can:
1. Use mocks by default (`USE_REAL_SERVICES=false`)
2. Run real service tests in staging environment only
3. Use Docker Compose to spin up test services

Example GitHub Actions:
```yaml
- name: Run Unit Tests
  run: make test-unit

- name: Run Real Service Tests
  if: github.ref == 'refs/heads/develop'
  run: |
    docker-compose -f docker-compose.test.yml up -d
    make test-real
    docker-compose -f docker-compose.test.yml down
```