#!/bin/bash

# Deployment script with correct SSH details
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="th-lab01.pem"

echo "🚀 Deploying Moisture HTTP Server to EC2"
echo "========================================"

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found: $SSH_KEY"
    echo "Please ensure you're in the directory containing th-lab01.pem"
    exit 1
fi

# Step 1: Copy deployment script to EC2
echo "📋 Copying deployment script to EC2..."
scp -i $SSH_KEY deploy-http-server.sh ${EC2_USER}@${EC2_HOST}:~/ || {
    echo "❌ Failed to copy files. Please check:"
    echo "   1. Security group allows SSH (port 22) from your IP"
    echo "   2. You're in the correct directory with th-lab01.pem"
    exit 1
}

# Step 2: SSH and run deployment
echo "🔧 Connecting to EC2 and running deployment..."
ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST} << 'ENDSSH'
# Make script executable
chmod +x deploy-http-server.sh

# Run deployment
./deploy-http-server.sh
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📡 Your moisture sensor HTTP endpoint:"
echo "   http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo ""
echo "🔍 To check logs on EC2:"
echo "   ssh -i $SSH_KEY ${EC2_USER}@${EC2_HOST}"
echo "   pm2 logs moisture-http"