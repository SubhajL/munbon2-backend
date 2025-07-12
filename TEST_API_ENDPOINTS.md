# Test Munbon API Endpoints

Run these commands in your terminal to test the API endpoints:

## 1. Test SHAPE File Upload

```bash
# Create test file
echo "test shapefile data" > test.txt
zip test.zip test.txt

# Upload file
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload \
  -H "Authorization: Bearer munbon-ridms-shape" \
  -F "file=@test.zip" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=weekly" \
  -F "zone=TestZone" \
  -F "description=Test upload" \
  -w "\nHTTP Status: %{http_code}\n"

# Cleanup
rm test.txt test.zip
```

## 2. Test Sensor Telemetry Endpoints

### Water Level Sensor
```bash
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "WL001",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "waterLevel": 5.5,
    "flowRate": 2.3,
    "temperature": 28.5
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

### Moisture Sensor (Confirmed Working)
```bash
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_id": "00001",
    "msg_type": "interval",
    "date": "2025/06/03",
    "time": "10:30:00",
    "latitude": "13.12345",
    "longitude": "100.54621",
    "gw_batt": "372",
    "sensor": [
      {
        "sensor_id": "00001",
        "flood": "no",
        "amb_humid": "60",
        "amb_temp": "40.50",
        "humid_hi": "50",
        "temp_hi": "25.50",
        "humid_low": "72",
        "temp_low": "25.00",
        "sensor_batt": "395"
      }
    ]
  }' \
  -w "\nHTTP Status: %{http_code}\n"
```

## 3. Test Attributes Endpoints

```bash
# Water level attributes
curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/attributes

# Moisture attributes
curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/attributes

# SHAPE file attributes
curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridms-shape/attributes
```

## 4. Check for Data APIs

These endpoints might return 404 if not deployed:

```bash
# Public APIs (may require API key)
curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/public/water-levels/latest -H "x-api-key: test"

curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/public/moisture/latest -H "x-api-key: test"

# Internal APIs
curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/sensors/active

curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/water-levels

curl https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/moisture
```

## Expected Results

1. **SHAPE File Upload**: Should return 200 with uploadId if working, or 403/401 for auth errors
2. **Moisture Telemetry**: Should return 200 (confirmed working)
3. **Water Level Telemetry**: Should return 200 if deployed
4. **Attributes**: Should return JSON configuration data
5. **Data APIs**: May return 404 if not deployed yet