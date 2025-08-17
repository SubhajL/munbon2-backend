# EC2 Deployment Guide for ROS/GIS Integration Service

## Overview
This guide explains how to deploy the ROS/GIS Integration Service to the EC2 instance with the database at `43.209.22.250`.

## Prerequisites

1. **PostgreSQL Client** (for running migrations)
   ```bash
   # macOS
   brew install postgresql
   
   # Ubuntu/Debian
   sudo apt-get install postgresql-client
   ```

2. **Python 3.8+** with pip
3. **Access to EC2 instance** (SSH or deployment pipeline)

## Database Deployment

### Step 1: Deploy Database Schema

Run the deployment script from your local machine:

```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/ros-gis-integration
./scripts/deploy-database-ec2.sh
```

This script will:
- Connect to the EC2 PostgreSQL instance
- Create the `ros_gis` schema
- Install PostGIS extension if needed
- Create all required tables
- Set up indexes and views

### Step 2: Verify Database Setup

Test the connection:

```bash
python3 scripts/test-ec2-connection.py
```

Expected output:
```
✓ Connected to PostgreSQL: PostgreSQL 14.x ...
✓ PostGIS version: 3.x.x
✓ Found 13 tables in ros_gis schema:
  - accumulated_demands
  - aquacrop_results
  - daily_demands
  - demands
  - gate_demands
  - gate_mappings
  - irrigation_channels
  - plots
  - section_performance
  - sections
  - weather_adjustments
  - v_channel_utilization
  - v_section_channel_demands
```

## Service Deployment Options

### Option 1: Direct Deployment on EC2

1. **SSH to EC2 instance:**
   ```bash
   ssh -i your-key.pem ubuntu@43.209.22.250
   ```

2. **Clone/Update the repository:**
   ```bash
   cd /home/ubuntu
   git clone https://github.com/your-repo/munbon2-backend.git
   # or git pull if already cloned
   ```

3. **Install dependencies:**
   ```bash
   cd munbon2-backend/services/ros-gis-integration
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Set environment variables:**
   ```bash
   # Copy the generated env file
   cp .env.ec2-deploy .env
   
   # Or export directly
   export POSTGRES_URL="postgresql://postgres:P@ssw0rd123!@localhost:5432/munbon_dev"
   export REDIS_URL="redis://localhost:6379/2"
   export ENVIRONMENT="production"
   ```

5. **Run the service:**
   ```bash
   # With PM2 (recommended)
   pm2 start src/main.py --name ros-gis-integration --interpreter python3
   
   # Or directly
   python3 src/main.py
   ```

### Option 2: Docker Deployment

1. **Build Docker image locally:**
   ```bash
   cd services/ros-gis-integration
   docker build -t ros-gis-integration:latest .
   ```

2. **Tag and push to registry:**
   ```bash
   docker tag ros-gis-integration:latest your-registry/ros-gis-integration:latest
   docker push your-registry/ros-gis-integration:latest
   ```

3. **On EC2, run the container:**
   ```bash
   docker run -d \
     --name ros-gis-integration \
     --network munbon-network \
     -p 3022:3022 \
     -e POSTGRES_URL="postgresql://postgres:P@ssw0rd123!@host.docker.internal:5432/munbon_dev" \
     -e REDIS_URL="redis://redis:6379/2" \
     -e ENVIRONMENT="production" \
     your-registry/ros-gis-integration:latest
   ```

### Option 3: Docker Compose (Recommended)

1. **Create docker-compose.yml on EC2:**
   ```yaml
   version: '3.8'
   
   services:
     ros-gis-integration:
       image: your-registry/ros-gis-integration:latest
       container_name: ros-gis-integration
       ports:
         - "3022:3022"
       environment:
         - POSTGRES_URL=postgresql://postgres:P@ssw0rd123!@host.docker.internal:5432/munbon_dev
         - REDIS_URL=redis://redis:6379/2
         - ENVIRONMENT=production
         - USE_MOCK_SERVER=false
         - ROS_SERVICE_URL=http://ros-service:3047
         - GIS_SERVICE_URL=http://gis-service:3007
         - FLOW_MONITORING_URL=http://flow-monitoring:3011
         - SCHEDULER_SERVICE_URL=http://scheduler:3021
       networks:
         - munbon-network
       restart: unless-stopped
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:3022/health"]
         interval: 30s
         timeout: 10s
         retries: 3
   
   networks:
     munbon-network:
       external: true
   ```

2. **Deploy:**
   ```bash
   docker-compose up -d
   ```

## Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| POSTGRES_URL | PostgreSQL connection string | postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev |
| REDIS_URL | Redis connection string | redis://43.209.22.250:6379/2 |
| ENVIRONMENT | Environment name | production |
| USE_MOCK_SERVER | Use mock data instead of real services | false |
| ROS_SERVICE_URL | ROS service endpoint | http://localhost:3047 |
| GIS_SERVICE_URL | GIS service endpoint | http://localhost:3007 |
| FLOW_MONITORING_URL | Flow monitoring endpoint | http://localhost:3011 |
| SCHEDULER_SERVICE_URL | Scheduler service endpoint | http://localhost:3021 |

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| LOG_LEVEL | Logging level | INFO |
| DEMAND_COMBINATION_STRATEGY | How to combine ROS/AquaCrop | aquacrop_priority |
| CACHE_TTL_SECONDS | Default cache TTL | 300 |
| FLOW_MONITORING_NETWORK_FILE | Path to network JSON | None |

## Post-Deployment

### 1. Health Check

```bash
curl http://43.209.22.250:3022/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "ros-gis-integration",
  "version": "1.0.0",
  "databases": {
    "postgres": true,
    "redis": true
  },
  "external_services": {
    "flow_monitoring": true,
    "scheduler": true,
    "ros": true,
    "gis": true
  }
}
```

### 2. Check Service Status

```bash
curl http://43.209.22.250:3022/api/v1/status
```

### 3. GraphQL Interface

Access GraphiQL at: `http://43.209.22.250:3022/graphql`

### 4. Admin Endpoints

- Cache stats: `GET /api/v1/admin/cache/stats`
- Query stats: `GET /api/v1/admin/query/stats`
- Detailed health: `GET /api/v1/admin/health/detailed`

## Daily Operations

### Start Daily Demand Calculation

```bash
curl -X POST http://43.209.22.250:3022/api/v1/daily-demands/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2024-01-20",
    "zones": [2, 3, 5, 6]
  }'
```

### Trigger Control Interval Accumulation

```bash
curl -X POST http://43.209.22.250:3022/api/v1/demands/accumulate \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-15",
    "interval": "weekly",
    "zones": [2, 3, 5, 6]
  }'
```

## Monitoring

### With PM2
```bash
pm2 status
pm2 logs ros-gis-integration
pm2 monit
```

### With Docker
```bash
docker logs -f ros-gis-integration
docker stats ros-gis-integration
```

### Prometheus Metrics
Available at: `http://43.209.22.250:3022/metrics`

## Troubleshooting

### Database Connection Issues
1. Check PostgreSQL is running on EC2
2. Verify security group allows port 5432
3. Test with psql: `psql -h 43.209.22.250 -U postgres -d munbon_dev`

### Service Won't Start
1. Check logs for errors
2. Verify all environment variables are set
3. Ensure PostGIS extension is installed
4. Check if ports are already in use

### Cache Issues
1. Clear cache namespace: `POST /api/v1/admin/cache/clear/{namespace}`
2. Check Redis connection
3. Monitor cache hit rates

### Performance Issues
1. Check query statistics: `GET /api/v1/admin/query/stats`
2. Ensure database indexes exist
3. Monitor cache effectiveness
4. Check network latency to EC2

## Backup and Recovery

### Database Backup
```bash
# On EC2 or remotely
pg_dump -h 43.209.22.250 -U postgres -d munbon_dev -n ros_gis -f ros_gis_backup.sql
```

### Database Restore
```bash
psql -h 43.209.22.250 -U postgres -d munbon_dev -f ros_gis_backup.sql
```

## Security Notes

1. **Change default passwords** in production
2. **Use SSL/TLS** for database connections
3. **Implement API authentication** for production
4. **Restrict network access** via security groups
5. **Enable audit logging** for compliance

## Support

For issues or questions:
1. Check logs first
2. Review this guide
3. Check SERVICE_RELATIONSHIPS.md for integration details
4. Contact the development team