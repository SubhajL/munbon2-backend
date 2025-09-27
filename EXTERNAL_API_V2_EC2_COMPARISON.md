# External API V2.0 - EC2 Implementation vs AWS Lambda

## Overview

The EC2 implementation provides the **exact same API interface** as the production AWS Lambda version, with only the base URL being different.

## Comparison

| Feature | AWS Lambda (Production) | EC2 Implementation |
|---------|------------------------|-------------------|
| **Base URL** | `https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1` | `http://43.208.201.191:8080/api/v1` |
| **Authentication** | X-API-Key header | X-API-Key header (same) |
| **Valid API Keys** | rid-ms-prod-key1, tmd-weather-key2, university-key3 | Same keys |
| **Endpoints** | All /public/* endpoints | Same endpoints |
| **Response Format** | JSON with Buddhist dates | Identical format |
| **Date Format** | DD/MM/YYYY (Buddhist) | Same format |
| **Error Responses** | 401, 400, 500 | Same error codes |

## Endpoints - Identical Structure

### Water Level Data
- `GET /public/water-levels/latest`
- `GET /public/water-levels/timeseries?date=DD/MM/YYYY`
- `GET /public/water-levels/statistics?date=DD/MM/YYYY`

### Moisture Data
- `GET /public/moisture/latest`
- `GET /public/moisture/timeseries?date=DD/MM/YYYY`
- `GET /public/moisture/statistics?date=DD/MM/YYYY`

### AOS Meteorological Data
- `GET /public/aos/latest`
- `GET /public/aos/timeseries?date=DD/MM/YYYY`
- `GET /public/aos/statistics?date=DD/MM/YYYY`

## Example Requests

### AWS Lambda (Original)
```bash
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest
```

### EC2 Implementation (New)
```bash
curl -H "X-API-Key: rid-ms-prod-key1" \
  http://43.208.201.191:8080/api/v1/public/water-levels/latest
```

## Response Format - Identical

Both implementations return the exact same response structure:

```json
{
  "data_type": "water_level",
  "request_time": "2025-06-10T15:30:00Z",
  "request_time_buddhist": "10/06/2568",
  "sensor_count": 6,
  "sensors": [
    {
      "sensor_id": "AWD-B75A",
      "sensor_name": "AWD-B75A",
      "location": {
        "latitude": 13.7563,
        "longitude": 100.5234
      },
      "zone": "Zone1",
      "latest_reading": {
        "timestamp": "2025-06-10T15:00:00Z",
        "timestamp_buddhist": "10/06/2568",
        "water_level_m": 12.5,
        "flow_rate_m3s": 0,
        "quality": 100
      }
    }
  ]
}
```

## Technical Implementation

### AWS Lambda Architecture
1. API Gateway → Lambda Function
2. Lambda validates API key
3. Lambda proxies to internal API
4. Internal API queries databases

### EC2 Architecture (Simplified)
1. Direct Express.js server on EC2
2. Server validates API key
3. Server queries database directly
4. Returns formatted response

## Benefits of EC2 Implementation

1. **Lower Latency**: Direct database connection
2. **No Cold Starts**: Always warm
3. **Cost Effective**: No Lambda/API Gateway charges
4. **Easier Debugging**: Direct access to logs
5. **Same API Contract**: No client changes needed

## Deployment

```bash
# Deploy to EC2
./deploy-external-api-v2-ec2.sh

# Test all endpoints
./test-external-api-v2-ec2.sh
```

## Migration Guide

To migrate from AWS Lambda to EC2:

1. Change base URL:
   - From: `https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1`
   - To: `http://43.208.201.191:8080/api/v1`

2. Keep everything else the same:
   - Same API keys
   - Same headers
   - Same endpoints
   - Same response format

That's it! The EC2 implementation is a drop-in replacement.