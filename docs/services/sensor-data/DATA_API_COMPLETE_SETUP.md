# Data API Complete Setup - Munbon Sensor Data

## Architecture Overview

The data API uses a **Lambda Proxy Architecture** to expose local TimescaleDB and MSSQL data through AWS Lambda:

```
[External Clients] → [AWS Lambda + API Gateway] → [Cloudflare Tunnel] → [Local Unified API] → [TimescaleDB/MSSQL]
```

## Components

### 1. Local Unified API (Running on Port 3000)
- **Location**: `services/sensor-data/src/unified-api-v2.js`
- **Process ID**: 59833
- **Internal API Key**: `munbon-internal-f3b89263126548`
- **Features**:
  - Connects to TimescaleDB on port 5433
  - Buddhist calendar conversion (BE = CE + 543)
  - Maps TimescaleDB schema to external API format

### 2. Cloudflare Tunnel
- **Tunnel Name**: munbon-api
- **Tunnel ID**: f3b89263-1265-4843-b08c-5391e73e8c75
- **Public URL**: https://munbon-api-proxy.beautifyai.io
- **Status**: ✅ Active and permanent
- **Process ID**: 55818

### 3. AWS Lambda Functions (Proxy)
- **API Gateway ID**: 5e3l647kpd
- **Region**: ap-southeast-1 (Singapore)
- **Stage**: prod
- **Functions**: 9 Lambda functions for different endpoints

## Public API Endpoints

All endpoints require `X-API-Key` header with one of these valid keys:
- `rid-ms-prod-key1`
- `tmd-weather-key2`
- `university-key3`

### Water Level Endpoints
```bash
# Latest readings
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest

# Time series data (Buddhist calendar date required)
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/timeseries?date=30/06/2568

# Statistics
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/statistics?date=30/06/2568
```

### Moisture Endpoints
```bash
# Latest readings
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest

# Time series data
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/timeseries?date=30/06/2568

# Statistics
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/statistics?date=30/06/2568
```

### AOS/Weather Endpoints
```bash
# Latest readings
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest

# Time series data
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/timeseries?date=30/06/2568

# Statistics
GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/statistics?date=30/06/2568
```

## Testing Examples

### Test with valid API key:
```bash
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest | jq
```

### Test with invalid API key (should return 401):
```bash
curl -H "X-API-Key: invalid-key" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest
```

## Response Format

All responses follow this format:
```json
{
  "data_type": "moisture",
  "request_time": "2025-06-30T02:45:35.165Z",
  "request_time_buddhist": "30/06/2568",
  "sensor_count": 1,
  "sensors": [
    {
      "sensor_id": "00001-00001",
      "sensor_name": "00001-00001",
      "location": {
        "latitude": 13.7563,
        "longitude": 100.5018
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-06-30T02:00:00.000Z",
        "timestamp_buddhist": "30/06/2568",
        "moisture_percentage": 65.5,
        "temperature_celsius": 28.3,
        "quality": 98
      }
    }
  ]
}
```

## Management Commands

### Check services status:
```bash
# Check unified API
ps aux | grep unified-api-v2

# Check tunnel
ps aux | grep cloudflared

# Check logs
tail -f unified-api-v2.log
tail -f ~/.cloudflared/tunnel.log
```

### Restart services:
```bash
# Restart unified API
kill 59833
nohup node src/unified-api-v2.js > unified-api-v2.log 2>&1 &

# Restart tunnel
kill 55818
cd ~/.cloudflared && nohup cloudflared tunnel run munbon-api > tunnel.log 2>&1 &
```

### Deploy Lambda updates:
```bash
cd services/sensor-data/deployments/aws-lambda
serverless deploy --config serverless-data-api.yml --stage prod
```

## Database Information

### TimescaleDB (Port 5433)
- Container: munbon-timescaledb
- Database: sensor_data
- Tables:
  - `sensor_registry` - Sensor metadata
  - `water_level_readings` - Water level data
  - `moisture_readings` - Moisture sensor data
  - `sensor_readings` - General sensor data

### Current Data
- **Moisture sensors**: 1 active (00001-00001)
- **Water level sensors**: 0 (no data yet)
- **Weather stations**: 0 (no data yet)

## Cost Summary
- **AWS Lambda**: ~$0 (free tier covers millions of requests)
- **API Gateway**: ~$0 (free tier covers 1M requests/month)
- **Cloudflare Tunnel**: $0 (free forever)
- **Total monthly cost**: $0

## Security Notes
1. Internal API key protects tunnel-to-API communication
2. External API keys control public access
3. Lambda functions only proxy requests, no data storage
4. All databases remain local and secure