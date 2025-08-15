# Moisture Data Investigation Report
Date: August 2, 2025

## Executive Summary
The manufacturer claims continuous moisture data transmission, but our investigation shows **extremely sporadic data receipt** with only **13 total readings over 7 days** from gateway 0003, sensor 13.

## Key Findings

### 1. Data Frequency Analysis
- **Total readings in last 7 days**: 13
- **Average gap between readings**: 118.71 minutes (almost 2 hours)
- **Maximum gap**: 854.60 minutes (over 14 hours)
- **Minimum gap**: 0 minutes (duplicate timestamps)

### 2. HTTP Endpoint Activity (Last 24 hours)
- **Total moisture requests received**: 37
- **Requests by hour**:
  - 04:00 - 1 request
  - 08:00 - 3 requests  
  - 09:00 - 25 requests (burst of activity)
  - 10:00 - 6 requests
  - 11:00 - 1 request
  - 16:00 - 1 request

### 3. Gateway ID Inconsistency
The same gateway sends data with different ID formats:
- "gw_id": "3" (9 times)
- "gw_id": "0003" (4 times)
- "gw_id": "003" (1 time)

### 4. Data Receipt Pattern
```
Last readings from gateway 0003-13:
2025-08-02 21:14:30 - moisture: 35%/38%
2025-08-02 17:03:09 - moisture: 16%/16%
2025-08-02 17:02:02 - moisture: 20%/18%
2025-08-02 14:54:30 - moisture: 22%/28%
2025-08-02 14:17:45 - moisture: 40%/42%
```

### 5. System Status
- **HTTP Server**: Online for 35 hours, 4 restarts
- **SQS Queue**: Empty (no stuck messages)
- **Consumer**: Processing successfully when data arrives
- **Database**: Storing data correctly when received

## Conclusion
The system is working correctly and storing all data it receives. However, we are NOT receiving continuous data as claimed by the manufacturer. The data arrives in sporadic bursts with long gaps between transmissions.

## Recommendations for Manufacturer
1. **Verify transmission frequency**: Check if the gateway is actually sending data continuously
2. **Check network connectivity**: Ensure stable connection from gateway to our endpoint
3. **Standardize gateway ID**: Always use "0003" format (4 digits with leading zeros)
4. **Enable logging**: Add transmission logs on the gateway side to verify sent data
5. **Test direct connection**: Try sending data directly to our endpoint to rule out network issues

## Our Endpoint Details
- **URL**: http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture
- **Method**: POST
- **Content-Type**: application/json
- **Status**: Online and receiving data successfully

## Test Command
Manufacturer can test the endpoint with:
```bash
curl -X POST http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0003",
    "gateway_msg_type": "data",
    "gateway_date": "2025/08/02",
    "gateway_utc": "04:00:00",
    "gps_lat": "14.2333",
    "gps_lng": "99.1234",
    "gw_batt": "450",
    "sensor": [{
      "sensor_id": "13",
      "sensor_msg_type": "data",
      "sensor_date": "2025/08/02",
      "sensor_utc": "04:00:00",
      "humid_hi": "25",
      "humid_low": "30",
      "temp_hi": "28.5",
      "temp_low": "27.2",
      "amb_humid": "70",
      "amb_temp": "26.8",
      "flood": "no",
      "sensor_batt": "420"
    }]
  }'
```