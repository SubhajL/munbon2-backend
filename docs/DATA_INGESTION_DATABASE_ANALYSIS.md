# Data Ingestion Database Analysis

## Executive Summary

**NO**, the data ingestion services are **NOT** currently writing to both local and EC2 databases. Here's the actual situation:

## 1. Sensor Data Service (Water Level & Moisture)

### Current Configuration
- **Primary Database**: Local TimescaleDB (localhost:5433)
- **Database Name**: `munbon_timescale`
- **Dual-Write**: **DISABLED** (code exists but not activated)

### Evidence
1. Current `.env` configuration:
   ```
   TIMESCALE_HOST=localhost
   TIMESCALE_PORT=5433
   TIMESCALE_DB=munbon_timescale
   ENABLE_DUAL_WRITE=<not set>  # Defaults to false
   ```

2. Dual-write infrastructure exists:
   - `src/config/dual-write.config.ts` - Configuration
   - `src/repository/dual-write.repository.ts` - Implementation
   - `.env.dual-write` - Example configuration (not active)

3. To enable dual-write, you would need to:
   ```bash
   ENABLE_DUAL_WRITE=true
   EC2_DB_HOST=43.209.22.250
   EC2_DB_PORT=5432
   EC2_DB_NAME=sensor_data
   EC2_DB_USER=postgres
   EC2_DB_PASSWORD=P@ssw0rd123!
   ```

### Current Data Flow
```
Sensors → HTTP Endpoint (EC2) → SQS → Consumer → Local TimescaleDB ONLY
```

## 2. GIS Service (GeoPackage Upload)

### Current Configuration
- **Primary Database**: EC2 PostgreSQL (43.209.22.250:5432)
- **Database Name**: `munbon_dev`
- **Schema**: `gis`
- **Dual-Write**: **NO** (writes only to EC2)

### Evidence
1. Current `.env` configuration:
   ```
   DATABASE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev?schema=gis
   ```

2. No dual-write code exists in GIS service
3. All writes go directly to EC2

### Current Data Flow
```
GeoPackage Upload → S3 → SQS → GIS Processor → EC2 PostgreSQL ONLY
```

## 3. Data Synchronization Status

### Sensor Data (Moisture/Water Level)
- **Local TimescaleDB**: Has all recent data
- **EC2 Database**: No sensor data (dual-write disabled)
- **Status**: ❌ Not synchronized

### GIS Data (Parcels/Zones)
- **Local PostgreSQL (5434)**: Has 15,069 parcels (historical data)
- **EC2 PostgreSQL**: Has same 15,069 parcels
- **Status**: ✅ Synchronized (but GIS service only writes to EC2 now)

## 4. Why This Architecture?

1. **Sensor Data**: 
   - High volume (thousands of readings per hour)
   - Requires TimescaleDB for time-series optimization
   - Local processing reduces latency
   - Dual-write code ready but disabled (performance concerns?)

2. **GIS Data**:
   - Low volume (occasional uploads)
   - Requires PostGIS for spatial queries
   - EC2 hosting makes sense for web access
   - No need for dual-write

## 5. Recommendations

### Option 1: Enable Dual-Write for Sensor Data
```bash
# Copy dual-write config
cp .env.dual-write .env
# Restart consumer
pm2 restart sensor-consumer
```
**Pros**: Data redundancy, EC2 backup
**Cons**: Network latency, potential failures, double storage costs

### Option 2: Keep Current Architecture
- Sensor data stays local (optimized for ingestion)
- GIS data stays on EC2 (optimized for web access)
- Set up periodic sync/backup between databases

### Option 3: Migrate Everything to EC2
- Move TimescaleDB to EC2
- Single point of truth
- Higher latency for sensor ingestion

## Conclusion

The system is **NOT** doing dual-writes. Each service writes to its designated database:
- **Sensor Data** → Local TimescaleDB only
- **GIS Data** → EC2 PostgreSQL only

The dual-write capability exists for sensor data but is currently disabled.