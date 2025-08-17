# Test Results Report - EC2 IP Migration

## Test Date: 2025-08-13

## 1. Connection Test Results (`./test-new-ec2-connection.sh`)

### ✅ Successful Connections:
- **PostgreSQL munbon_dev** - Connected successfully
- **TimescaleDB sensor_data** - Connected successfully  
- **AWD schema** - Accessible (0 fields configured)

### ❌ Failed Connections:
- **SCADA database (db_scada)** - Database does not exist on new server
- **tb_gatelevel_command table** - Not accessible (database missing)

### Analysis:
The `db_scada` database is not present on the new EC2 instance at IP `43.209.22.250`. This is critical for SCADA gate control functionality.

## 2. Service Startup Test (`npm run dev`)

### ❌ Failed to Start
**Error**: TimescaleDB pool not initialized

**Root Cause**: The service is trying to initialize database connections during module loading, which fails because the TimescaleDB connection cannot be established properly.

**Stack Trace**:
```
Error: TimescaleDB pool not initialized
    at getTimescalePool (/Users/subhajlimanond/dev/munbon2-backend/services/awd-control/src/config/database.ts:68:11)
    at SensorRepository.<instance_members_initializer>
```

## 3. SCADA Integration Test (`./test-scada-integration.sh`)

### ❌ Failed
- Connected to SCADA database (false positive - likely connecting to wrong DB)
- tb_gatelevel_command table not found

## Summary of Issues

### Critical Issues:
1. **Missing SCADA Database**: The `db_scada` database does not exist on the new EC2 instance
2. **Service Cannot Start**: Database initialization errors prevent the service from starting

### Database Status on New Server (43.209.22.250):
- ✅ munbon_dev (exists)
- ✅ munbon_timescale (exists)
- ✅ sensor_data (exists)
- ❌ db_scada (missing)

## Recommended Actions

### Immediate Actions:
1. **Create db_scada database** on the new server:
   ```sql
   CREATE DATABASE db_scada;
   ```

2. **Create required SCADA tables**:
   ```sql
   CREATE TABLE tb_gatelevel_command (
     id SERIAL PRIMARY KEY,
     gate_name VARCHAR(50),
     gate_level INTEGER,
     startdatetime TIMESTAMP,
     completestatus INTEGER
   );
   
   CREATE TABLE tb_site (
     stationcode VARCHAR(50),
     site_name VARCHAR(255)
   );
   ```

3. **Fix service initialization** - The service needs to handle database connection errors more gracefully during startup

### Alternative Solutions:
1. **If SCADA remains on old server**: Update only SCADA_DB_HOST back to old IP (43.209.12.182)
2. **If migrating SCADA data**: Need to dump and restore from old server to new server

## Configuration Status

All configuration files have been updated to use the new IP (43.209.22.250):
- ✅ .env file updated
- ✅ Source code defaults updated
- ✅ Scripts updated
- ✅ Documentation updated

## Next Steps

Please confirm:
1. Should the `db_scada` database be created on the new server?
2. Or does it remain on the old server (43.209.12.182)?
3. Do you have a backup of the SCADA database that needs to be restored?

Without the SCADA database, the gate control functionality will not work.