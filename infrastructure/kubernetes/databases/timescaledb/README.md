# TimescaleDB Setup for Munbon Backend

TimescaleDB is used for storing and querying time-series sensor data including moisture readings, water levels, flow rates, and weather data.

## Architecture Overview

- **Database**: `sensor_data`
- **Schemas**:
  - `sensor`: Core sensor metadata and readings
  - `aggregates`: Continuous aggregates for performance
  - `maintenance`: Maintenance and calibration logs

## Local Development Setup

### Using Docker Compose

```bash
# Start TimescaleDB
docker-compose up -d timescaledb

# Check logs
docker-compose logs -f timescaledb

# Connect to database
docker exec -it munbon-timescaledb psql -U postgres -d sensor_data
```

### Using Kubernetes

```bash
# Apply base configuration
kubectl apply -k infrastructure/kubernetes/databases/timescaledb/base

# Apply local overlay for development
kubectl apply -k infrastructure/kubernetes/databases/timescaledb/overlays/local

# Check status
kubectl get pods -n munbon-databases -l app=timescaledb
kubectl get pvc -n munbon-databases -l app=timescaledb

# Port forward for local access
kubectl port-forward -n munbon-databases svc/timescaledb 5433:5432
```

## Database Schema

### Core Tables

1. **sensor.sensors** - Sensor metadata
   - Stores sensor information, location, type, and configuration
   - Uses PostGIS for spatial queries

2. **sensor.readings** - Generic sensor readings (hypertable)
   - Time-series data for all sensor types
   - Partitioned by time (7-day chunks)
   - Compressed after 7 days

3. **Specialized Tables**:
   - `sensor.moisture_readings` - Soil moisture data
   - `sensor.water_level_readings` - Water level measurements
   - `sensor.weather_readings` - Weather station data
   - `sensor.flow_readings` - Flow meter data

### Continuous Aggregates

- **5-minute aggregates**: Real-time monitoring
- **Hourly aggregates**: Trending and analysis
- **Daily aggregates**: Historical reporting

## Connection Details

### Local Development
- **Host**: localhost
- **Port**: 5433 (Docker) or 30433 (Kubernetes NodePort)
- **Database**: sensor_data
- **Username**: postgres
- **Password**: postgres

### Application User
- **Username**: sensor_service
- **Password**: sensor-munbon-2024!
- **Permissions**: Read/write on sensor schema

## Performance Tuning

The configuration is optimized for time-series workloads:

- **Shared Buffers**: 1GB (production) / 256MB (local)
- **Effective Cache Size**: 3GB (production) / 1GB (local)
- **Chunk Size**: 7 days for optimal query performance
- **Compression**: Enabled for data > 7 days
- **Retention**: 1 year for raw data

## Monitoring

### Check Database Size
```sql
SELECT hypertable_size('sensor.readings');
SELECT * FROM timescaledb_information.hypertables;
```

### Check Continuous Aggregates
```sql
SELECT * FROM timescaledb_information.continuous_aggregates;
SELECT * FROM timescaledb_information.jobs;
```

### Monitor Compression
```sql
SELECT * FROM timescaledb_information.compressed_chunk_stats;
```

## Backup and Recovery

### Manual Backup
```bash
# Backup specific hypertables
docker exec munbon-timescaledb pg_dump -U postgres -d sensor_data \
  --schema=sensor --schema=aggregates -f /backup/sensor_data.sql

# Backup with compression
docker exec munbon-timescaledb pg_dump -U postgres -d sensor_data \
  -Fc -f /backup/sensor_data.dump
```

### Restore
```bash
# Restore from SQL
docker exec -i munbon-timescaledb psql -U postgres -d sensor_data < sensor_data.sql

# Restore from dump
docker exec munbon-timescaledb pg_restore -U postgres -d sensor_data /backup/sensor_data.dump
```

## Common Queries

### Get Latest Sensor Reading
```sql
SELECT * FROM sensor.get_latest_reading('MS001');
```

### Check Sensor Health
```sql
SELECT * FROM sensor.check_sensor_health('MS001', 24);
```

### Query Aggregated Data
```sql
-- Hourly average moisture
SELECT bucket, sensor_id, avg_moisture 
FROM aggregates.moisture_hourly
WHERE bucket > NOW() - INTERVAL '24 hours'
ORDER BY bucket DESC;
```

### Spatial Queries
```sql
-- Find sensors within 1km radius
SELECT sensor_id, ST_Distance(location, ST_GeogFromText('POINT(100.5342 13.7279)')) as distance
FROM sensor.sensors
WHERE ST_DWithin(location, ST_GeogFromText('POINT(100.5342 13.7279)'), 1000)
ORDER BY distance;
```

## Troubleshooting

### Check TimescaleDB Version
```sql
SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';
```

### Repair Continuous Aggregates
```sql
CALL refresh_continuous_aggregate('aggregates.readings_5min', NULL, NULL);
```

### Check Background Jobs
```sql
SELECT * FROM timescaledb_information.jobs WHERE proc_name LIKE '%policy%';
```

## Integration with Services

The Sensor Data Service (Task 8) will be the primary consumer of this database, providing:
- Real-time data ingestion via MQTT
- REST API for historical queries
- WebSocket streaming for live data
- Integration with AI models for predictions