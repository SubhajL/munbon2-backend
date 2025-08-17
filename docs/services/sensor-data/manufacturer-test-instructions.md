# Instructions for Manufacturer - Moisture Data Verification Test

## Issue Summary
We are receiving very limited moisture data from gateway 0003:
- Only 13 readings in 7 days
- Average gap between readings: 2 hours
- Maximum gap: 14 hours

## Our Findings
1. Endpoint is working correctly: http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture
2. Network packet capture shows NO incoming data from external sources
3. When test data is sent, it is received and stored correctly

**Note on Timestamps**: Currently timestamps are stored with a +7 hour offset due to server timezone. We use the query `time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok'` to display correct Bangkok time.

## Test Script for Manufacturer

Please run this test from your gateway location or any computer with internet access:

```bash
#!/bin/bash

# Test connectivity and send verification data
ENDPOINT="http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture"
TIMESTAMP=$(date -u '+%Y/%m/%d')
UTC_TIME=$(date -u '+%H:%M:%S')
TEST_ID=$(date +%s)

echo "=== MOISTURE ENDPOINT TEST ==="
echo "Test ID: $TEST_ID"
echo ""

# 1. Test basic connectivity
echo "Testing connectivity..."
ping -c 3 43.209.22.250

# 2. Test port 8080
echo ""
echo "Testing port 8080..."
nc -zv 43.209.22.250 8080

# 3. Send test data
echo ""
echo "Sending test data with unique ID: $TEST_ID"
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0003",
    "gateway_msg_type": "data",
    "gateway_date": "'$TIMESTAMP'",
    "gateway_utc": "'$UTC_TIME'",
    "gps_lat": "14.2333",
    "gps_lng": "99.1234",
    "gw_batt": "450",
    "test_id": "'$TEST_ID'",
    "sensor": [{
      "sensor_id": "13",
      "sensor_msg_type": "data",
      "sensor_date": "'$TIMESTAMP'",
      "sensor_utc": "'$UTC_TIME'",
      "humid_hi": "99",
      "humid_low": "99",
      "temp_hi": "99.9",
      "temp_low": "99.9",
      "amb_humid": "99",
      "amb_temp": "99.9",
      "flood": "no",
      "sensor_batt": "999"
    }]
  }'

echo ""
echo "Test complete! Please share Test ID: $TEST_ID with Munbon team"
```

## After Running the Test

Please provide us with:
1. The Test ID number
2. Screenshot of the test output
3. Confirmation of whether you see "success" response

We will then check our database for the test data with moisture values of 99%.

## Expected Gateway Behavior

If your gateway is configured correctly, it should:
1. Send data every 5-15 minutes (288-864 times per day)
2. Use gateway ID format: "0003" (with leading zeros)
3. Include valid timestamps in UTC

## Contact
If the test succeeds but regular data is still not arriving, please check:
- Gateway configuration and sending frequency
- Network/firewall settings
- Power supply to the gateway
- SIM card data balance (if using cellular)

Our endpoint is confirmed working and accessible 24/7.