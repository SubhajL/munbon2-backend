# Data Ingestion Service Deployment Status

## Date: August 11, 2025

### Current Architecture

#### Data Entry Points
1. **Moisture Sensors**
   - Entry: HTTP endpoint on EC2 (http://43.209.22.250:8080) ✅
   - Service: `moisture-http` running on EC2 PM2

2. **Water Level Sensors**
   - Entry: AWS API Gateway → Lambda → SQS ✅
   - Lambda: `munbon-sensor-ingestion-dev-telemetry`
   - SQS Queue: AWS ap-southeast-1

#### Data Processing
- **SQS Consumer**: Running LOCALLY ⚠️
  - Service: `sensor-consumer` on local PM2
  - Status: Online for 22 hours
  - Dual-write enabled to both databases

#### Data Storage
- **Local TimescaleDB** (port 5433) - Still receiving data ✅
- **EC2 PostgreSQL/TimescaleDB** (43.209.22.250:5432) - Receiving data ✅

### Service Status

#### EC2 Services (✅ DEPLOYED)
- `moisture-http` - HTTP endpoint for moisture sensors
- PostgreSQL with TimescaleDB extension
- Hypertables configured for sensor data

#### Local Services (⚠️ STILL RUNNING)
1. **sensor-consumer** - SQS message processor
2. **sensor-data-service** - API service (port 3001)
3. **munbon-moisture-tunnel** - Legacy Cloudflare tunnel
4. **Docker containers**:
   - munbon-timescaledb
   - munbon-postgres

### Migration Status

✅ **COMPLETED**:
- HTTP endpoint moved to EC2
- EC2 database configured with hypertables
- Dual-write functioning properly
- Both moisture and water level data flowing to EC2

⚠️ **NOT MIGRATED**:
- SQS Consumer still running locally
- Local databases still active and receiving data
- Local API service still running

### Next Steps to Complete Migration

1. **Deploy SQS Consumer to EC2**
   - Need to containerize or deploy consumer service
   - Configure EC2 environment variables
   - Ensure AWS credentials for SQS access

2. **Disable Dual-Write**
   - Once consumer runs on EC2
   - Update to write only to EC2 database

3. **Shutdown Local Services**
   - Stop sensor-consumer
   - Stop Docker containers
   - Keep local data as backup

### Current Data Flow
```
Sensors → EC2/AWS → SQS → LOCAL Consumer → Dual-Write → Both DBs
                                                      ↓
                                              Need to move to EC2
```

### Recommendation
The ingestion service is **partially ported** to EC2. The entry points (HTTP, Lambda) are on AWS/EC2, but the critical SQS consumer that processes and stores data is still running locally. This creates a dependency on the local environment.