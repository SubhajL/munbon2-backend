#!/bin/bash

echo "=== Sensor Data Service Status Check ==="
echo

echo "1. Consumer Service:"
if curl -s http://localhost:3002/health > /dev/null 2>&1; then
    echo "   ✅ Consumer is running at http://localhost:3002"
else
    echo "   ⚠️  Consumer health check failed (but service may still be running)"
fi

echo
echo "2. Database Tables:"
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "\dt" 2>/dev/null | grep -E "(sensor_|moisture_|water_)" | sed 's/^/   /'

echo
echo "3. Recent Sensor Data (last 24 hours):"
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -t -c "
SELECT 
    'sensor_readings' as table_name, 
    COUNT(*) as count 
FROM sensor_readings 
WHERE time > NOW() - INTERVAL '24 hours'
UNION ALL
SELECT 
    'water_level_readings', 
    COUNT(*) 
FROM water_level_readings 
WHERE time > NOW() - INTERVAL '24 hours'
UNION ALL
SELECT 
    'moisture_readings', 
    COUNT(*) 
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '24 hours';" | sed 's/^/   /'

echo
echo "4. AWS Configuration:"
echo "   SQS Queue: ${SQS_QUEUE_URL:-Not configured}"
echo "   AWS Region: ${AWS_REGION:-Not configured}"

echo
echo "5. To Send Test Data:"
echo "   - Water Level: npm run test:water-level"
echo "   - Moisture: npm run test:moisture"
echo "   - Or use curl to POST to your AWS API Gateway endpoints"

echo
echo "6. Check Consumer Logs:"
echo "   tail -f consumer.log"

echo
echo "7. Dashboard:"
echo "   Open http://localhost:3002 in your browser"