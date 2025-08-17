# Starting Munbon Microservices

## Overview of Data Flow

```mermaid
graph TD
    A[Water Level Sensors] -->|MQTT/HTTP| B[Sensor Data Service]
    C[Moisture Sensors] -->|MQTT/HTTP| B
    D[Shape Files] -->|HTTP Upload| E[GIS Service]
    F[External Clients] -->|API Keys| G[Data API Gateway]
    
    B -->|TimescaleDB| H[(Time Series DB)]
    E -->|PostGIS| I[(Spatial DB)]
    
    G -->|Query| H
    G -->|Query| I
    
    J[AWS SQS] -->|Queue| B
    K[AWS SQS] -->|Queue| E
```

## 1. GIS Service (Shape File Processing)

### Start GIS Service:
```bash
cd services/gis

# Option A: Using convenience script
./start-gis-background.sh

# Option B: Manual start
# Terminal 1 - API Service
npm run dev  # Runs on port 3007

# Terminal 2 - Queue Processor
npm run queue:processor
```

### Check Status:
```bash
./status-gis.sh

# Or manually:
curl http://localhost:3007/health
```

### Upload Shape Files:
```bash
# To AWS Lambda endpoint (production)
curl -X POST https://6wls4auo90.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/gis/shapefile/upload \
  -H "Authorization: Bearer munbon-gis-shapefile" \
  -F "file=@yourfile.zip"

# To local endpoint (development)
curl -X POST http://localhost:3007/api/v1/gis/shapefiles/upload \
  -H "Authorization: Bearer your-dev-token" \
  -F "file=@yourfile.zip"
```

## 2. Sensor Data Service (Water Level & Moisture)

### Start Sensor Data Service:
```bash
cd services/sensor-data

# Option A: Development mode with test API keys
# Terminal 1 - API Service
export PORT=3003  # Port for TypeScript sensor data service
export TIMESCALE_HOST=localhost
export TIMESCALE_PORT=5433
export TIMESCALE_DB=sensor_data
export TIMESCALE_USER=postgres
export TIMESCALE_PASSWORD=postgres
export VALID_TOKENS="munbon-ridr-water-level:water-level,munbon-m2m-moisture:moisture"
npm run dev  # Runs on port 3001 with hot reload

# Terminal 2 - SQS Consumer (background worker - no port)
npm run consumer  # or ./start-consumer.sh
```

### Ingest Sensor Data:

#### Water Level Data:
```bash
# Direct ingestion (local)
curl -X POST http://localhost:3003/api/v1/telemetry/water-level \
  -H "Authorization: Bearer munbon-ridr-water-level" \
  -H "Content-Type: application/json" \
  -d '{
    "stationId": "WL001",
    "timestamp": "2025-07-04T10:00:00Z",
    "waterLevel": 5.23,
    "unit": "meters"
  }'

# AWS endpoint (queued)
curl -X POST https://YOUR-API-GATEWAY/api/v1/sensor-data/ingest \
  -H "Authorization: Bearer munbon-ridr-water-level" \
  -H "Content-Type: application/json" \
  -d '{"type": "water-level", "data": {...}}'
```

#### Moisture Data:
```bash
# Direct ingestion (local)
curl -X POST http://localhost:3003/api/v1/telemetry/moisture \
  -H "Authorization: Bearer munbon-m2m-moisture" \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "MOISTURE001",
    "timestamp": "2025-07-04T10:00:00Z",
    "moisture": 65.5,
    "temperature": 28.3,
    "humidity": 72.1
  }'
```

## 3. External Data API (For Clients)

### Local Data API Access:
```bash
# Get water level data (from local sensor service)
curl -X GET "http://localhost:3003/api/v1/external/water-level?from=2025-07-01&to=2025-07-04" \
  -H "X-API-Key: rid-ms-dev-1234567890abcdef"

# Get moisture data (from local sensor service)
curl -X GET "http://localhost:3003/api/v1/external/moisture?deviceId=MOISTURE001" \
  -H "X-API-Key: test-key-fedcba0987654321"

# Get shape file data (from GIS service)
curl -X GET "http://localhost:3007/api/v1/gis/parcels?zone=1" \
  -H "Authorization: Bearer your-api-key"
```

### External AWS API Access (Production):
```bash
# Water level data via AWS Lambda (Data Exposure API)
curl -X GET "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest" \
  -H "X-API-Key: rid-ms-prod-key1"

# Moisture data via AWS Lambda
curl -X GET "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/timeseries?date=30/06/2568" \
  -H "X-API-Key: rid-ms-prod-key1"

# Data Ingestion via AWS Lambda
curl -X POST "https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry" \
  -H "Content-Type: application/json" \
  -d '{"stationId":"WL001","waterLevel":5.23}'
```

## 4. Docker Compose (All Services)

### Start All Services:
```bash
# From project root
docker-compose up -d

# Or specific services
docker-compose up -d postgres timescaledb redis
```

### Service Ports:
- **Unified API (PM2)**: http://localhost:3000 (sensor data via unified-api.js)
- **Auth Service**: http://localhost:3001
- **Sensor Data API**: http://localhost:3003 (TypeScript microservice)
- **Sensor Data Consumer**: Background worker (no port)
- **GIS API**: http://localhost:3007
- **GIS Queue Processor**: Background worker (no port)
- **PostgreSQL (PostGIS)**: localhost:5434
- **TimescaleDB**: localhost:5433
- **Redis**: localhost:6379

## 5. Monitoring & Logs

### View Logs:
```bash
# GIS Service
tail -f services/gis/logs/gis-api.log
tail -f services/gis/logs/gis-queue-processor.log

# Sensor Data Service
tail -f services/sensor-data/logs/combined.log

# Docker logs
docker-compose logs -f gis-service
docker-compose logs -f sensor-service
```

### Check Queue Status:
```bash
# GIS Queue
cd services/gis/deployments/aws-lambda
node check-queue-status.js

# Sensor Data Queue
cd services/sensor-data
node check-sqs-messages.sh
```

## 6. Production Deployment

### AWS Lambda Functions:
```bash
# Deploy GIS upload endpoint
cd services/gis/deployments/aws-lambda
serverless deploy

# Deploy sensor data ingestion
cd services/sensor-data/deployments/aws-lambda
./deploy-all.sh
```

### Kubernetes:
```bash
# Apply configurations
kubectl apply -f k8s/namespaces/
kubectl apply -f k8s/configmaps/
kubectl apply -f k8s/services/

# Check status
kubectl get pods -n munbon
kubectl get services -n munbon
```

## API Authentication Summary

| Service | Endpoint Type | Authentication Method | Example Token/Key |
|---------|--------------|----------------------|-------------------|
| GIS Upload | Shape file upload | Bearer Token | `munbon-gis-shapefile` |
| Sensor Ingestion | Water level | Bearer Token | `munbon-ridr-water-level` |
| Sensor Ingestion | Moisture | Bearer Token | `munbon-m2m-moisture` |
| External API | Data retrieval | X-API-Key | `rid-ms-dev-1234567890abcdef` |

## Quick Test Commands

```bash
# Test all services
./test-all-microservices.sh

# Test specific endpoints
./test-shape-upload.sh
./test-sensor-ingestion.sh
./test-external-api.sh
```

## Important Notes

1. **Port Configuration**:
   - **API Gateway/Unified API**: Port **3000** (PM2)
   - **Auth Service**: Port **3001**
   - **Sensor Data API**: Port **3001** (standalone) or **3000** (unified API via PM2)
   - **GIS Service**: Port **3007**

2. **Background Workers** (no ports):
   - **Sensor Data Consumer**: Processes messages from AWS SQS queue
   - **GIS Queue Processor**: Processes shape file uploads from SQS

3. **API Access**:
   - **Local Services**: 
     - Unified API (PM2): http://localhost:3000
     - Auth: http://localhost:3001
     - Sensor Data: http://localhost:3001 (standalone)
     - GIS: http://localhost:3007
   - **AWS Lambda Endpoints**:
     - Data Ingestion: https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1
     - Data Exposure: https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1
   - **Temporary Tunnels** (when configured):
     - Cloudflare: https://asked-arbitrary-shakespeare-ken.trycloudflare.com