#!/bin/bash

# SSH key and host
SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="${EC2_HOST:-43.208.201.191}"

echo "=== Live Moisture Data Monitor ==="
echo "Watching for incoming moisture data at http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo "Press Ctrl+C to stop"
echo ""

# Follow the logs in real-time, filtering for moisture data
ssh -i $SSH_KEY ubuntu@$EC2_HOST "tail -f /home/ubuntu/.pm2/logs/moisture-http-out.log | grep --line-buffered -A20 'Received moisture'"