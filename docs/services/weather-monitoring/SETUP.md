# Weather Monitoring Service - Setup Guide

## Prerequisites

1. **Node.js** (v18+ recommended)
2. **Docker** and **Docker Compose**
3. **PostgreSQL** (v14+) with PostGIS extension
4. **TimescaleDB** (v2.11+)
5. **Redis** (v7.0+)
6. **MQTT Broker** (Mosquitto or similar)

## Database Setup

### 1. PostgreSQL Database (for weather integration data)

```sql
-- Create database
CREATE DATABASE weather_integration;

-- Connect to database
\c weather_integration;

-- Create weather stations table
CREATE TABLE weather_stations (
  station_id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  type VARCHAR(50) NOT NULL,
  location_lat DECIMAL(10, 8) NOT NULL,
  location_lng DECIMAL(11, 8) NOT NULL,
  altitude DECIMAL(10, 2),
  source VARCHAR(50) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create weather readings table
CREATE TABLE weather_readings (
  id BIGSERIAL PRIMARY KEY,
  station_id VARCHAR(50) NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  location_lat DECIMAL(10, 8),
  location_lng DECIMAL(11, 8),
  temperature DECIMAL(5, 2),
  humidity DECIMAL(5, 2),
  pressure DECIMAL(6, 2),
  wind_speed DECIMAL(5, 2),
  wind_direction DECIMAL(5, 2),
  rainfall DECIMAL(6, 2),
  solar_radiation DECIMAL(6, 2),
  uv_index DECIMAL(3, 1),
  visibility DECIMAL(5, 2),
  cloud_cover DECIMAL(5, 2),
  dew_point DECIMAL(5, 2),
  feels_like DECIMAL(5, 2),
  source VARCHAR(50),
  quality_score DECIMAL(3, 2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create weather forecasts table
CREATE TABLE weather_forecasts (
  id BIGSERIAL PRIMARY KEY,
  station_id VARCHAR(50),
  location_lat DECIMAL(10, 8) NOT NULL,
  location_lng DECIMAL(11, 8) NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  forecast_time TIMESTAMP NOT NULL,
  temp_min DECIMAL(5, 2),
  temp_max DECIMAL(5, 2),
  temp_avg DECIMAL(5, 2),
  humidity_min DECIMAL(5, 2),
  humidity_max DECIMAL(5, 2),
  humidity_avg DECIMAL(5, 2),
  rainfall_amount DECIMAL(6, 2),
  rainfall_probability DECIMAL(3, 2),
  wind_speed DECIMAL(5, 2),
  wind_direction DECIMAL(5, 2),
  cloud_cover DECIMAL(5, 2),
  uv_index DECIMAL(3, 1),
  conditions VARCHAR(50),
  confidence DECIMAL(3, 2),
  source VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_weather_readings_timestamp ON weather_readings(timestamp DESC);
CREATE INDEX idx_weather_readings_station ON weather_readings(station_id, timestamp DESC);
CREATE INDEX idx_weather_readings_location ON weather_readings(location_lat, location_lng);
CREATE INDEX idx_weather_forecasts_time ON weather_forecasts(forecast_time);
CREATE INDEX idx_weather_forecasts_location ON weather_forecasts(location_lat, location_lng);
```

### 2. TimescaleDB Setup (for AOS time-series data)

```sql
-- Create database
CREATE DATABASE aos_weather;

-- Connect to database
\c aos_weather;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create same tables as above, then convert to hypertables
SELECT create_hypertable('weather_readings', 'timestamp');

-- Set data retention policy (optional - keeps 1 year of data)
SELECT add_retention_policy('weather_readings', INTERVAL '1 year');

-- Create continuous aggregates for better performance
CREATE MATERIALIZED VIEW weather_hourly
WITH (timescaledb.continuous) AS
SELECT 
  time_bucket('1 hour', timestamp) AS bucket,
  station_id,
  AVG(temperature) as avg_temperature,
  MIN(temperature) as min_temperature,
  MAX(temperature) as max_temperature,
  AVG(humidity) as avg_humidity,
  SUM(rainfall) as total_rainfall,
  AVG(wind_speed) as avg_wind_speed
FROM weather_readings
GROUP BY bucket, station_id;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('weather_hourly',
  start_offset => INTERVAL '3 hours',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');
```

### 3. Redis Setup

```bash
# Start Redis with persistence
docker run -d \
  --name redis-weather \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:7-alpine redis-server --appendonly yes
```

### 4. MQTT Broker Setup (Mosquitto)

```bash
# Create mosquitto config
cat > mosquitto.conf << EOF
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd
EOF

# Create password file
docker run -it --rm -v $(pwd):/mosquitto/config eclipse-mosquitto mosquitto_passwd -c /mosquitto/config/passwd weather_user

# Start Mosquitto
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  -v $(pwd)/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  -v $(pwd)/passwd:/mosquitto/config/passwd \
  eclipse-mosquitto
```

## Environment Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Update the `.env` file with your actual values:
```bash
# Databases
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DATABASE=aos_weather
TIMESCALE_USER=your_user
TIMESCALE_PASSWORD=your_password

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=weather_integration
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# MQTT
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=weather_user
MQTT_PASSWORD=your_mqtt_password

# JWT Secret (generate a strong secret)
JWT_SECRET=your-very-long-random-string
```

## Installation

```bash
# Navigate to service directory
cd services/weather-monitoring

# Install dependencies
npm install

# Build TypeScript
npm run build

# Run database migrations (if available)
# npm run migrate

# Start in development mode
npm run dev

# Or start in production mode
npm start
```

## Docker Deployment

```bash
# Build Docker image
docker build -t weather-monitoring-service .

# Run with Docker Compose
docker-compose up -d
```

## Initial Data Setup

### 1. Add Sample Weather Stations

```sql
-- Insert sample stations
INSERT INTO weather_stations (station_id, name, type, location_lat, location_lng, source) VALUES
('VTBD', 'Don Mueang International Airport', 'AERONAUTICAL', 13.9126, 100.6070, 'AOS'),
('TMD001', 'Bangkok Metropolis', 'SYNOPTIC', 13.7278, 100.5241, 'TMD'),
('CUSTOM001', 'Munbon Project Station 1', 'AGRICULTURAL', 14.5896, 101.3764, 'CUSTOM');
```

### 2. Test MQTT Connection

```bash
# Subscribe to test topic
mosquitto_sub -h localhost -p 1883 -u weather_user -P your_password -t weather/test

# Publish test message
mosquitto_pub -h localhost -p 1883 -u weather_user -P your_password -t weather/test -m "Hello Weather Service"
```

### 3. Test API Endpoints

```bash
# Health check
curl http://localhost:3055/health

# Get current weather
curl http://localhost:3055/api/v1/weather/current?lat=13.7278&lng=100.5241

# Get weather stations
curl http://localhost:3055/api/v1/weather/stations
```

## Integration with Kong API Gateway

Add the service to Kong:

```bash
# Create service
curl -i -X POST http://localhost:8001/services/ \
  --data "name=weather-monitoring-service" \
  --data "url=http://weather-monitoring-service:3055"

# Create route
curl -i -X POST http://localhost:8001/services/weather-monitoring-service/routes \
  --data "paths[]=/api/weather" \
  --data "strip_path=false"
```

## Monitoring Setup

### 1. Prometheus Metrics

The service exposes metrics at `/metrics` endpoint. Add to Prometheus config:

```yaml
scrape_configs:
  - job_name: 'weather-monitoring'
    static_configs:
      - targets: ['weather-monitoring-service:3055']
```

### 2. Logging

Logs are output in JSON format. For production, consider using:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Grafana Loki
- CloudWatch Logs (AWS)

## Security Considerations

1. **JWT Token**: Generate a strong JWT secret (min 256 bits)
2. **Database Passwords**: Use strong, unique passwords
3. **MQTT Security**: Always use authentication, consider TLS
4. **API Rate Limiting**: Configure in Kong/Traefik
5. **CORS**: Restrict to known frontends only
6. **Network Policies**: Implement Kubernetes network policies

## Troubleshooting

### Database Connection Issues
```bash
# Test PostgreSQL connection
psql -h localhost -U weather_user -d weather_integration -c "SELECT 1"

# Test TimescaleDB connection
psql -h localhost -p 5433 -U weather_user -d aos_weather -c "SELECT 1"
```

### Redis Connection Issues
```bash
# Test Redis connection
redis-cli -h localhost ping
```

### MQTT Connection Issues
```bash
# Check MQTT broker logs
docker logs mosquitto
```

### Service Not Starting
1. Check all environment variables are set
2. Verify all dependencies are running
3. Check logs: `npm run dev` or `docker logs weather-monitoring`

## Performance Tuning

1. **Database Indexes**: Ensure all indexes are created
2. **Redis Memory**: Set appropriate `maxmemory` policy
3. **Connection Pools**: Adjust pool sizes based on load
4. **Cache TTL**: Fine-tune cache expiration times
5. **TimescaleDB Chunks**: Monitor chunk sizes and adjust if needed

## Backup and Recovery

### Database Backup
```bash
# PostgreSQL
pg_dump -h localhost -U weather_user weather_integration > weather_backup.sql

# TimescaleDB
pg_dump -h localhost -p 5433 -U weather_user aos_weather > aos_backup.sql
```

### Redis Backup
```bash
# Save Redis data
docker exec redis-weather redis-cli BGSAVE
```

## Next Steps

1. Configure monitoring dashboards
2. Set up alerting rules
3. Implement backup automation
4. Configure auto-scaling policies
5. Set up CI/CD pipeline