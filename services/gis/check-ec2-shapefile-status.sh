#!/bin/bash

echo "=== Checking Shapefile Processor Status on EC2 ==="
echo "Date: $(date)"
echo ""

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"
EC2_USER="ubuntu"

echo "1. PM2 Process Status..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP "pm2 list | grep -E 'shapefile|sqs' || echo 'No shapefile processor found'"

echo ""
echo "2. Database Status..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << 'EOF'
echo "Checking munbon_dev gis schema tables..."
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT table_name, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname IN ('gis', 'public') 
AND tablename IN ('shape_file_uploads', 'parcels', 'zones')
ORDER BY tablename;"
EOF

echo ""
echo "3. Recent Upload Records..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT upload_id, file_name, status, parcel_count, created_at 
FROM gis.shape_file_uploads 
ORDER BY created_at DESC 
LIMIT 10;" 2>/dev/null || echo "No upload records found"
EOF

echo ""
echo "4. Parcel Count..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT COUNT(*) as total_parcels FROM gis.parcels;" 2>/dev/null || echo "No parcels table"
EOF

echo ""
echo "5. Recent Processor Logs..."
ssh -i $SSH_KEY $EC2_USER@$EC2_IP "tail -20 ~/.pm2/logs/shapefile-queue-processor-out.log 2>/dev/null || echo 'No logs found'"

echo ""
echo "6. SQS Queue Status..."
# This would need AWS CLI on local machine
if command -v aws &> /dev/null; then
    QUEUE_URL="https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue"
    QUEUE_ATTRS=$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" \
        --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
        --region ap-southeast-1 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        MSG_COUNT=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessages')
        IN_FLIGHT=$(echo "$QUEUE_ATTRS" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible')
        echo "Messages in queue: $MSG_COUNT"
        echo "Messages in flight: $IN_FLIGHT"
    else
        echo "Could not check SQS queue status"
    fi
else
    echo "AWS CLI not available locally"
fi

echo ""
echo "=== Summary ==="
echo "Use this script to monitor the shapefile processor on EC2"