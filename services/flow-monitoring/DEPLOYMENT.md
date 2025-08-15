# Flow Monitoring Service - EC2 Deployment Guide

## Overview
This guide covers the deployment of the Flow Monitoring Service to the EC2 instance at `43.209.22.250`.

## Prerequisites
1. Docker Hub account with access to push images
2. SSH key for EC2 access (`~/dev/th-lab01.pem`)
3. Docker installed locally
4. Access to EC2 instance

## Port Configuration
- **Service Port**: 3011
- **Metrics Port**: 9090 (internal)

## Database Configuration
The service connects to consolidated PostgreSQL on EC2:
- **Main Database**: `postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev`
- **TimescaleDB**: `postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/sensor_data`

## Quick Deployment

### 1. Automated Deployment
```bash
cd services/flow-monitoring
./deploy-to-ec2.sh
```

### 2. Manual Deployment Steps

#### Build and Push Docker Image
```bash
# Build image
docker build -t subhaj888/munbon-flow-monitoring:latest .

# Push to Docker Hub
docker push subhaj888/munbon-flow-monitoring:latest
```

#### Update EC2 Configuration
```bash
# Copy environment file
scp -i ~/dev/th-lab01.pem .env.ec2 ubuntu@43.209.22.250:/home/ubuntu/munbon2-backend/services/flow-monitoring/.env

# Copy network configuration files
scp -i ~/dev/th-lab01.pem src/munbon_network_final.json ubuntu@43.209.22.250:/home/ubuntu/munbon2-backend/services/flow-monitoring/src/
scp -i ~/dev/th-lab01.pem canal_geometry_template.json ubuntu@43.209.22.250:/home/ubuntu/munbon2-backend/services/flow-monitoring/
```

#### Deploy on EC2
```bash
# SSH to EC2
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250

# Navigate to project
cd /home/ubuntu/munbon2-backend

# Update docker-compose.ec2.yml with the configuration from docker-compose.ec2.snippet.yml

# Pull and restart service
docker-compose -f docker-compose.ec2.yml pull flow-monitoring
docker-compose -f docker-compose.ec2.yml up -d flow-monitoring
```

## Verification

### Check Service Status
```bash
# Check if container is running
docker ps | grep flow-monitoring

# Check logs
docker logs munbon-flow-monitoring

# Check health endpoint
curl http://localhost:3011/health
```

### Test API Endpoints
```bash
# Get current water levels
curl http://43.209.22.250:3011/api/v1/level/current?location_ids=<uuid>

# Get flow statistics
curl http://43.209.22.250:3011/api/v1/flow/statistics/<location_id>

# Get gate states
curl http://43.209.22.250:3011/api/v1/gates
```

## Database Tables Created
The service will create the following tables on first run:

### In `sensor_data` database:
- `flow_aggregates` (TimescaleDB hypertable)
- `water_balance` (TimescaleDB hypertable)  
- `flow_anomalies`

### In `munbon_dev` database:
- `flow_sensors`
- `monitoring_locations`
- `hydraulic_models`
- `calibration_history`

## Troubleshooting

### Service Won't Start
```bash
# Check logs
docker logs munbon-flow-monitoring

# Check database connectivity
docker exec munbon-flow-monitoring python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev'))"
```

### Port Already in Use
```bash
# Check what's using port 3011
sudo lsof -i :3011

# Kill process if needed
sudo kill -9 <PID>
```

### Database Connection Issues
1. Verify PostgreSQL is accepting connections from Docker network
2. Check credentials in .env file
3. Ensure databases exist: `munbon_dev` and `sensor_data`

### Missing Network Files
The service requires:
- `src/munbon_network_final.json` - Network topology
- `canal_geometry_template.json` - Canal geometry data

These must be present in the container at:
- `/app/src/munbon_network_final.json`
- `/app/canal_geometry_template.json`

## Monitoring

### Prometheus Metrics
Available at `http://43.209.22.250:9090/metrics`:
- `flow_monitoring_requests_total`
- `flow_monitoring_request_duration_seconds`
- `flow_monitoring_db_operations_total`
- `flow_monitoring_gate_opening_percentage`

### Health Check
```bash
curl http://43.209.22.250:3011/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "flow-monitoring",
  "version": "1.0.0",
  "databases": {
    "postgres": true,
    "timescale": true,
    "redis": true,
    "influxdb": true
  }
}
```

## Rolling Back
```bash
# On EC2
cd /home/ubuntu/munbon2-backend

# Stop current version
docker-compose -f docker-compose.ec2.yml stop flow-monitoring

# Pull previous version (if tagged)
docker pull subhaj888/munbon-flow-monitoring:previous-tag

# Update docker-compose.ec2.yml to use previous tag
# Then restart
docker-compose -f docker-compose.ec2.yml up -d flow-monitoring
```

## Security Notes
1. Database credentials are stored in environment variables
2. Service runs as non-root user inside container
3. Only required ports are exposed
4. Health check endpoint doesn't expose sensitive data