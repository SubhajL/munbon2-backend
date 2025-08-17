# Munbon API Status Report

## Current Status (2025-06-29)

### ✅ Working Endpoints

#### 1. Sensor Data Ingestion
- **Base URL**: `https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev`

| Endpoint | Token | Status | Purpose |
|----------|-------|--------|---------|
| POST `/api/v1/munbon-ridr-water-level/telemetry` | Built into URL | ✅ Working | Water level data |
| POST `/api/v1/munbon-m2m-moisture/telemetry` | Built into URL | ✅ Working | Moisture sensor data |
| GET `/api/v1/munbon-ridr-water-level/attributes` | Built into URL | ✅ Working | Get config |
| GET `/api/v1/munbon-m2m-moisture/attributes` | Built into URL | ✅ Working | Get config |

#### 2. Example Working Request
```bash
# Moisture sensor (confirmed working)
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_id": "00001",
    "msg_type": "interval",
    "date": "2025/06/03",
    "time": "10:30:00",
    "sensor": [{
      "sensor_id": "00001",
      "humid_hi": "50",
      "temp_hi": "25.50"
    }]
  }'
```

### ❌ Issues to Fix

#### 1. SHAPE File Upload
- **Endpoint**: POST `/api/v1/rid-ms/upload`
- **Issue**: Authorization header format error
- **Token**: `munbon-ridms-shape` is configured but handler expects different format
- **Solution**: The fileUpload function might not be deployed or has auth issues

#### 2. SHAPE Token Not Recognized
- GET `/api/v1/munbon-ridms-shape/attributes` returns "Invalid token"
- Token is in serverless.yml but not in deployed Lambda environment

#### 3. Data APIs Not Deployed
All these endpoints return "Missing Authentication Token":
- `/api/v1/public/water-levels/latest`
- `/api/v1/public/moisture/latest`
- `/api/v1/public/aos/latest`
- `/api/v1/sensors/active`
- `/api/v1/water-levels`
- `/api/v1/moisture`

### 📋 Next Steps

1. **Check if fileUpload function is deployed**:
   - Look for `/api/v1/rid-ms/upload` in API Gateway console
   - Verify the handler code is correct

2. **Deploy Data APIs**:
   - These need to be deployed from sensor-data service
   - Check if serverless-data-api.yml needs to be deployed

3. **Fix SHAPE token**:
   - Redeploy with updated VALID_TOKENS environment variable
   - Or use existing telemetry endpoint for SHAPE data

### 🔧 Quick Fix Options

#### Option 1: Use Telemetry Endpoint for SHAPE Files
Since telemetry endpoints work, you could send SHAPE file info via:
```bash
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridms-shape/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "type": "shape-file",
    "uploadId": "123",
    "fileName": "zone1.zip",
    "s3Location": "s3://bucket/path"
  }'
```

#### Option 2: Redeploy with Fixes
```bash
cd services/sensor-data/deployments/aws-lambda
serverless deploy function -f fileUpload
```

#### Option 3: Deploy Data APIs
```bash
cd services/sensor-data/deployments/aws-lambda
serverless deploy --config serverless-data-api.yml
```