#!/bin/bash

EC2_HOST="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"

echo "=== Monitoring Live Moisture Data Activity ==="
echo "Time: $(date)"
echo ""

# Send a test request with unique ID
TEST_ID="live-test-$(date +%s)"
echo "1. Sending test request with ID: $TEST_ID"
curl -X POST http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "'$TEST_ID'",
    "sensor": [{
      "sensor_id": "1",
      "humid_hi": "85",
      "humid_low": "78",
      "temp_hi": "33.5",
      "temp_low": "31.0"
    }]
  }' 2>&1

echo ""
echo "2. Waiting 2 seconds for processing..."
sleep 2

echo ""
echo "3. Checking database for all entries in last 5 minutes:"
ssh -i $SSH_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    sensor_id,
    time,
    moisture_surface_pct as surface,
    moisture_deep_pct as deep,
    CASE 
        WHEN sensor_id LIKE '%test%' THEN 'TEST'
        WHEN sensor_id LIKE '%monitor%' THEN 'MONITOR'
        ELSE 'REAL SENSOR'
    END as type
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '5 minutes'
ORDER BY time DESC;
"
EOF

echo ""
echo "4. Checking distinct sensors active in last 30 minutes:"
ssh -i $SSH_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_HOST << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    sensor_id,
    COUNT(*) as readings,
    MAX(time) as last_seen
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '30 minutes'
GROUP BY sensor_id
ORDER BY last_seen DESC;
"
EOF

echo ""
echo "5. Checking PM2 process info:"
ssh -i $SSH_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_HOST "pm2 info moisture-http | grep -E '(status|uptime|restarts|created at)'"

echo ""
echo "6. Checking for any HTTP requests in nginx logs (if available):"
ssh -i $SSH_KEY -o StrictHostKeyChecking=no ubuntu@$EC2_HOST "sudo tail -10 /var/log/nginx/access.log 2>/dev/null | grep -E '8080|moisture' || echo 'No nginx logs or no recent moisture requests'"