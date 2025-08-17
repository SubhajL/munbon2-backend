# Comprehensive Testing Guide for Munbon Backend with EC2 Database

## Overview

This guide covers testing all 17 implemented backend services using the consolidated PostgreSQL database on EC2. The database architecture uses a single PostgreSQL instance (port 5432) with TimescaleDB extension for time-series data.

## EC2 Database Architecture

### Consolidated PostgreSQL Instance
- **Host**: 43.209.22.250
- **Port**: 5432 (both PostgreSQL and TimescaleDB)
- **Databases**:
  - `munbon_dev` - Main database with schemas:
    - `auth` - Authentication service
    - `gis` - GIS service
    - `ros` - ROS service
    - `awd` - AWD control service
  - `sensor_data` - TimescaleDB for time-series data
- **Other Services**:
  - Redis: localhost:6379 (Docker container)
  - MongoDB: 43.209.22.250:27017 (if needed)

## Service Architecture

### Tier 1: Core Services
1. **Auth Service** (3001) - User authentication, JWT tokens
2. **GIS Service** (3007) - Spatial data, PostGIS operations
3. **Sensor Data Service** (3003) - Time-series ingestion

### Tier 2: Data Services  
4. **ROS Service** (3047) - Crop management, water calculations
5. **Weather Monitoring** (3006) - Weather data processing
6. **Water Level Monitoring** (3008) - Water level tracking
7. **Moisture Monitoring** (3005) - Soil moisture analysis

### Tier 3: Control Services
8. **AWD Control** (3013) - Irrigation control decisions
9. **Flow Monitoring** (3014) - Hydraulic calculations, gate control
10. **RID-MS** (3011) - RID management system

### Tier 4: Integration Services
11. **ROS-GIS Integration** (3022) - GraphQL API
12. **Scheduler** (3021) - Task scheduling
13. **Gravity Optimizer** (3016) - Optimization algorithms
14. **Water Accounting** (3019) - Water usage tracking
15. **Sensor Location Mapping** (3018) - Sensor geolocation
16. **Sensor Network Management** (3020) - Network monitoring
17. **Unified API** (3000) - API Gateway

## Test Scripts

### 1. Comprehensive Test Runner
```bash
./scripts/test-all-services-ec2.sh
```
Tests all services with:
- Database connectivity checks
- Service health verification
- Integration tests
- End-to-end scenarios
- Load testing
- Performance metrics

### 2. Sensor Data Service Test
```bash
./scripts/test-sensor-data-ec2.sh
```
Specific tests for:
- TimescaleDB hypertable verification
- Data ingestion
- Query performance
- Aggregation functions

### 3. Integration Test Suite
```bash
./scripts/test-integration-ec2.sh
```
Multi-service workflows:
- Sensor → Weather → ROS flow
- GIS → ROS-GIS → AWD control
- AWD → Flow Monitoring → SCADA
- Real-time Redis pub/sub
- End-to-end irrigation cycle

### 4. Load Testing with K6
```bash
k6 run scripts/load-test-ec2.js
```
Performance testing:
- 100 concurrent users
- Mixed workload simulation
- EC2 latency considerations
- Service health monitoring

## Running Tests

### Prerequisites
1. Ensure EC2 database is accessible:
```bash
# Test connection
PGPASSWORD="P@ssw0rd123!" psql -h 43.209.22.250 -p 5432 -U postgres -l
```

2. Start all services:
```bash
# Using PM2
pm2 start ecosystem.config.js --env ec2

# Or using Docker Compose
docker-compose -f docker-compose.ec2-consolidated.yml up -d
```

3. Verify services are running:
```bash
pm2 status
# or
docker-compose ps
```

### Test Execution Order

1. **Phase 1: Infrastructure**
   ```bash
   # Test database connections
   ./scripts/test-all-services-ec2.sh
   ```

2. **Phase 2: Individual Services**
   ```bash
   # Test specific services
   ./scripts/test-sensor-data-ec2.sh
   ```

3. **Phase 3: Integration**
   ```bash
   # Test service interactions
   ./scripts/test-integration-ec2.sh
   ```

4. **Phase 4: Load Testing**
   ```bash
   # Install k6 if needed
   brew install k6
   
   # Run load tests
   k6 run scripts/load-test-ec2.js
   ```

## Expected Results

### Database Performance
- Connection time: <50ms
- Query response: <100ms for simple queries
- Write performance: >100 inserts/second

### Service Health
- All services responding on health endpoints
- Response time: <100ms for health checks
- Memory usage: <512MB per service

### Integration Tests
- Cross-service communication working
- Data consistency maintained
- Real-time updates via Redis

### Load Test Targets
- 95% requests under 1 second
- Error rate under 10%
- Support 100+ concurrent users

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check EC2 connectivity
   ping 43.209.22.250
   
   # Test PostgreSQL port
   nc -zv 43.209.22.250 5432
   ```

2. **Service Not Responding**
   ```bash
   # Check service logs
   pm2 logs [service-name]
   
   # Restart service
   pm2 restart [service-name]
   ```

3. **TimescaleDB Issues**
   ```sql
   -- Check extension
   SELECT * FROM pg_extension WHERE extname = 'timescaledb';
   
   -- Check hypertables
   SELECT * FROM timescaledb_information.hypertables;
   ```

4. **Performance Issues**
   - Monitor EC2 database load
   - Check connection pool settings
   - Review service memory usage

## Test Reports

Test results are saved in:
- `test-results-[timestamp].log` - Detailed test output
- `test-report-[timestamp].json` - Summary in JSON format
- K6 HTML reports (if configured)

## Best Practices

1. **Always test database connectivity first**
2. **Run tests in order: infrastructure → services → integration → load**
3. **Monitor EC2 resource usage during tests**
4. **Clean up test data after completion**
5. **Document any failures with logs**

## CI/CD Integration

For automated testing:
```yaml
# .github/workflows/test-ec2.yml
name: EC2 Integration Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        env:
          POSTGRES_PASSWORD: ${{ secrets.EC2_DB_PASSWORD }}
        run: |
          ./scripts/test-all-services-ec2.sh
```

## Security Notes

- Never commit EC2 credentials
- Use environment variables for passwords
- Restrict EC2 security group to known IPs
- Use SSH tunnels for remote testing