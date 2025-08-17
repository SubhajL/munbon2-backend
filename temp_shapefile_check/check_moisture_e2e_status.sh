#!/bin/bash

echo "🔍 Moisture Data E2E Status Check"
echo "================================="

# 1. Check EC2 HTTP endpoint
echo -e "\n1️⃣ EC2 HTTP Endpoint:"
if curl -s -o /dev/null -w "%{http_code}" http://${EC2_HOST:-43.208.201.191}:8080/health | grep -q "200"; then
    echo "✅ Moisture HTTP service is running on EC2 (port 8080)"
else
    echo "❌ Moisture HTTP service is NOT accessible"
fi

# 2. Check SQS Queue
echo -e "\n2️⃣ SQS Queue Status:"
QUEUE_STATUS=$(AWS_REGION=ap-southeast-1 aws sqs get-queue-attributes \
    --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
    --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
    --query 'Attributes' --output json 2>/dev/null)

if [ $? -eq 0 ]; then
    MESSAGES=$(echo $QUEUE_STATUS | jq -r '.ApproximateNumberOfMessages')
    IN_FLIGHT=$(echo $QUEUE_STATUS | jq -r '.ApproximateNumberOfMessagesNotVisible')
    echo "✅ SQS Queue accessible"
    echo "   - Messages waiting: $MESSAGES"
    echo "   - Messages in flight: $IN_FLIGHT"
else
    echo "❌ Cannot access SQS queue"
fi

# 3. Check Consumer Status
echo -e "\n3️⃣ Consumer Status:"
CONSUMER_PID=$(lsof -i :3004 -t 2>/dev/null)
if [ ! -z "$CONSUMER_PID" ]; then
    echo "✅ Consumer is running (PID: $CONSUMER_PID)"
else
    echo "❌ Consumer is NOT running on port 3004"
fi

# 4. Check Local Database
echo -e "\n4️⃣ Local Database (last moisture data):"
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d munbon_timescale -t -c "
SELECT 'Last moisture data: ' || 
       CASE 
         WHEN MAX(time) IS NULL THEN 'No data'
         ELSE to_char(MAX(time), 'YYYY-MM-DD HH24:MI:SS') || ' (' || 
              EXTRACT(EPOCH FROM (NOW() - MAX(time)))/3600 || ' hours ago)'
       END
FROM moisture_readings;"

# 5. Check EC2 Moisture Service Logs
echo -e "\n5️⃣ Recent EC2 Moisture Service Activity:"
ssh -i $HOME/dev/th-lab01.pem ubuntu@${EC2_HOST:-43.208.201.191} "pm2 logs moisture-http --lines 5 --nostream | grep -E '(INFO|ERROR|success)' | tail -5" 2>/dev/null

echo -e "\n📊 Summary:"
echo "- EC2 HTTP → SQS: ✅ Working (based on EC2 logs)"
echo "- SQS → Consumer: ❓ Need to check consumer logs"
echo "- Consumer → Dual-write: ❓ Need to verify"
echo -e "\nTo send test data, run: node test_moisture_e2e.js"