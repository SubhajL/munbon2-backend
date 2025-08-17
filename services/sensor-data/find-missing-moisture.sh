#!/bin/bash

echo "=== Searching for Missing Moisture Data ==="
echo ""

# Check HTTP server for recent moisture data sent after 4 PM
echo "1. Recent moisture data received at HTTP endpoint (after 16:00):"
ssh -i ~/dev/th-lab01.pem ubuntu@${EC2_HOST:-43.208.201.191} "grep -A5 'Received moisture' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -E 'INFO.*Received|time\":|gw_id' | grep -B2 -A2 '\"(16|17|18|19|20|21):' | tail -20"

echo ""
echo "2. Messages sent to SQS from HTTP server:"
ssh -i ~/dev/th-lab01.pem ubuntu@${EC2_HOST:-43.208.201.191} "grep 'Sent to SQS successfully' /home/ubuntu/.pm2/logs/moisture-http-out.log | tail -10"

echo ""
echo "3. Check if consumer is receiving moisture messages:"
echo "Checking local consumer logs..."
tail -1000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-out-13.log | grep -E "moisture|0001.*000D|0002.*001[AB]" | tail -20

echo ""
echo "4. Check for moisture processing errors:"
tail -1000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-out-13.log | grep -B5 -A5 "moisture" | grep -E "ERROR|error|Failed" | tail -10

echo ""
echo "=== End of Search ==="