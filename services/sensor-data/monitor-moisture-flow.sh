#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="${EC2_HOST:-43.208.201.191}"

echo "=== Real-time Moisture Data Flow Monitor ==="
echo "Time: $(date)"
echo ""

# Function to show section
show_section() {
    echo -e "\033[1;34m$1\033[0m"
    echo "=================================="
}

while true; do
    clear
    echo "=== Real-time Moisture Data Flow Monitor ==="
    echo "Time: $(date)"
    echo ""
    
    # 1. HTTP Endpoint Status
    show_section "1. HTTP Endpoint Status"
    ssh -i $SSH_KEY ubuntu@$EC2_HOST "pm2 list | grep moisture-http | awk '{print \"Status: \" \$10 \", Uptime: \" \$7, \"Restarts: \" \$8}'"
    echo ""
    
    # 2. Empty Payload Statistics
    show_section "2. Empty Payload Rejections"
    curl -s http://$EC2_HOST:8080/api/stats/empty-payloads 2>/dev/null | jq -r '.sources[] | "IP: \(.ip) - Count: \(.count) - Last: \(.lastSeen)"' | head -5
    echo ""
    
    # 3. Recent Valid Data
    show_section "3. Recent Valid Moisture Data (Last 5 min)"
    ssh -i $SSH_KEY ubuntu@$EC2_HOST "tail -500 /home/ubuntu/.pm2/logs/moisture-http-out.log | grep 'Received valid moisture' | tail -5 | grep -o 'gw_id.*' | cut -d',' -f1-3"
    echo ""
    
    # 4. SQS Queue Status
    show_section "4. SQS Queue Status"
    aws sqs get-queue-attributes \
        --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
        --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
        2>/dev/null | jq -r '.Attributes | "Messages: \(.ApproximateNumberOfMessages), In-Flight: \(.ApproximateNumberOfMessagesNotVisible)"'
    echo ""
    
    # 5. Consumer Processing
    show_section "5. Recent Consumer Activity"
    tail -100 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-out-13.log | grep -E "Processing.*moisture|Saved moisture" | tail -3
    echo ""
    
    # 6. Database Latest Entry
    show_section "6. Latest Moisture in Database"
    PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d sensor_data -t -c "
    SELECT sensor_id, recorded_at, surface_moisture, deep_moisture 
    FROM moisture_readings 
    ORDER BY recorded_at DESC 
    LIMIT 3;" 2>/dev/null | grep -v "^$"
    
    echo ""
    echo "Press Ctrl+C to exit. Refreshing in 10 seconds..."
    sleep 10
done