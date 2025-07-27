#!/bin/bash

# Script to check EC2 instance status
# Requires AWS CLI to be installed and configured

echo "=== EC2 Instance Check Script ==="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first:"
    echo "brew install awscli"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "AWS CLI is not configured. Please run:"
    echo "aws configure"
    exit 1
fi

# Get all EC2 instances
echo "Fetching EC2 instances..."
aws ec2 describe-instances \
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress,PublicDnsName,Tags[?Key==`Name`].Value|[0]]' \
    --output table

echo ""
echo "=== Security Groups ==="
# Get security groups
aws ec2 describe-security-groups \
    --query 'SecurityGroups[*].[GroupId,GroupName,Description]' \
    --output table

echo ""
echo "To check specific security group rules for SSH:"
echo "aws ec2 describe-security-groups --group-ids <your-security-group-id> --query 'SecurityGroups[*].IpPermissions[?FromPort==\`22\`]'"

echo ""
echo "=== Quick Actions ==="
echo "1. Start EC2 instance: aws ec2 start-instances --instance-ids <instance-id>"
echo "2. Check instance status: aws ec2 describe-instance-status --instance-ids <instance-id>"
echo "3. Get instance public IP: aws ec2 describe-instances --instance-ids <instance-id> --query 'Reservations[0].Instances[0].PublicIpAddress' --output text"