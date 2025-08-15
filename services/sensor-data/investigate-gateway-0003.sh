#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="43.209.22.250"

echo "=== INVESTIGATING GATEWAY 0003 SENSOR 13 DATA ==="
echo "Time: $(date)"
echo ""

# 1. Check HTTP logs for gateway 0003
echo "1. CHECKING HTTP ENDPOINT FOR GATEWAY 0003:"
echo "==========================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -i '0003' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -v 'empty' | tail -50" || echo "SSH connection failed"
echo ""

# 2. Check for sensor 13 specifically
echo "2. CHECKING FOR SENSOR 13 DATA:"
echo "==============================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'sensor_id.*13|\"13\"' /home/ubuntu/.pm2/logs/moisture-http-out.log | tail -20" || echo "SSH connection failed"
echo ""

# 3. Check database for gateway 0003
echo "3. DATABASE CHECK FOR GATEWAY 0003:"
echo "==================================="
docker exec munbon-timescaledb psql -U postgres -d sensor_data -c "
SELECT sensor_id, time AT TIME ZONE 'Asia/Bangkok' as local_time, 
       moisture_surface_pct, moisture_deep_pct 
FROM moisture_readings 
WHERE sensor_id LIKE '%0003%' OR sensor_id LIKE '%-13'
ORDER BY time DESC;"

echo ""
# 4. Check sensor_readings table
echo "4. SENSOR_READINGS TABLE CHECK:"
echo "==============================="
docker exec munbon-timescaledb psql -U postgres -d sensor_data -c "
SELECT sensor_id, time AT TIME ZONE 'Asia/Bangkok' as local_time,
       value->>'gw_id' as gateway,
       value->>'sensor' as sensor_data
FROM sensor_readings 
WHERE sensor_type = 'moisture' 
  AND (sensor_id LIKE '%0003%' OR value->>'gw_id' = '0003')
ORDER BY time DESC
LIMIT 10;"

echo ""
# 5. Check consumer logs for gateway 0003
echo "5. CONSUMER LOGS FOR GATEWAY 0003:"
echo "=================================="
tail -2000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-out-*.log | grep -E "0003|gateway.*0003" | tail -20

echo ""
# 6. Check for any errors related to 0003
echo "6. ERRORS RELATED TO GATEWAY 0003:"
echo "=================================="
tail -1000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-error-*.log | grep -E "0003|sensor.*13" | tail -10

echo ""
# 7. Check HTTP logs more broadly
echo "7. BROADER HTTP LOG SEARCH (hex variants):"
echo "=========================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'gw_id.*(0003|03)' /home/ubuntu/.pm2/logs/moisture-http-out.log | tail -20" || echo "SSH connection failed"

echo ""
echo "=== END OF INVESTIGATION ==="