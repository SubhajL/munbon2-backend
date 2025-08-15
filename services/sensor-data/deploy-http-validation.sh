#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="43.209.22.250"
LOCAL_FILE="patches/simple-http-server-validated.ts"
REMOTE_FILE="/home/ubuntu/app/moisture-http-server/src/simple-http-server.ts"

echo "=== Deploying HTTP Server Validation Update ==="
echo ""

# Backup current file
echo "1. Creating backup of current HTTP server..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "cp $REMOTE_FILE ${REMOTE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

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
echo "New features:"
echo "- Validates and rejects empty data payloads"
echo "- Tracks sources of empty payloads"
echo "- Requires gateway ID (gw_id or gateway_id)"
echo "- Adds stats endpoint: http://$EC2_HOST:8080/api/stats/empty-payloads"