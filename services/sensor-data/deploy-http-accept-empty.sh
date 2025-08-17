#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="${EC2_HOST:-43.208.201.191}"
LOCAL_FILE="patches/simple-http-server-accept-empty.ts"
REMOTE_FILE="/home/ubuntu/app/moisture-http-server/src/simple-http-server.ts"

echo "=== Deploying HTTP Server Update (Accept Empty Payloads) ==="
echo ""

# Backup current file
echo "1. Creating backup of current HTTP server..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "cp $REMOTE_FILE ${REMOTE_FILE}.backup.accept-empty.$(date +%Y%m%d_%H%M%S)"

# Copy new file
echo "2. Copying updated HTTP server file..."
scp -i $SSH_KEY $LOCAL_FILE ubuntu@$EC2_HOST:$REMOTE_FILE

# Restart PM2 process
echo "3. Restarting moisture-http process..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "pm2 restart moisture-http"

# Wait a moment
sleep 3

# Check status
echo "4. Checking process status..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "pm2 status moisture-http"

echo ""
echo "5. Checking recent logs..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "pm2 logs moisture-http --lines 10 --nostream"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Changes:"
echo "✅ Empty payloads are now ACCEPTED (200 OK response)"
echo "✅ Empty payloads are NOT sent to SQS (won't reach database)"
echo "✅ Valid data continues to be processed normally"
echo "✅ Empty payload tracking continues for monitoring"
echo ""
echo "Monitor at: http://$EC2_HOST:8080/api/stats/empty-payloads"