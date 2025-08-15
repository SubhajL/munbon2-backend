# Database Consolidation Mapping

## Overview
Consolidating local databases to EC2 PostgreSQL instance on port 5432.

### Current State (Local):
- **munbon_dev** (PostgreSQL on port 5434) - Main application database
- **sensor_data** (TimescaleDB on port 5433) - Time-series sensor data

### Target State (EC2):
- **munbon_dev** (PostgreSQL on port 5432) - Consolidated application database
- **sensor_data** (PostgreSQL with TimescaleDB on port 5432) - Time-series database

## Database Mapping

### 1. munbon_dev (5434) → munbon_dev (5432)
All schemas from local munbon_dev will remain in EC2 munbon_dev:
- `auth` schema - Authentication service
- `gis` schema - GIS service  
- `ros` schema - ROS service data
- `public` schema - Shared resources
- `config` schema - Configuration data
- `tiger`, `tiger_data`, `topology` schemas - PostGIS geocoding

### 2. sensor_data (5433) → sensor_data (5432)
All schemas from local sensor_data will remain in EC2 sensor_data:
- `public` schema - Sensor registry and readings
- `sensor` schema - Sensor management
- TimescaleDB hypertables for time-series data

## Service Configuration Changes

### 1. **Authentication Service** (`/services/auth`)
```env
# From:
DATABASE_URL=postgresql://postgres:postgres@localhost:5434/munbon_dev?schema=auth

# To:
DATABASE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev?schema=auth
```

### 2. **GIS Service** (`/services/gis`)
```env
# From:
DATABASE_URL=postgresql://postgres:postgres@localhost:5434/munbon_dev?schema=gis

# To:
DATABASE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev?schema=gis
```

### 3. **ROS Service** (`/services/ros`)
```env
# From:
DB_HOST=localhost
DB_PORT=5434
DB_NAME=munbon_ros

# To:
DB_HOST=43.209.22.250
DB_PORT=5432
DB_NAME=munbon_dev
DB_SCHEMA=ros  # New: specify schema
```

### 4. **Sensor Data Service** (`/services/sensor-data`)
```env
# From:
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=munbon_timescale

# To:
TIMESCALE_HOST=43.209.22.250
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
```

### 5. **Moisture Monitoring Service** (`/services/moisture-monitoring`)
```env
# From:
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DATABASE=sensor_data

# To:
TIMESCALE_HOST=43.209.22.250
TIMESCALE_PORT=5432
TIMESCALE_DATABASE=sensor_data
```

### 6. **Weather Monitoring Service** (`/services/weather-monitoring`)
```env
# From:
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/sensor_data

# To:
DATABASE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/sensor_data
```

### 7. **Water Level Monitoring Service** (`/services/water-level-monitoring`)
```env
# From:
TIMESCALE_URL=postgresql://postgres:postgres@localhost:5433/sensor_data

# To:
TIMESCALE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/sensor_data
```

### 8. **AWD Control Service** (`/services/awd-control`)
```env
# From:
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=munbon_awd
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=munbon_timeseries

# To:
POSTGRES_HOST=43.209.22.250
POSTGRES_PORT=5432
POSTGRES_DB=munbon_dev
POSTGRES_SCHEMA=awd  # New: use schema in munbon_dev
TIMESCALE_HOST=43.209.22.250
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
```

### 9. **RID-MS Service** (`/services/rid-ms`)
```env
# From:
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=munbon_gis

# To:
POSTGRES_HOST=43.209.22.250
POSTGRES_PORT=5432
POSTGRES_DB=munbon_dev
POSTGRES_SCHEMA=gis  # Use existing gis schema
```

### 10. **Flow Monitoring Service** (`/services/flow-monitoring`)
```env
# From:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/munbon
TIMESCALE_URL=postgresql://postgres:postgres@localhost:5433/sensor_data

# To:
DATABASE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev
TIMESCALE_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/sensor_data
```

## Schema Creation for New Services

Some services need new schemas in munbon_dev:

```sql
-- Create AWD schema for AWD Control Service
CREATE SCHEMA IF NOT EXISTS awd;

-- Grant permissions
GRANT ALL ON SCHEMA awd TO postgres;
GRANT USAGE ON SCHEMA awd TO postgres;
GRANT CREATE ON SCHEMA awd TO postgres;
```

## Docker Compose Environment Updates

### For docker-compose.ec2.yml:
```yaml
x-common-variables: &common-variables
  # PostgreSQL Connection (single instance on EC2)
  POSTGRES_HOST: 43.209.22.250
  POSTGRES_PORT: 5432
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: P@ssw0rd123!
  
  # TimescaleDB is same as PostgreSQL
  TIMESCALE_HOST: 43.209.22.250
  TIMESCALE_PORT: 5432
  TIMESCALE_USER: postgres
  TIMESCALE_PASSWORD: P@ssw0rd123!
```

## Migration Steps

1. **Verify EC2 databases exist**:
   ```bash
   psql -h 43.209.22.250 -U postgres -c "\l"
   ```

2. **Create missing schemas**:
   ```bash
   psql -h 43.209.22.250 -U postgres -d munbon_dev -c "CREATE SCHEMA IF NOT EXISTS awd;"
   ```

3. **Update service configurations**:
   - Update all .env files with new connection strings
   - Update docker-compose files with new environment variables

4. **Deploy services**:
   - Use docker-compose.ec2.yml for deployment
   - All services connect to single PostgreSQL instance on EC2

## Benefits of Consolidation

1. **Simplified Management**: Single PostgreSQL instance to maintain
2. **Better Resource Utilization**: One database server instead of three
3. **Easier Backups**: Single backup strategy for all data
4. **Reduced Complexity**: No need to manage multiple database versions
5. **Cost Efficiency**: Single EC2 instance for database

## Important Notes

- TimescaleDB extension is installed in the sensor_data database
- PostGIS extension is installed in the munbon_dev database
- All services use schema isolation for data separation
- Redis remains as a separate service for caching