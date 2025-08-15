#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="43.209.22.250"

echo "=== MOISTURE DATA PATTERN ANALYSIS ==="
echo ""

# 1. Check empty payloads pattern
echo "1. EMPTY PAYLOAD ANALYSIS:"
echo "=========================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep 'Empty payload detected' /home/ubuntu/.pm2/logs/moisture-http-out.log | head -5"
echo "..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep 'Empty payload detected' /home/ubuntu/.pm2/logs/moisture-http-out.log | tail -5"
echo ""
ssh -i $SSH_KEY ubuntu@$EC2_HOST "echo 'Total empty payloads:' && grep -c 'Empty payload detected' /home/ubuntu/.pm2/logs/moisture-http-out.log"
echo ""

# 2. Check timing of all requests
echo "2. REQUEST TIMING PATTERN (All requests including empty):"
echo "========================================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'Received moisture data|Empty payload detected' /home/ubuntu/.pm2/logs/moisture-http-out.log | awk '{print \$1}' | head -20"
echo "..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'Received moisture data|Empty payload detected' /home/ubuntu/.pm2/logs/moisture-http-out.log | awk '{print \$1}' | tail -20"
echo ""

# 3. Calculate time between requests
echo "3. TIME BETWEEN REQUESTS:"
echo "========================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'Received moisture data|Empty payload detected' /home/ubuntu/.pm2/logs/moisture-http-out.log | awk '{print substr(\$1,2,8)}' > /tmp/times.txt && \
awk 'NR>1{
  split(prev,p,\":\"); 
  split(\$0,c,\":\"); 
  diff = (c[1]*3600 + c[2]*60 + c[3]) - (p[1]*3600 + p[2]*60 + p[3]); 
  if(diff<0) diff+=86400; 
  print diff \" seconds between \" prev \" and \" \$0
} 
{prev=\$0}' /tmp/times.txt | sort -n | uniq -c | sort -rn | head -10"
echo ""

# 4. Check actual data content
echo "4. ACTUAL SENSOR DATA RECEIVED:"
echo "==============================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -A5 'sensor_id' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -E 'sensor_id|humid_hi|humid_low' | tail -20"
echo ""

# 5. Database actual frequency check
echo "5. DATABASE - ACTUAL DATA FREQUENCY:"
echo "===================================="
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    DATE(time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok') as date_bangkok,
    EXTRACT(HOUR FROM time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok') as hour_bangkok,
    COUNT(*) as readings,
    COUNT(DISTINCT sensor_id) as sensors
FROM moisture_readings
WHERE time > NOW() - INTERVAL '3 days'
GROUP BY DATE(time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok'), 
         EXTRACT(HOUR FROM time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok')
ORDER BY date_bangkok DESC, hour_bangkok DESC
LIMIT 30;"
echo ""

# 6. Check for manufacturer's claim timeframe
echo "6. SEARCHING FOR CONTINUOUS DATA PATTERN:"
echo "========================================="
echo "If manufacturer sends every X minutes, we should see a pattern..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
WITH sensor_data AS (
    SELECT 
        sensor_id,
        time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
        LAG(time) OVER (PARTITION BY sensor_id ORDER BY time) as prev_time,
        EXTRACT(EPOCH FROM (time - LAG(time) OVER (PARTITION BY sensor_id ORDER BY time)))/60 as minutes_gap
    FROM moisture_readings
    WHERE sensor_id = '0003-13'
    AND time > NOW() - INTERVAL '7 days'
)
SELECT 
    CASE 
        WHEN minutes_gap < 5 THEN '< 5 min'
        WHEN minutes_gap < 15 THEN '5-15 min'
        WHEN minutes_gap < 30 THEN '15-30 min'
        WHEN minutes_gap < 60 THEN '30-60 min'
        WHEN minutes_gap < 120 THEN '1-2 hours'
        ELSE '> 2 hours'
    END as gap_range,
    COUNT(*) as frequency
FROM sensor_data
WHERE minutes_gap IS NOT NULL
GROUP BY gap_range
ORDER BY 
    CASE gap_range
        WHEN '< 5 min' THEN 1
        WHEN '5-15 min' THEN 2
        WHEN '15-30 min' THEN 3
        WHEN '30-60 min' THEN 4
        WHEN '1-2 hours' THEN 5
        ELSE 6
    END;"

echo ""
echo "=== END OF PATTERN ANALYSIS ===="