#!/bin/bash

# Script to configure EC2 security group for HTTP server
# Run this locally (not on EC2)

echo "🔐 Configuring EC2 Security Group for HTTP Server"

# Get instance details
INSTANCE_ID=$(aws ec2 describe-instances \
    --filters "Name=instance-state-name,Values=running" \
    --query "Reservations[*].Instances[*].[InstanceId,PublicDnsName,SecurityGroups[0].GroupId]" \
    --output text | grep "ec2-${EC2_HOST:-43.208.201.191}" | awk '{print $1}')

if [ -z "$INSTANCE_ID" ]; then
    echo "❌ Could not find instance with hostname ec2-${EC2_HOST:-43.208.201.191}.ap-southeast-7.compute.amazonaws.com"
    echo "Please provide your instance ID:"
    read INSTANCE_ID
fi

# Get security group ID
SECURITY_GROUP_ID=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query "Reservations[0].Instances[0].SecurityGroups[0].GroupId" \
    --output text)

echo "📋 Instance ID: $INSTANCE_ID"
echo "🔒 Security Group ID: $SECURITY_GROUP_ID"

# Function to add rule if it doesn't exist
add_rule_if_not_exists() {
    local port=$1
    local protocol=$2
    local cidr=$3
    local description=$4
    
    # Check if rule exists
    EXISTS=$(aws ec2 describe-security-groups \
        --group-ids $SECURITY_GROUP_ID \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`$port\`]" \
        --output text)
    
    if [ -z "$EXISTS" ]; then
        echo "➕ Adding rule for port $port..."
        aws ec2 authorize-security-group-ingress \
            --group-id $SECURITY_GROUP_ID \
            --protocol $protocol \
            --port $port \
            --cidr $cidr \
            --group-rule-description "$description" 2>/dev/null || echo "   Rule might already exist"
    else
        echo "✅ Rule for port $port already exists"
    fi
}

# Add required rules
echo ""
echo "🔧 Configuring security group rules..."

# Port 8080 for HTTP server
add_rule_if_not_exists 8080 tcp "0.0.0.0/0" "Moisture sensor HTTP server"

# Port 3003 for main sensor service
add_rule_if_not_exists 3003 tcp "0.0.0.0/0" "Sensor data service"

# Port 22 for SSH (if not exists)
add_rule_if_not_exists 22 tcp "0.0.0.0/0" "SSH access"

# Port 80 for standard HTTP (optional)
add_rule_if_not_exists 80 tcp "0.0.0.0/0" "Standard HTTP"

echo ""
echo "📊 Current security group rules:"
aws ec2 describe-security-groups \
    --group-ids $SECURITY_GROUP_ID \
    --query "SecurityGroups[0].IpPermissions[*].[FromPort,IpProtocol,IpRanges[0].CidrIp]" \
    --output table

echo ""
echo "✅ Security group configuration complete!"
echo ""
echo "🚀 Next steps:"
echo "1. Copy deployment script to EC2:"
echo "   scp deploy-http-server.sh ec2-user@ec2-${EC2_HOST:-43.208.201.191}.ap-southeast-7.compute.amazonaws.com:~/"
echo ""
echo "2. SSH to EC2 and run deployment:"
echo "   ssh ec2-user@ec2-${EC2_HOST:-43.208.201.191}.ap-southeast-7.compute.amazonaws.com"
echo "   chmod +x deploy-http-server.sh"
echo "   ./deploy-http-server.sh"