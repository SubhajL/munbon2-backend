# EC2 IP Address Migration Summary

## Overview
All references to the EC2 database server have been updated from the old IP address `43.209.22.250` to the new IP address `43.209.22.250`.

## Files Updated

### 1. Configuration Files
- **`.env`** - Updated all database host references:
  - `POSTGRES_HOST=43.209.22.250`
  - `TIMESCALE_HOST=43.209.22.250`
  - `SCADA_DB_HOST=43.209.22.250`

### 2. Source Code
- **`src/services/scada-gate-control.service.ts`** - Updated default host in Pool configuration:
  ```typescript
  host: process.env.SCADA_DB_HOST || '43.209.22.250',
  ```

### 3. Scripts
- **`scripts/initialize-awd-databases.sh`** - Updated default host values:
  - `POSTGRES_HOST=${POSTGRES_HOST:-"43.209.22.250"}`
  - `TIMESCALE_HOST=${TIMESCALE_HOST:-"43.209.22.250"}`

- **`scripts/verify-tables.sh`** - Updated default host:
  - `POSTGRES_HOST=${POSTGRES_HOST:-"43.209.22.250"}`

- **`test-scada-integration.sh`** - Updated all psql commands to use new IP

### 4. Documentation
- **`docs/scada-gate-control-integration.md`** - Updated:
  - Environment variable example
  - psql command examples

- **`docs/testing-water-level-control.md`** - Updated:
  - Database location reference
  - All psql test commands
  - Troubleshooting section

- **`docs/awd-service-flow-diagram.md`** - Updated:
  - Database connection diagram header

- **`IMPLEMENTATION_COMPLETE.md`** - Updated:
  - Environment variable configuration example

## New Files Created
- **`test-new-ec2-connection.sh`** - New script to verify connectivity to the new EC2 instance

## Services Affected
All services that connect to the EC2 databases will use the new IP:
1. AWD Control Service (Port 3013)
2. SCADA Gate Control integration
3. Sensor data retrieval from TimescaleDB
4. All PostgreSQL operations

## Testing Recommendations

### 1. Run Connection Test
```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/awd-control
./test-new-ec2-connection.sh
```

### 2. Verify Service Startup
```bash
# Start the service and check logs
npm run dev

# Look for successful database connections in logs
```

### 3. Test SCADA Integration
```bash
./test-scada-integration.sh
```

### 4. Verify API Endpoints
```bash
# Health check
curl http://localhost:3013/health

# If authenticated, test irrigation control
curl -X POST http://localhost:3013/api/v1/awd/control/fields/{fieldId}/irrigation/start \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"targetLevelCm": 10}'
```

## Important Notes

1. **No Physical Server Changes**: The physical server remains the same, only the IP address has changed
2. **Database Names Unchanged**: All database names and schemas remain the same
3. **Credentials Unchanged**: All usernames and passwords remain the same
4. **Port Numbers Unchanged**: All services still use the same ports

## Rollback Plan
If needed to rollback to the old IP:
1. Update `.env` file with old IP `43.209.22.250`
2. Restart the service
3. The hardcoded defaults in source code would need manual updates

## Migration Status
✅ **COMPLETE** - All references have been updated to the new IP address `43.209.22.250`