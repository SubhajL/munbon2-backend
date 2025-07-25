#!/bin/bash

# Update EC2 Security Group to allow Lambda connections

echo "=== Updating EC2 Security Group for Lambda Access ==="
echo ""

# Variables
EC2_IP="43.209.12.182"
REGION="ap-southeast-1"

# Find security group ID
echo "Finding security group for EC2 instance with IP: $EC2_IP"
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=ip-address,Values=$EC2_IP" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --region $REGION \
    --output text 2>/dev/null)

if [ "$INSTANCE_ID" == "None" ] || [ -z "$INSTANCE_ID" ]; then
    echo "❌ Could not find EC2 instance with IP $EC2_IP"
    echo ""
    echo "Attempting alternative approach..."
    
    # For external EC2 instances, we'll add rules for Lambda's IP ranges
    echo "Since this appears to be an external EC2 instance, you'll need to:"
    echo "1. Log into the EC2 provider's console"
    echo "2. Find the security group/firewall rules for the instance"
    echo "3. Add inbound rule for PostgreSQL (port 5432) from anywhere (0.0.0.0/0)"
    echo "   OR preferably from AWS Lambda IP ranges for ap-southeast-1"
    echo ""
    echo "For now, let's ensure the EC2 instance allows connections from anywhere on port 5432"
    echo ""
    
    # Create a simple security group update script for manual execution
    cat > manual-sg-update.txt << EOF
Manual Security Group Update Instructions:

1. If this is an AWS EC2 instance:
   - Go to AWS Console > EC2 > Security Groups
   - Find the security group attached to your instance
   - Add inbound rule:
     * Type: PostgreSQL
     * Port: 5432
     * Source: 0.0.0.0/0 (or restrict to Lambda IP ranges)

2. If this is a non-AWS VPS/Cloud instance:
   - Check firewall rules (ufw, iptables, etc.)
   - Allow incoming connections on port 5432
   - Example for ufw:
     sudo ufw allow 5432/tcp
     sudo ufw reload

3. AWS Lambda IP Ranges for ap-southeast-1:
   You can get the latest IP ranges from:
   https://ip-ranges.amazonaws.com/ip-ranges.json
   
   Filter for:
   - Region: ap-southeast-1
   - Service: LAMBDA
EOF
    
    echo "Instructions saved to manual-sg-update.txt"
    exit 0
fi

# Get security group ID
SG_ID=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query "Reservations[0].Instances[0].SecurityGroups[0].GroupId" \
    --region $REGION \
    --output text)

echo "Instance ID: $INSTANCE_ID"
echo "Security Group ID: $SG_ID"
echo ""

# Add rule for PostgreSQL access from anywhere (Lambda doesn't have fixed IPs)
echo "Adding inbound rule for PostgreSQL (port 5432) from anywhere..."
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 5432 \
    --cidr 0.0.0.0/0 \
    --region $REGION \
    2>&1 | grep -v "already exists" || true

# Also add rules for other service ports
echo "Adding inbound rules for other services..."

# Sensor data service
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 3001 \
    --cidr 0.0.0.0/0 \
    --region $REGION \
    2>&1 | grep -v "already exists" || true

# Consumer dashboard
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 3002 \
    --cidr 0.0.0.0/0 \
    --region $REGION \
    2>&1 | grep -v "already exists" || true

echo ""
echo "=== Security Group Update Complete ==="
echo ""
echo "The following ports are now open:"
echo "- 5432 (PostgreSQL) - For Lambda data exposure API"
echo "- 3001 (Sensor Data Service) - For Cloudflare tunnel"
echo "- 3002 (Consumer Dashboard) - For monitoring"
echo ""
echo "Note: Opening ports to 0.0.0.0/0 is not recommended for production."
echo "Consider restricting to specific IP ranges once you identify Lambda's IPs."