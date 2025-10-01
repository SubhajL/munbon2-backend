# Smart Farm Water Control Integration Guide

This guide explains how to integrate the Smart Farm Water Control service with the existing Munbon backend services.

## Service Dependencies

The Smart Farm Water Control service integrates with the following services:

### 1. External API Service (Sensor Data)

**Service URL**: `http://localhost:3015` (or your deployed URL)
**Authentication**: API Key required

The external-api service provides authenticated access to sensor data. Update your `.env` file:

```env
SENSOR_DATA_SERVICE_URL=http://localhost:3015
SENSOR_DATA_API_KEY=your-api-key-here
```

#### Available Endpoints:

- `GET /api/v1/public/water-levels/latest` - Latest water level readings
- `GET /api/v1/public/water-levels/timeseries` - Historical water level data
- `GET /api/v1/public/moisture/latest` - Latest moisture readings
- `GET /api/v1/public/moisture/timeseries` - Historical moisture data

#### Example Request:

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:3015/api/v1/public/moisture/latest?sensor_id=MOIST-SF06-001"
```

### 2. ROS Service (Water Demand Calculation)

**Service URL**: `http://localhost:3001` (or your deployed URL)
**Authentication**: API Key required

The ROS service calculates daily water demands. Update your `.env` file:

```env
ROS_API_URL=http://localhost:3001
ROS_API_KEY=your-ros-api-key
ROS_CALCULATION_ENDPOINT=/api/v1/ros/demand/calculate
```

#### Water Demand Calculation

The endpoint expects a POST request with the following structure:

```json
{
  "cropType": "rice",
  "calculationDate": "2025-01-01",
  "calculationPeriod": 1,
  "plantings": [
    {
      "plantingDate": "2024-12-01",
      "areaRai": 2.5,
      "growthDays": null
    }
  ],
  "nonAgriculturalDemands": []
}
```

### 3. Database Configuration

#### TimescaleDB (Sensor Data & Water Planning)

```env
TIMESCALE_HOST=postgres-aws-munbon.region.rds.amazonaws.com
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=your-password
```

The service will create the following schemas if they don't exist:
- `ros_gis_smartfarm` - For water planning data
- `water_control_smartfarm` - For control and balance data

#### MSSQL (Valve Commands)

```env
MSSQL_HOST=moonup.hopto.org
MSSQL_PORT=1433
MSSQL_DB=db_scada
MSSQL_USER=your-mssql-user
MSSQL_PASSWORD=your-mssql-password
```

Valve commands are written to the `tb_valve_command_v2` table.

## Getting API Keys

### External API Service

1. Check if API keys are already configured in the external-api service
2. Look for configuration in `/services/external-api/.env`
3. API keys might be stored in AWS Parameter Store or environment variables

### ROS Service

1. Check ROS service configuration in `/services/ros/.env`
2. API keys may be configured in the service itself
3. Contact the ROS service maintainer for access

## Testing Integration

### 1. Test Sensor Data Connection

```bash
# Test water level sensor
curl -X GET "http://localhost:3015/api/v1/public/water-levels/latest?sensor_id=AWD-SF01" \
  -H "X-API-Key: your-api-key"

# Test moisture sensor
curl -X GET "http://localhost:3015/api/v1/public/moisture/latest?sensor_id=MOIST-SF06-001" \
  -H "X-API-Key: your-api-key"
```

### 2. Test ROS Integration

```bash
# Test water demand calculation
curl -X POST "http://localhost:3001/api/v1/ros/demand/calculate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-ros-api-key" \
  -d '{
    "cropType": "rice",
    "calculationDate": "2025-01-01",
    "calculationPeriod": 1,
    "plantings": [{
      "plantingDate": "2024-12-01",
      "areaRai": 2.5
    }]
  }'
```

### 3. Test Database Connections

```bash
# Test TimescaleDB
psql -h postgres-aws-munbon.region.rds.amazonaws.com -U postgres -d sensor_data

# Test MSSQL
sqlcmd -S moonup.hopto.org,1433 -U your-user -P your-password -d db_scada
```

## Running with Real Services

1. Copy the production configuration:
   ```bash
   cp .env.production .env
   ```

2. Update the `.env` file with actual credentials

3. Ensure dependent services are running:
   - External API service on port 3015
   - ROS service on port 3001
   - Database connections are accessible

4. Start the Smart Farm service:
   ```bash
   npm start
   ```

## Monitoring Integration

Check the logs for successful connections:

```bash
# Look for successful sensor readings
grep "Sensor reading retrieved" logs/combined.log

# Check for ROS API calls
grep "Water demand calculated" logs/combined.log

# Monitor valve commands
grep "Valve command sent" logs/combined.log
```

## Troubleshooting

### Sensor Data Issues

1. **401 Unauthorized**: Check API key configuration
2. **404 Not Found**: Verify sensor IDs match registered sensors
3. **Connection Refused**: Ensure external-api service is running

### ROS Integration Issues

1. **Invalid Response**: Check ROS API expects the correct request format
2. **Timeout**: ROS calculations can take time, adjust timeout if needed

### Database Issues

1. **Connection Failed**: Check network connectivity and credentials
2. **Schema Not Found**: Run database initialization script
3. **Permission Denied**: Ensure user has CREATE SCHEMA permissions