#!/bin/bash

# Complete deployment script for moisture HTTP server
# This script handles everything from security group to deployment

set -e

echo "🚀 Complete Moisture HTTP Server Deployment"
echo "==========================================="

# Configuration
EC2_HOST="ec2-43.209.22.250.ap-southeast-7.compute.amazonaws.com"
EC2_USER="ec2-user"
HTTP_PORT=8080

# Step 1: Configure Security Group (run locally)
echo "Step 1: Configuring Security Group..."
echo "Please run this command in AWS CLI or Console to add security group rules:"
echo ""
echo "For AWS CLI:"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 8080 --cidr 0.0.0.0/0"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3003 --cidr 0.0.0.0/0"
echo ""
echo "Press Enter when security group is configured..."
read

# Step 2: Copy files to EC2
echo ""
echo "Step 2: Copying deployment script to EC2..."
scp deploy-http-server.sh ${EC2_USER}@${EC2_HOST}:~/ || {
    echo "❌ Failed to copy files. Please check:"
    echo "   1. Your SSH key is configured"
    echo "   2. The EC2 hostname is correct"
    echo "   3. Security group allows SSH (port 22)"
    exit 1
}

# Step 3: Execute deployment on EC2
echo ""
echo "Step 3: Executing deployment on EC2..."
ssh ${EC2_USER}@${EC2_HOST} << 'ENDSSH'
chmod +x deploy-http-server.sh
./deploy-http-server.sh
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📡 Your moisture sensor endpoints:"
echo "   HTTP: http://${EC2_HOST}:${HTTP_PORT}/api/sensor-data/moisture/munbon-m2m-moisture"
echo ""
echo "🧪 Test command:"
echo "curl -X POST http://${EC2_HOST}:${HTTP_PORT}/api/sensor-data/moisture/munbon-m2m-moisture \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"gateway_id\":\"TEST-001\",\"sensor\":[{\"moisture\":45,\"temperature\":28}]}'"