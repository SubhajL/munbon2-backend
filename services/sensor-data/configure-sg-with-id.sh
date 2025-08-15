#!/bin/bash

# Configure security group using instance ID
INSTANCE_ID="i-04ff727ac3337a608"

echo "🔐 Configuring Security Group for Instance: $INSTANCE_ID"
echo "======================================================="

# Try to find the region
echo "🔍 Searching for instance region..."
REGION=""
for r in ap-southeast-1 ap-southeast-2 us-east-1 us-west-2 eu-west-1 ap-northeast-1; do
    if aws ec2 describe-instances --instance-ids $INSTANCE_ID --region $r &>/dev/null; then
        REGION=$r
        echo "✅ Found instance in region: $REGION"
        break
    fi
done

if [ -z "$REGION" ]; then
    echo "❌ Could not find instance. Please specify your AWS region:"
    echo "   (e.g., ap-southeast-1, us-east-1, etc.)"
    read -p "Region: " REGION
fi

# Get security group ID
echo "📋 Getting security group information..."
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --region $REGION --query "Reservations[0].Instances[0].SecurityGroups[0].GroupId" --output text 2>/dev/null)

if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
    echo "❌ Could not get security group ID"
    echo "Please check:"
    echo "1. Instance ID is correct: $INSTANCE_ID"
    echo "2. Region is correct: $REGION"
    echo "3. You have AWS credentials configured"
    exit 1
fi

echo "🔒 Security Group ID: $SG_ID"

# Function to add rule
add_rule() {
    local port=$1
    local description=$2
    echo "➕ Adding rule for port $port..."
    aws ec2 authorize-security-group-ingress \
        --group-id $SG_ID \
        --protocol tcp \
        --port $port \
        --cidr 0.0.0.0/0 \
        --region $REGION 2>&1 | grep -q "InvalidPermission.Duplicate" && echo "   ✅ Rule already exists" || echo "   ✅ Rule added"
}

# Add required rules
echo ""
echo "🔧 Adding security group rules..."
add_rule 8080 "Moisture HTTP Server"
add_rule 3003 "Sensor Data Service"
add_rule 80 "HTTP"
add_rule 22 "SSH"

# Show current rules
echo ""
echo "📊 Current security group rules:"
aws ec2 describe-security-groups --group-ids $SG_ID --region $REGION \
    --query "SecurityGroups[0].IpPermissions[*].[FromPort,ToPort,IpProtocol,IpRanges[0].CidrIp]" \
    --output table

echo ""
echo "✅ Security group configured!"
echo ""
echo "🚀 Next: Deploy the HTTP server"
echo "   scp deploy-http-server.sh ec2-user@43.209.22.250:~/"
echo "   ssh ec2-user@43.209.22.250"
echo "   ./deploy-http-server.sh"