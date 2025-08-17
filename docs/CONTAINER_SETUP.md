# Munbon Backend Container Setup

## Current Status

### ✅ Containerized Services Available
- PostgreSQL with PostGIS (Port 5432) - Spatial data
- TimescaleDB (Port 5433) - Time-series sensor data
- MongoDB (Port 27017) - Document storage
- Redis (Port 6379) - Caching
- InfluxDB (Port 8086) - Metrics
- Kafka + Zookeeper (Ports 9092, 2181) - Message broker
- Kong API Gateway (Ports 8000, 8001) - API management
- Sensor Data Service (Port 3000) - Sensor data API

### 🚧 Services Not Yet Implemented
- Auth Service (Port 3001)
- GIS Service (Port 3007)
- ROS Service (Port 3047)
- Water Level Monitoring (Port 3004)
- Moisture Monitoring (Port 3005)
- Weather Monitoring (Port 3006)

## Quick Start

### 1. Start All Services with Docker Compose
```bash
cd /Users/subhajlimanond/dev/munbon2-backend

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### 2. Alternative: Use Current PM2 Setup (Non-containerized)
```bash
# Currently running setup
pm2 status

# Shows:
# - sensor-api (Port 3000)
# - quick-tunnel (Cloudflare tunnel)
# - tunnel-monitor (Auto-updates Parameter Store)
```

## Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     External Access                          │
│  Customer API → AWS Lambda → Parameter Store → Cloudflare   │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    Kong API Gateway                          │
│                    (Ports 8000, 8001)                       │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                     Microservices                            │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Sensor Data │  │    Auth     │  │     GIS     │   ...   │
│  │  Port 3000  │  │  Port 3001  │  │  Port 3007  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
┌─────────▼─────────────────▼─────────────────▼───────────────┐
│                      Data Layer                              │
├──────────────────────────────────────────────────────────────┤
│ PostgreSQL │ MongoDB │ Redis │ InfluxDB │ Kafka            │
│  (5432)    │ (27017) │(6379) │  (8086)  │ (9092)           │
└──────────────────────────────────────────────────────────────┘
```

## Development Workflow

### Option 1: Full Container Setup (Recommended for Production-like)
```bash
# Build and start all services
docker-compose up --build

# Scale services
docker-compose up --scale sensor-data=3

# View specific service logs
docker-compose logs -f sensor-data
```

### Option 2: Hybrid Setup (Current - Good for Development)
- **Local Services**: Sensor API via PM2
- **Databases**: Can use Docker or Homebrew
- **External Access**: Cloudflare tunnel + AWS Lambda

### Option 3: Kubernetes (Production)
```bash
# Apply Kubernetes manifests (when created)
kubectl apply -f k8s/

# Check deployments
kubectl get deployments -n munbon
```

## Database Initialization

### PostgreSQL with PostGIS (Port 5432)
```sql
-- Connect to PostgreSQL
psql -h localhost -p 5432 -U postgres -d munbon_dev

-- Create PostGIS extension for spatial data
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create tables for GIS data, users, etc.
```

### TimescaleDB (Port 5433)
```sql
-- Connect to TimescaleDB (separate instance)
psql -h localhost -p 5433 -U postgres -d munbon_timescale

-- TimescaleDB extension is pre-installed in this image
-- Create hypertables for time-series data
CREATE TABLE water_levels (
    time TIMESTAMPTZ NOT NULL,
    sensor_id TEXT NOT NULL,
    level DOUBLE PRECISION,
    PRIMARY KEY(time, sensor_id)
);

SELECT create_hypertable('water_levels', 'time');

-- Create other sensor data tables
CREATE TABLE moisture_readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id TEXT NOT NULL,
    moisture DOUBLE PRECISION,
    temperature DOUBLE PRECISION,
    PRIMARY KEY(time, sensor_id)
);

SELECT create_hypertable('moisture_readings', 'time');
```

### MongoDB
```javascript
// Connect to MongoDB
mongosh mongodb://admin:admin123@localhost:27017/munbon?authSource=admin

// Create collections
db.createCollection('farmers')
db.createCollection('irrigation_zones')
db.createCollection('crop_data')
```

## Service Discovery

When running in containers, services communicate using container names:
- `postgres` instead of `localhost:5432`
- `redis` instead of `localhost:6379`
- `kafka:9093` instead of `localhost:9092`

## Environment Variables

### For Containerized Services
```env
# Database connections
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=munbon_dev
TIMESCALE_HOST=timescaledb
TIMESCALE_PORT=5432  # Internal container port
TIMESCALE_DB=munbon_timescale
MONGO_URL=mongodb://admin:admin@mongodb:27017/munbon_dev?authSource=admin
REDIS_URL=redis://redis:6379

# Kafka
KAFKA_BROKERS=kafka:29092  # Internal listener

# Service Discovery
AUTH_SERVICE_URL=http://auth-service:8001
GIS_SERVICE_URL=http://gis-service:3007
```

### For Local Development (Non-containerized)
```env
# Database connections
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=munbon_dev
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433  # External mapped port
TIMESCALE_DB=munbon_timescale
MONGO_URL=mongodb://admin:admin@localhost:27017/munbon_dev?authSource=admin
REDIS_URL=redis://localhost:6379

# Kafka
KAFKA_BROKERS=localhost:9092

# Service Discovery
AUTH_SERVICE_URL=http://localhost:3001
GIS_SERVICE_URL=http://localhost:3007
```

## Health Checks

All services include health checks:
```bash
# Check all service health
docker-compose ps

# Manual health check
curl http://localhost:3000/health
curl http://localhost:8001/status  # Kong Admin API
```

## Troubleshooting

### Port Conflicts
```bash
# Check what's using a port
lsof -i :3000

# Kill process using port
kill -9 $(lsof -t -i:3000)
```

### Container Issues
```bash
# Remove all containers and volumes
docker-compose down -v

# Rebuild without cache
docker-compose build --no-cache

# View container resource usage
docker stats
```

### Database Connection Issues
```bash
# Test PostgreSQL connection
docker exec -it munbon-postgres psql -U postgres -d munbon_dev -c "SELECT 1"

# Test TimescaleDB connection
docker exec -it munbon-timescaledb psql -U postgres -d munbon_timescale -c "SELECT 1"

# Test MongoDB connection
docker exec -it munbon-mongodb mongosh --eval "db.adminCommand('ping')"

# Test Redis connection
docker exec -it munbon-redis redis-cli ping
```

## Next Steps

1. **Implement remaining microservices** (Auth, GIS, ROS, etc.)
2. **Set up Kong API Gateway routes**
3. **Create Kubernetes manifests** for production deployment
4. **Add service mesh** (Istio/Linkerd) for advanced networking
5. **Implement distributed tracing** (Jaeger/Zipkin)