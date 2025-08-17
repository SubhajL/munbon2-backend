#!/bin/bash

# Security Group Update Script for ROS/GIS Integration Service
# This script updates the EC2 security group to allow port 3022

set -e

# Configuration
INSTANCE_ID="i-04ff727ac3337a608"
PORT="3022"
DESCRIPTION="ROS/GIS Integration Service"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Security Group Update Script${NC}"
echo -e "${YELLOW}This script will add port ${PORT} to your EC2 instance security group${NC}"
echo ""

# Function to check if AWS CLI is installed
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
        echo "Visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
        exit 1
    fi
}

# Function to check AWS credentials
check_aws_credentials() {
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}AWS credentials not configured or invalid.${NC}"
        echo "Run: aws configure"
        exit 1
    fi
}

# Main execution
echo "Step 1: Checking prerequisites..."
check_aws_cli
check_aws_credentials

echo -e "${GREEN}✓ AWS CLI is installed and configured${NC}"
echo ""

# Try multiple regions
echo "Step 2: Finding instance in AWS regions..."
REGIONS=("ap-southeast-1" "us-east-1" "us-west-2" "eu-west-1" "ap-northeast-1")
FOUND_REGION=""
SECURITY_GROUP_ID=""

for region in "${REGIONS[@]}"; do
    echo -n "Checking region ${region}... "
    if aws ec2 describe-instances --instance-ids ${INSTANCE_ID} --region ${region} &> /dev/null; then
        FOUND_REGION=${region}
        echo -e "${GREEN}Found!${NC}"
        
        # Get security group ID
        SECURITY_GROUP_ID=$(aws ec2 describe-instances \
            --instance-ids ${INSTANCE_ID} \
            --region ${FOUND_REGION} \
            --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
            --output text)
        break
    else
        echo "Not found"
    fi
done

if [ -z "${FOUND_REGION}" ]; then
    echo -e "${RED}Instance ${INSTANCE_ID} not found in any common region.${NC}"
    echo ""
    echo "Alternative: Update security group manually"
    echo "1. Check your AWS region"
    echo "2. Find instance with IP ${EC2_HOST:-43.208.201.191}"
    echo "3. Update its security group to allow TCP port ${PORT}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Found instance in region: ${FOUND_REGION}${NC}"
echo -e "${GREEN}✓ Security Group ID: ${SECURITY_GROUP_ID}${NC}"
echo ""

# Check if rule already exists
echo "Step 3: Checking if port ${PORT} is already open..."
RULE_EXISTS=$(aws ec2 describe-security-groups \
    --group-ids ${SECURITY_GROUP_ID} \
    --region ${FOUND_REGION} \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`${PORT}\`]" \
    --output json | jq '. | length')

if [ "${RULE_EXISTS}" -gt 0 ]; then
    echo -e "${YELLOW}Port ${PORT} is already open in the security group.${NC}"
    echo "Existing rule found. No changes needed."
    exit 0
fi

# Add the security group rule
echo "Step 4: Adding security group rule for port ${PORT}..."
if aws ec2 authorize-security-group-ingress \
    --group-id ${SECURITY_GROUP_ID} \
    --region ${FOUND_REGION} \
    --protocol tcp \
    --port ${PORT} \
    --cidr 0.0.0.0/0 \
    --group-rule-description "${DESCRIPTION}" 2>&1; then
    
    echo -e "${GREEN}✓ Successfully added port ${PORT} to security group!${NC}"
    echo ""
    echo "The ROS/GIS Integration Service is now accessible at:"
    echo "  http://${EC2_HOST:-43.208.201.191}:${PORT}/health"
    echo "  http://${EC2_HOST:-43.208.201.191}:${PORT}/graphql"
else
    echo -e "${RED}Failed to add security group rule.${NC}"
    echo "This might be due to:"
    echo "1. Insufficient permissions"
    echo "2. Rule already exists (check manually)"
    echo "3. Security group doesn't allow modifications"
    exit 1
fi

echo ""
echo -e "${GREEN}Security group update complete!${NC}"