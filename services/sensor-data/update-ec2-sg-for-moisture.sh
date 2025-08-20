#!/bin/bash

# Script to update EC2 security group to allow port 8080 for moisture data

set -e

EC2_IP="43.208.201.191"
REGION="ap-southeast-1"

echo "🔍 Finding EC2 instance and its security group..."

# Find instance ID by IP
INSTANCE_ID=$(aws ec2 describe-instances \
    --region $REGION \
    --query "Reservations[*].Instances[*].[InstanceId,PublicIpAddress]" \
    --output text | grep "$EC2_IP" | awk '{print $1}')

if [ -z "$INSTANCE_ID" ]; then
    echo "❌ Could not find EC2 instance with IP $EC2_IP"
    echo "Trying alternative search..."
    
    # List all instances
    echo "Available instances:"
    aws ec2 describe-instances \
        --region $REGION \
        --query "Reservations[*].Instances[*].{ID:InstanceId,PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress,State:State.Name}" \
        --output table
    exit 1
fi

echo "✅ Found instance: $INSTANCE_ID"

# Get security group IDs
SECURITY_GROUPS=$(aws ec2 describe-instances \
    --region $REGION \
    --instance-ids $INSTANCE_ID \
    --query "Reservations[0].Instances[0].SecurityGroups[*].GroupId" \
    --output text)

echo "📋 Security groups: $SECURITY_GROUPS"

# Add rule to each security group
for SG_ID in $SECURITY_GROUPS; do
    echo "🔧 Updating security group: $SG_ID"
    
    # Check if rule already exists
    EXISTING_RULE=$(aws ec2 describe-security-groups \
        --region $REGION \
        --group-ids $SG_ID \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`8080\`]" \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$EXISTING_RULE" != "[]" ]; then
        echo "✅ Port 8080 rule already exists in $SG_ID"
    else
        echo "➕ Adding port 8080 rule to $SG_ID..."
        aws ec2 authorize-security-group-ingress \
            --region $REGION \
            --group-id $SG_ID \
            --protocol tcp \
            --port 8080 \
            --cidr 0.0.0.0/0 \
            --group-rule-description "Moisture sensor HTTP endpoint" \
            2>&1 || echo "⚠️  Rule might already exist or permission denied"
    fi
done

echo ""
echo "✅ Security group update complete!"
echo ""
echo "🧪 Test the endpoint:"
echo "curl http://$EC2_IP:8080/health"