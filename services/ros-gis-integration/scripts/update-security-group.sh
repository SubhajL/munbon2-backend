#!/bin/bash

# Script to add port 3022 to EC2 security group

set -e

# Configuration
INSTANCE_ID="i-04ff727ac3337a608"
PORT="3022"
PROTOCOL="tcp"
DESCRIPTION="ROS/GIS Integration Service"
REGION="ap-southeast-1"

# Set AWS region
export AWS_DEFAULT_REGION=$REGION

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Updating EC2 Security Group for ROS/GIS Integration Service${NC}"
echo ""

# Get the security group ID
echo -e "${YELLOW}Getting security group ID...${NC}"
SECURITY_GROUP_ID=$(aws ec2 describe-instances \
    --region ${REGION} \
    --instance-ids ${INSTANCE_ID} \
    --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
    --output text)

if [ -z "$SECURITY_GROUP_ID" ] || [ "$SECURITY_GROUP_ID" == "None" ]; then
    echo -e "${RED}Error: Could not find security group for instance ${INSTANCE_ID}${NC}"
    exit 1
fi

echo "Security Group ID: $SECURITY_GROUP_ID"

# Check if the rule already exists
echo -e "${YELLOW}Checking if port ${PORT} is already open...${NC}"
EXISTING_RULE=$(aws ec2 describe-security-groups \
    --group-ids ${SECURITY_GROUP_ID} \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`${PORT}\`]" \
    --output json 2>/dev/null || echo "[]")

if [ "$EXISTING_RULE" != "[]" ]; then
    echo -e "${YELLOW}Port ${PORT} is already open in security group${NC}"
else
    # Add the security group rule
    echo -e "${YELLOW}Adding inbound rule for port ${PORT}...${NC}"
    aws ec2 authorize-security-group-ingress \
        --group-id ${SECURITY_GROUP_ID} \
        --protocol ${PROTOCOL} \
        --port ${PORT} \
        --cidr 0.0.0.0/0 \
        --group-rule-description "${DESCRIPTION}"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Successfully added port ${PORT} to security group${NC}"
    else
        echo -e "${RED}✗ Failed to add security group rule${NC}"
        exit 1
    fi
fi

# Verify the rule
echo -e "${YELLOW}Verifying security group rules...${NC}"
aws ec2 describe-security-groups \
    --group-ids ${SECURITY_GROUP_ID} \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`${PORT}\`].[FromPort,ToPort,IpRanges[0].CidrIp]" \
    --output table

echo ""
echo -e "${GREEN}Security group update complete!${NC}"
echo ""
echo "You should now be able to access the service at:"
echo "  http://43.209.22.250:${PORT}/health"
echo "  http://43.209.22.250:${PORT}/graphql"
echo ""