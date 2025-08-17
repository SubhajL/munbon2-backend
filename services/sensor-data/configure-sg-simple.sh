#!/bin/bash

# Simple security group configuration
# Uses IP address instead of instance ID

echo "🔐 Security Group Configuration for Moisture HTTP Server"
echo "======================================================"
echo ""
echo "Since we can't automatically find your instance, please:"
echo ""
echo "1. Go to AWS Console > EC2 > Instances"
echo "2. Find the instance with IP: ${EC2_HOST:-43.208.201.191}"
echo "3. Click on the Security tab"
echo "4. Click on the Security Group link"
echo "5. Add these Inbound Rules:"
echo ""
echo "   Port 8080 | TCP | 0.0.0.0/0 | Moisture HTTP Server"
echo "   Port 3003 | TCP | 0.0.0.0/0 | Sensor Data Service"
echo "   Port 22   | TCP | Your IP   | SSH Access"
echo ""
echo "OR use AWS CLI with your security group ID:"
echo ""
echo "aws ec2 authorize-security-group-ingress --group-id sg-XXXXXXXX --protocol tcp --port 8080 --cidr 0.0.0.0/0 --region YOUR-REGION"
echo "aws ec2 authorize-security-group-ingress --group-id sg-XXXXXXXX --protocol tcp --port 3003 --cidr 0.0.0.0/0 --region YOUR-REGION"
echo ""
echo "Press Enter when done..."
read

echo "✅ Assuming security group is configured!"
echo ""
echo "Next step: Deploy the HTTP server"
echo "Run: ./deploy-moisture-http-complete.sh"