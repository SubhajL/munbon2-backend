#!/bin/bash

# Quick ALB setup script - keeps your existing API endpoint working!

echo "Setting up ALB with custom TLS (takes ~10 minutes)..."

# Variables
REGION="ap-southeast-1"
VPC_ID=$(aws ec2 describe-vpcs --region $REGION --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)
SUBNET_IDS=$(aws ec2 describe-subnets --region $REGION --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[?AvailabilityZone!='ap-southeast-1c'].SubnetId" --output text)

# 1. Create security group
echo "1. Creating security group..."
SG_ID=$(aws ec2 create-security-group \
    --group-name munbon-alb-sg \
    --description "Munbon ALB Security Group" \
    --vpc-id $VPC_ID \
    --region $REGION \
    --output text)

# Allow HTTPS
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    --region $REGION

# 2. Create ALB
echo "2. Creating Application Load Balancer..."
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name munbon-api-alb \
    --subnets $SUBNET_IDS \
    --security-groups $SG_ID \
    --region $REGION \
    --query "LoadBalancers[0].LoadBalancerArn" \
    --output text)

# 3. Create target group pointing to API Gateway
echo "3. Creating target group..."
TG_ARN=$(aws elbv2 create-target-group \
    --name munbon-api-tg \
    --protocol HTTPS \
    --port 443 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --health-check-path "/dev/api/v1/munbon-m2m-moisture/attributes" \
    --region $REGION \
    --query "TargetGroups[0].TargetGroupArn" \
    --output text)

# 4. Get API Gateway IP (this is simplified - in production use VPC Link)
API_ENDPOINT="c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com"
API_IP=$(dig +short $API_ENDPOINT | tail -1)

# Register API Gateway as target
aws elbv2 register-targets \
    --target-group-arn $TG_ARN \
    --targets Id=$API_IP \
    --region $REGION

# 5. Create HTTPS listener with TLS 1.0 policy
echo "4. Creating HTTPS listener with custom TLS..."
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=arn:aws:acm:$REGION:YOUR_ACCOUNT:certificate/YOUR_CERT \
    --ssl-policy ELBSecurityPolicy-TLS-1-0-2015-04 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $REGION

# Get ALB DNS
ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --region $REGION \
    --query "LoadBalancers[0].DNSName" \
    --output text)

echo ""
echo "✅ Setup Complete!"
echo ""
echo "Your endpoints:"
echo "1. Original (still works): https://$API_ENDPOINT/dev/..."
echo "2. New ALB (with TLS 1.0+): https://$ALB_DNS/dev/..."
echo ""
echo "The ALB supports TLS 1.0, 1.1, 1.2 with more cipher options."
echo "Your existing API endpoint continues to work unchanged!"