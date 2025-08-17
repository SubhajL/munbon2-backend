# Database Configuration for Munbon Backend

## Current Database Setup

### 1. Local Development Databases

#### munbon_dev (PostgreSQL) - Port 5434
- **Purpose**: Main application database
- **Schemas**: 
  - `gis` - GIS/spatial data (parcels, zones, canals)
  - `ros` - ROS water demand calculations
- **Connection**: `postgresql://postgres:postgres@localhost:5434/munbon_dev`

#### munbon_timescale (TimescaleDB) - Port 5433
- **Purpose**: Time-series sensor data
- **Schema**: `public`
- **Connection**: `postgresql://postgres:postgres@localhost:5433/munbon_timescale`

### 2. Production Database (AWS EC2) - Port 5432
- **Purpose**: Production database (target for migration)
- **Will contain**: Both munbon_dev and munbon_timescale data after migration
- **Connection**: `postgresql://postgres:password@ec2-host:5432/munbon`

## Service Configuration

### GIS Service
```bash
# Local development
export DATABASE_URL="postgresql://postgres:postgres@localhost:5434/munbon_dev"

# Production
export DATABASE_URL="postgresql://postgres:password@ec2-host:5432/munbon"
```

### ROS Service
```bash
# Local development
export DATABASE_URL="postgresql://postgres:postgres@localhost:5434/munbon_dev"

# Production
export DATABASE_URL="postgresql://postgres:password@ec2-host:5432/munbon"
```

### ROS-GIS Integration Service
```bash
# Local development
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5434/munbon_dev"

# Production
export POSTGRES_URL="postgresql://postgres:password@ec2-host:5432/munbon"
```

### Sensor Data Service
```bash
# Local development (TimescaleDB)
export TIMESCALE_URL="postgresql://postgres:postgres@localhost:5433/munbon_timescale"

# Production (will be in same DB after migration)
export TIMESCALE_URL="postgresql://postgres:password@ec2-host:5432/munbon"
```

## ROS-GIS Consolidation Migration

The ROS water demands table will be created in the `gis` schema:

```bash
# For local development
cd services/gis/scripts
export DB_HOST="localhost"
export DB_PORT="5434"
export DB_NAME="munbon_dev"
export DB_USER="postgres"
export DB_PASSWORD="postgres"
export DB_SCHEMA="gis"
./run-ros-migration.sh

# For production (after main migration)
export DB_HOST="ec2-host"
export DB_PORT="5432"
export DB_NAME="munbon"
export DB_USER="postgres"
export DB_PASSWORD="your_password"
export DB_SCHEMA="gis"
./run-ros-migration.sh
```

## Important Notes

1. **Schema Location**: The `ros_water_demands` table is created in the `gis` schema, not `ros` schema, because:
   - It needs to reference `agricultural_plots` table in `gis` schema
   - It's part of the GIS service API
   - It consolidates ROS calculations with GIS spatial data

2. **After AWS Migration**: Once both databases are migrated to AWS EC2:
   - All services will connect to port 5432
   - Schemas will be: `gis`, `ros`, `public` (for timescale data)
   - Update all connection strings to use AWS endpoint

3. **Development vs Production**: Always use:
   - Port 5434 for local GIS/ROS development
   - Port 5433 for local sensor/timescale development  
   - Port 5432 for production AWS EC2