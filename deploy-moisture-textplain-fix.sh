#!/bin/bash

# EC2 instance details
EC2_HOST="43.208.201.191"
EC2_USER="ubuntu"
SSH_KEY_PATH="$HOME/dev/th-lab01.pem"

echo "=== Deploying Moisture Endpoint Fix for text/plain Support ==="
echo "Timestamp: $(date)"
echo ""

# Backup current version
echo "1. Backing up current version..."
ssh -o StrictHostKeyChecking=no -i ${SSH_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
  "cp /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js \
   /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js.backup-$(date +%Y%m%d-%H%M%S)"

# Copy new version
echo ""
echo "2. Copying fixed version to EC2..."
scp -o StrictHostKeyChecking=no -i ${SSH_KEY_PATH} \
  ./services/sensor-data/src/simple-http-server-fixed.js \
  ${EC2_USER}@${EC2_HOST}:/home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server-fixed.js

# Replace the current file
echo ""
echo "3. Replacing current file with fixed version..."
ssh -o StrictHostKeyChecking=no -i ${SSH_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
  "cp /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server-fixed.js \
   /home/ubuntu/munbon2-backend/services/sensor-data/src/simple-http-server.js"

# Restart the service
echo ""
echo "4. Restarting moisture-http service..."
ssh -o StrictHostKeyChecking=no -i ${SSH_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
  "pm2 restart moisture-http && pm2 save"

# Check status
echo ""
echo "5. Checking service status..."
ssh -o StrictHostKeyChecking=no -i ${SSH_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
  "pm2 status moisture-http"

# Test health endpoint
echo ""
echo "6. Testing health endpoint..."
sleep 3
curl -s http://${EC2_HOST}:8080/health | jq .

echo ""
echo "=== Deployment Complete ===""
echo "The moisture endpoint now supports text/plain content type!"