# Database Service Mapping

This document provides a comprehensive mapping of which database each service uses in the Munbon backend.

## Database Overview

### Main Databases:
1. **munbon_dev** (PostgreSQL on port 5434) - Main application database
2. **sensor_data** (TimescaleDB on port 5433) - Time-series sensor data

### Additional Databases Referenced:
- **munbon_ros** - ROS service specific database
- **munbon_awd** - AWD control specific database
- **munbon_timeseries** - General time-series data
- **munbon_gis** - GIS data

## Service-to-Database Mapping

### 1. **Authentication Service** (`/services/auth`)
- **Database**: munbon_dev (port 5434)
- **Schema**: `auth`
- **Connection**: Via DATABASE_URL environment variable
- **Tables**: 
  - users, roles, permissions
  - refresh_tokens, login_attempts
  - password_resets, two_factor_secrets
  - audit_logs, sessions

### 2. **GIS Service** (`/services/gis`)
- **Database**: munbon_dev (port 5434)
- **Schema**: `gis`
- **Connection**: Via DATABASE_URL environment variable
- **Features**: PostGIS extensions enabled
- **Tables**:
  - irrigation_zones, agricultural_plots
  - canal_network, control_structures
  - parcels, gates, pumps, water_sources
  - irrigation_blocks, spatial_indexes
  - shape_file_uploads

### 3. **Sensor Data Service** (`/services/sensor-data`)
- **Databases**: 
  - **Primary**: sensor_data (TimescaleDB on port 5433)
  - **Secondary**: MSSQL (for SCADA integration)
- **Connection**: 
  - TimescaleDB: TIMESCALE_HOST/PORT/DB environment variables
  - MSSQL: MSSQL_HOST/PORT/DB environment variables
- **Purpose**: Handles sensor telemetry and SCADA data integration

### 4. **ROS Service** (`/services/ros`)
- **Database**: munbon_ros (port 5434)
- **Connection**: Via DB_HOST/PORT/NAME environment variables
- **Default Config**:
  - Host: localhost
  - Port: 5434
  - Database: munbon_ros
- **Purpose**: Reference evapotranspiration and water demand calculations

### 5. **Flow Monitoring Service** (`/services/flow-monitoring`)
- **Databases**:
  - **InfluxDB**: For real-time flow metrics
  - **TimescaleDB**: For aggregated hydraulic data
  - **PostgreSQL**: For configuration and metadata
- **Connections**:
  - INFLUXDB_URL, INFLUXDB_TOKEN environment variables
  - TIMESCALE_URL environment variable
  - POSTGRES_URL environment variable
- **Tables/Measurements**:
  - flow_aggregates, water_balance (TimescaleDB)
  - flow_anomalies (TimescaleDB)
  - flow_sensors, monitoring_locations (PostgreSQL)
  - hydraulic_models, calibration_history (PostgreSQL)

### 6. **AWD Control Service** (`/services/awd-control`)
- **Databases**:
  - **PostgreSQL**: munbon_awd (port 5432)
  - **TimescaleDB**: munbon_timeseries (port 5433)
- **Schemas**:
  - Main schema in PostgreSQL
  - `gis` schema for GIS integration
- **Tables**:
  - PostgreSQL: awd_fields, awd_configurations, awd_sensors, irrigation_schedules
  - TimescaleDB: awd_sensor_readings, irrigation_events, water_level_readings, moisture_readings
  - GIS schema: water_level_measurements, field_attributes

### 7. **Weather Monitoring Service** (`/services/weather-monitoring`)
- **Database**: Not explicitly defined in checked files
- **Services Used**: 
  - DatabaseService (custom implementation)
  - CacheService (likely Redis)
- **Purpose**: Weather data collection and irrigation recommendations

### 8. **Moisture Monitoring Service** (`/services/moisture-monitoring`)
- **Database**: TimescaleDB
- **Connection**: TIMESCALE_HOST/PORT/DATABASE environment variables
- **Cache**: Redis (port 6379, DB 2)
- **Purpose**: Soil moisture monitoring and alerts

### 9. **RID-MS Service** (`/services/rid-ms`)
- **Database**: munbon_gis (PostgreSQL on port 5432)
- **Connection**: POSTGRES_HOST/PORT/DB environment variables
- **Purpose**: Shapefile processing and water demand calculations
- **Integration**: Kafka for event streaming

### 10. **Water Level Monitoring Service** (`/services/water-level-monitoring`)
- **Database**: Likely uses sensor_data (TimescaleDB)
- **Purpose**: Water level sensor data collection

## Database Port Summary

- **5432**: Standard PostgreSQL (AWD Control, RID-MS)
- **5433**: TimescaleDB (Sensor Data, Time-series data)
- **5434**: Main PostgreSQL (Auth, GIS, ROS)
- **6379**: Redis (Caching across all services)
- **8086**: InfluxDB (Flow Monitoring)

## Schema Organization

### munbon_dev (5434)
- `auth` schema - Authentication service
- `gis` schema - GIS service
- `public` schema - Shared resources

### sensor_data (5433)
- Time-series tables with hypertables
- Sensor readings and telemetry data

### Service-Specific Databases
- `munbon_ros` - ROS calculations
- `munbon_awd` - AWD control data
- `munbon_gis` - GIS and shapefile data

## Key Observations

1. **Database Consolidation**: Most services use either munbon_dev (5434) or sensor_data (5433)
2. **Schema Isolation**: Services use separate schemas for data isolation
3. **Time-series Specialization**: All sensor/telemetry data uses TimescaleDB
4. **Caching Strategy**: Redis is used consistently across services
5. **Mixed Database Types**: Services like Flow Monitoring use multiple database types (InfluxDB, TimescaleDB, PostgreSQL) for different purposes

## Recommendations

1. Consider consolidating munbon_ros, munbon_awd, and munbon_gis into munbon_dev with separate schemas
2. Standardize TimescaleDB usage for all time-series data
3. Document environment variable naming conventions
4. Consider using connection pooling for database efficiency