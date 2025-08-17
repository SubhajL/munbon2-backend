#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="${EC2_HOST:-43.208.201.191}"

echo "=== MONITORING FOR GATEWAY 0003 / SENSOR 13 ==="
echo "Endpoint: http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo "Started: $(date)"
echo ""
echo "Watching for incoming data from gateway 0003..."
echo "Press Ctrl+C to stop"
echo ""

# Monitor HTTP logs for gateway 0003
ssh -i $SSH_KEY ubuntu@$EC2_HOST "tail -f /home/ubuntu/.pm2/logs/moisture-http-out.log | grep --line-buffered -E '0003|\"3\"|sensor.*13'"