# Quick Start Guide - Sensor Data Service

## Prerequisites

1. AWS Account with access keys configured
2. Node.js 18+ installed
3. Docker running (for TimescaleDB)

## Step 1: Deploy AWS Lambda Functions

```bash
cd services/sensor-data/deployments/aws-lambda

# Configure AWS credentials (already set in .env)
# Update TimescaleDB connection details in .env

# Deploy to AWS
./deploy.sh

# Note the API Gateway URL from output
# Example: https://abc123.execute-api.ap-southeast-1.amazonaws.com/dev
```

## Step 2: Update SQS Queue URL

After deployment, update the SQS Queue URL in your local `.env`:

```bash
cd services/sensor-data
cp .env.example .env

# Edit .env and add the SQS_QUEUE_URL from AWS deployment output
```

## Step 3: Start TimescaleDB

```bash
# From project root
docker-compose up -d timescaledb
```

## Step 4: Run Local Consumer

```bash
cd services/sensor-data
npm install
npm run consumer:dev
```

Open http://localhost:3002 to see the dashboard

## Step 5: Test with Sample Data

### Test Water Level Sensor

```bash
# Replace API_URL with your actual API Gateway URL
API_URL="https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/dev"

curl -X POST $API_URL/api/v1/munbon-ridr-water-level/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "deviceID": "test-water-001",
    "macAddress": "1A2B3C4D5E6F",
    "latitude": 13.7563,
    "longitude": 100.5018,
    "RSSI": -67,
    "voltage": 420,
    "level": 15,
    "timestamp": '$(date +%s000)'
  }'
```

### Test Moisture Sensor

```bash
curl -X POST $API_URL/api/v1/munbon-m2m-moisture/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "gateway_id": "00001",
    "msg_type": "interval",
    "date": "'$(date +%Y/%m/%d)'",
    "time": "'$(date +%H:%M:%S)'",
    "latitude": "13.12345",
    "longitude": "100.54621",
    "gw_batt": "372",
    "sensor": [
      {
        "sensor_id": "00001",
        "flood": "no",
        "amb_humid": "60",
        "amb_temp": "32.5",
        "humid_hi": "45",
        "temp_hi": "28.5",
        "humid_low": "65",
        "temp_low": "26.0",
        "sensor_batt": "395"
      }
    ]
  }'
```

## Step 6: Run Main Sensor Service (Optional)

```bash
# In another terminal
cd services/sensor-data
npm run dev
```

This starts:
- HTTP API on port 3001
- MQTT interface (mock) on port 1883
- WebSocket on port 8083

## Verify Everything is Working

1. Check AWS Lambda logs:
   ```bash
   cd deployments/aws-lambda
   npx serverless logs -f telemetry --tail
   ```

2. Check consumer dashboard: http://localhost:3002
   - You should see sensor data appearing in real-time

3. Check TimescaleDB:
   ```bash
   docker exec -it munbon_timescale psql -U postgres -d munbon_timescale
   
   # List tables
   \dt
   
   # Check sensor readings
   SELECT * FROM sensor_readings ORDER BY time DESC LIMIT 10;
   ```

## Token Reference

Use these tokens when sending data:

- `munbon-ridr-water-level` - RID-R water level sensors in Munbon
- `munbon-m2m-moisture` - M2M moisture sensors in Munbon
- `munbon-test-devices` - Testing and development

## Troubleshooting

1. **Lambda timeout**: Check CloudWatch logs in AWS Console
2. **SQS not receiving**: Verify SQS_QUEUE_URL in Lambda environment
3. **Consumer not getting data**: Check AWS credentials in .env
4. **TimescaleDB connection failed**: Verify database is running with `docker ps`

## Next Steps

1. Deploy actual MQTT broker (Mosquitto/HiveMQ)
2. Configure IoT devices with tokens
3. Set up monitoring and alerts
4. Deploy to Kubernetes for production