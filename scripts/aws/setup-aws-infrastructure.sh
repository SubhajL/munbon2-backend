#!/bin/bash

# AWS Infrastructure Setup Script for Munbon Backend
# This script creates the necessary AWS resources for deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
PROJECT_NAME="munbon"
SERVICES=(
    "sensor-data"
    "auth"
    "gis"
    "moisture-monitoring"
    "weather-monitoring"
    "water-level-monitoring"
    "ros"
    "unified-api"
    "rid-ms"
    "awd-control"
    "flow-monitoring"
)

echo -e "${BLUE}[INFO]${NC} Setting up AWS infrastructure for Munbon Backend"
echo -e "${BLUE}[INFO]${NC} Region: $AWS_REGION"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} AWS credentials are not configured. Please run 'aws configure' first."
    exit 1
fi

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}[SUCCESS]${NC} AWS Account ID: $AWS_ACCOUNT_ID"

# Create ECR repositories
echo -e "${BLUE}[INFO]${NC} Creating ECR repositories..."
for service in "${SERVICES[@]}"; do
    repo_name="${PROJECT_NAME}-${service}"
    echo -e "${BLUE}[INFO]${NC} Creating ECR repository: $repo_name"
    
    if aws ecr describe-repositories --repository-names "$repo_name" --region "$AWS_REGION" &> /dev/null; then
        echo -e "${YELLOW}[WARNING]${NC} Repository $repo_name already exists"
    else
        aws ecr create-repository \
            --repository-name "$repo_name" \
            --region "$AWS_REGION" \
            --image-scanning-configuration scanOnPush=true \
            --image-tag-mutability MUTABLE
        echo -e "${GREEN}[SUCCESS]${NC} Created repository: $repo_name"
    fi
done

# Create ECS cluster
CLUSTER_NAME="${PROJECT_NAME}-cluster"
echo -e "${BLUE}[INFO]${NC} Creating ECS cluster: $CLUSTER_NAME"

if aws ecs describe-clusters --clusters "$CLUSTER_NAME" --region "$AWS_REGION" --query "clusters[0].status" --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo -e "${YELLOW}[WARNING]${NC} ECS cluster $CLUSTER_NAME already exists"
else
    aws ecs create-cluster \
        --cluster-name "$CLUSTER_NAME" \
        --region "$AWS_REGION" \
        --capacity-providers FARGATE FARGATE_SPOT \
        --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1
    echo -e "${GREEN}[SUCCESS]${NC} Created ECS cluster: $CLUSTER_NAME"
fi

# Create task execution role
TASK_ROLE_NAME="${PROJECT_NAME}-task-execution-role"
echo -e "${BLUE}[INFO]${NC} Creating IAM task execution role..."

TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

if aws iam get-role --role-name "$TASK_ROLE_NAME" &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} IAM role $TASK_ROLE_NAME already exists"
else
    aws iam create-role \
        --role-name "$TASK_ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY"
    
    aws iam attach-role-policy \
        --role-name "$TASK_ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
    
    echo -e "${GREEN}[SUCCESS]${NC} Created IAM role: $TASK_ROLE_NAME"
fi

# Create CloudWatch log groups
echo -e "${BLUE}[INFO]${NC} Creating CloudWatch log groups..."
for service in "${SERVICES[@]}"; do
    log_group="/ecs/${PROJECT_NAME}/${service}"
    echo -e "${BLUE}[INFO]${NC} Creating log group: $log_group"
    
    if aws logs describe-log-groups --log-group-name-prefix "$log_group" --region "$AWS_REGION" --query "logGroups[?logGroupName=='$log_group'].logGroupName" --output text | grep -q "$log_group"; then
        echo -e "${YELLOW}[WARNING]${NC} Log group $log_group already exists"
    else
        aws logs create-log-group \
            --log-group-name "$log_group" \
            --region "$AWS_REGION"
        echo -e "${GREEN}[SUCCESS]${NC} Created log group: $log_group"
    fi
done

# Create VPC and networking (if needed)
echo -e "${BLUE}[INFO]${NC} Checking VPC setup..."
DEFAULT_VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --region "$AWS_REGION" --query "Vpcs[0].VpcId" --output text)

if [ "$DEFAULT_VPC_ID" != "None" ]; then
    echo -e "${GREEN}[SUCCESS]${NC} Using default VPC: $DEFAULT_VPC_ID"
else
    echo -e "${YELLOW}[WARNING]${NC} No default VPC found. You may need to create one."
fi

# Create Application Load Balancer (optional)
echo -e "${BLUE}[INFO]${NC} Note: Application Load Balancer setup is optional and can be done later"

# Output summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}AWS Infrastructure Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nResources created:"
echo -e "- ECR repositories for all services"
echo -e "- ECS cluster: $CLUSTER_NAME"
echo -e "- IAM task execution role: $TASK_ROLE_NAME"
echo -e "- CloudWatch log groups"
echo -e "\nNext steps:"
echo -e "1. The GitHub Actions workflow will now be able to push images to ECR"
echo -e "2. You'll need to create task definitions and services for each microservice"
echo -e "3. Consider setting up an Application Load Balancer for public access"
echo -e "\nTo deploy services, push changes to the main branch and GitHub Actions will handle the rest!"