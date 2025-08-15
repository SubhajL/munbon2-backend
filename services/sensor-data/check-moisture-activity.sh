#!/bin/bash

# SSH key and host
SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="43.209.22.250"

echo "=== Moisture HTTP Endpoint Activity Check ==="
echo "Time: $(date)"
echo ""

# Check if HTTP server is running
echo "1. HTTP Server Status:"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "pm2 list | grep moisture-http"
echo ""

# Check last 10 moisture data entries
echo "2. Last 10 Moisture Data Entries:"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -B2 'Received moisture' /home/ubuntu/.pm2/logs/moisture-http-out.log | tail -30 | grep -E '\[.*\].*Received moisture' | tail -10"
echo ""

# Get unique gateway IDs from today
echo "3. Active Gateways Today:"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep 'gw_id' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -o '\"gw_id\": \"[^\"]*\"' | sort | uniq -c | sort -nr"
echo ""

# Count messages per hour today
echo "4. Hourly Message Count (Last 24h):"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep 'Received moisture' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -oE '\[[0-9]{2}:' | cut -d: -f1 | tr -d '[' | sort | uniq -c"
echo ""

# Check for errors
echo "5. Recent Errors (if any):"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "tail -50 /home/ubuntu/.pm2/logs/moisture-http-error.log | grep -v 'MODULE_TYPELESS_PACKAGE_JSON' | grep -E 'ERROR|Error|error' | tail -5"
echo ""

# Show endpoint URL
echo "6. Moisture HTTP Endpoint:"
echo "   URL: http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo "   Method: POST"
echo "   Content-Type: application/json"
echo ""

# Test endpoint availability
echo "7. Endpoint Health Check:"
curl -s -o /dev/null -w "   Status: %{http_code}\n   Response Time: %{time_total}s\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"test": true}' \
  http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-m2m-moisture

echo ""
echo "=== End of Report ==="