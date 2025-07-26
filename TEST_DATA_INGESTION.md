# Data Ingestion Test Guide

## 1. Water Level Sensor Test

### Endpoint:
```
https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry
```

### Test Command:
```bash
curl -X POST https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "deviceID": "WL-TEST-001",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "latitude": 13.756331,
    "longitude": 100.501765,
    "RSSI": -70,
    "voltage": 370,
    "level": 25,
    "timestamp": 1704067200000
  }'
```

### Expected Response:
```json
{
  "status": "success",
  "message": "Telemetry received",
  "timestamp": "2024-01-26T..."
}
```

## 2. Moisture Sensor Test

### Endpoint:
```
https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry
```

### Test Command:
```bash
curl -X POST https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "gateway_id": "GW-TEST-001",
    "msg_type": "sensor_data",
    "date": "2024-01-26",
    "time": "14:30:00",
    "latitude": "13.756331",
    "longitude": "100.501765",
    "gw_batt": "85",
    "sensor": [{
      "sensor_id": "MS-001",
      "flood": "0",
      "amb_humid": "65",
      "amb_temp": "28",
      "humid_hi": "45",
      "temp_hi": "26",
      "humid_low": "55",
      "temp_low": "24",
      "sensor_batt": "90"
    }]
  }'
```

### Expected Response:
```json
{
  "status": "success",
  "message": "Telemetry received",
  "timestamp": "2024-01-26T..."
}
```

## 3. Verify Data Flow

### Step 1: Check SQS Queue (AWS Console)
Go to: https://console.aws.amazon.com/sqs/v2/home?region=ap-southeast-1#/queues
- Queue: `munbon-sensor-ingestion-dev-queue`
- Look for "Messages Available" count

### Step 2: Check Consumer Dashboard
```
http://43.209.12.182:3004
```
- Should show real-time sensor data
- Shows message processing statistics

### Step 3: Check Database Directly
SSH to EC2 and run:
```bash
# Connect to PostgreSQL
docker exec -it munbon-postgres psql -U postgres -d sensor_data

# Check water level data
SELECT * FROM water_level_readings ORDER BY time DESC LIMIT 5;

# Check moisture data  
SELECT * FROM moisture_readings ORDER BY time DESC LIMIT 5;

# Exit
\q
```

## 4. Test External API (Data Exposure)

### Get Latest Water Level Data:
```bash
curl -X GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/water-level/latest \
  -H 'X-API-Key: rid-ms-prod-1234567890abcdef'
```

### Get Water Level by Device:
```bash
curl -X GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/water-level/device/WL-TEST-001 \
  -H 'X-API-Key: rid-ms-prod-1234567890abcdef'
```

### Get Moisture Data:
```bash
curl -X GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/moisture/latest \
  -H 'X-API-Key: rid-ms-prod-1234567890abcdef'
```

## 5. Troubleshooting

### If Lambda Returns Error:
1. Check CloudWatch Logs:
   - Go to: https://console.aws.amazon.com/cloudwatch/home?region=ap-southeast-1#logsV2:log-groups
   - Look for `/aws/lambda/munbon-sensor-ingestion-dev-telemetry`

2. Common Issues:
   - Invalid token: Check the token in URL path
   - Database connection error: Lambda can't reach EC2
   - SQS permission error: Check IAM roles

### If Data Not Appearing in Dashboard:
1. Check if consumer is running:
   ```bash
   docker-compose -f docker-compose.ec2-consolidated.yml ps
   ```

2. Check consumer logs:
   ```bash
   docker-compose -f docker-compose.ec2-consolidated.yml logs -f sensor-data-consumer
   ```

### If External API Returns No Data:
1. Verify Lambda environment variables were updated
2. Check if data exists in database first
3. Check API key is correct

## Summary of Endpoints:

| Purpose | Endpoint | Method |
|---------|----------|---------|
| Send Water Level Data | https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry | POST |
| Send Moisture Data | https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry | POST |
| Get Water Level Data | https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/water-level/latest | GET |
| Get Moisture Data | https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/moisture/latest | GET |
| Consumer Dashboard | http://43.209.12.182:3004 | Browser |