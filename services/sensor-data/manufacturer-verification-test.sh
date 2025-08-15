#!/bin/bash

# Manufacturer Verification Test Script
# This script provides undeniable proof of data transmission

ENDPOINT="http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture"
TIMESTAMP=$(date -u '+%Y/%m/%d')
UTC_TIME=$(date -u '+%H:%M:%S')
UNIQUE_ID=$(date +%s)

echo "=== MANUFACTURER VERIFICATION TEST ==="
echo "Test ID: $UNIQUE_ID"
echo "Timestamp: $(date)"
echo "====================================="
echo ""

# 1. Test connectivity
echo "1. TESTING BASIC CONNECTIVITY:"
echo "=============================="
echo "Ping test:"
ping -c 3 43.209.22.250
echo ""
echo "Port 8080 connectivity:"
nc -zv 43.209.22.250 8080
echo ""

# 2. Send test data with unique identifier
echo "2. SENDING TEST DATA WITH UNIQUE ID: $UNIQUE_ID"
echo "==============================================="

# Create test payload with unique values
cat > /tmp/test-moisture-$UNIQUE_ID.json << EOF
{
  "gw_id": "0003",
  "gateway_msg_type": "data",
  "gateway_date": "$TIMESTAMP",
  "gateway_utc": "$UTC_TIME",
  "gps_lat": "14.2333",
  "gps_lng": "99.1234",
  "gw_batt": "450",
  "test_id": "$UNIQUE_ID",
  "sensor": [
    {
      "sensor_id": "13",
      "sensor_msg_type": "data",
      "sensor_date": "$TIMESTAMP",
      "sensor_utc": "$UTC_TIME",
      "humid_hi": "$((UNIQUE_ID % 100))",
      "humid_low": "$((UNIQUE_ID % 100 + 5))",
      "temp_hi": "28.5",
      "temp_low": "27.2",
      "amb_humid": "70",
      "amb_temp": "26.8",
      "flood": "no",
      "sensor_batt": "420",
      "test_marker": "TEST-$UNIQUE_ID"
    }
  ]
}
EOF

echo "Sending test data..."
echo "Request details:"
echo "- URL: $ENDPOINT"
echo "- Method: POST"
echo "- Unique moisture values: $((UNIQUE_ID % 100))% / $((UNIQUE_ID % 100 + 5))%"
echo ""

# Send with full debugging
RESPONSE=$(curl -v -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "X-Test-ID: $UNIQUE_ID" \
  -d @/tmp/test-moisture-$UNIQUE_ID.json \
  2>&1)

echo "$RESPONSE"
echo ""

# 3. Verify receipt
echo "3. VERIFICATION STEPS:"
echo "====================="
echo "Your unique test ID is: $UNIQUE_ID"
echo "Your unique moisture values are: $((UNIQUE_ID % 100))% / $((UNIQUE_ID % 100 + 5))%"
echo ""
echo "Please ask the Munbon team to check for:"
echo "1. HTTP logs for test ID: $UNIQUE_ID"
echo "2. Database records with moisture values: $((UNIQUE_ID % 100))% / $((UNIQUE_ID % 100 + 5))%"
echo "3. SQS messages with test_id: $UNIQUE_ID"
echo ""

# 4. Create continuous test
echo "4. CREATING CONTINUOUS TEST SCRIPT:"
echo "==================================="
cat > /tmp/continuous-moisture-test.sh << 'SCRIPT'
#!/bin/bash
ENDPOINT="http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture"
INTERVAL=300  # 5 minutes

echo "Starting continuous moisture data transmission test"
echo "Sending data every $INTERVAL seconds"
echo "Press Ctrl+C to stop"

while true; do
    TIMESTAMP=$(date -u '+%Y/%m/%d')
    UTC_TIME=$(date -u '+%H:%M:%S')
    TEST_ID=$(date +%s)
    
    curl -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -d "{
            \"gw_id\": \"0003\",
            \"gateway_msg_type\": \"data\",
            \"gateway_date\": \"$TIMESTAMP\",
            \"gateway_utc\": \"$UTC_TIME\",
            \"gps_lat\": \"14.2333\",
            \"gps_lng\": \"99.1234\",
            \"gw_batt\": \"450\",
            \"continuous_test\": true,
            \"test_id\": \"$TEST_ID\",
            \"sensor\": [{
                \"sensor_id\": \"13\",
                \"sensor_msg_type\": \"data\",
                \"sensor_date\": \"$TIMESTAMP\",
                \"sensor_utc\": \"$UTC_TIME\",
                \"humid_hi\": \"$(( ($(date +%s) / 60) % 50 + 20 ))\",
                \"humid_low\": \"$(( ($(date +%s) / 60) % 50 + 25 ))\",
                \"temp_hi\": \"28.5\",
                \"temp_low\": \"27.2\",
                \"amb_humid\": \"70\",
                \"amb_temp\": \"26.8\",
                \"flood\": \"no\",
                \"sensor_batt\": \"420\"
            }]
        }"
    
    echo "[$(date)] Sent test data with ID: $TEST_ID"
    sleep $INTERVAL
done
SCRIPT

chmod +x /tmp/continuous-moisture-test.sh
echo "Continuous test script created at: /tmp/continuous-moisture-test.sh"
echo "Run it with: /tmp/continuous-moisture-test.sh"
echo ""

# 5. Network path trace
echo "5. NETWORK PATH ANALYSIS:"
echo "========================"
echo "Traceroute to endpoint:"
traceroute -n -p 8080 43.209.22.250 2>/dev/null || echo "Traceroute not available"
echo ""

# 6. Certificate test (if HTTPS)
echo "6. TLS/SSL TEST (if applicable):"
echo "================================"
timeout 5 openssl s_client -connect 43.209.22.250:8080 </dev/null 2>/dev/null || echo "No TLS on port 8080 (expected for HTTP)"

echo ""
echo "=== TEST COMPLETE ==="
echo "Test ID for reference: $UNIQUE_ID"
echo "Time: $(date)"
echo ""
echo "Share this test ID with Munbon team for verification"