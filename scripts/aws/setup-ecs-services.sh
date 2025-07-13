#!/bin/bash

# ECS Task Definitions and Services Setup for Munbon Backend
# Optimized for small project with minimal resources

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
AWS_REGION="${AWS_REGION:-ap-southeast-1}"
AWS_ACCOUNT_ID="108728974441"
ECR_REPOSITORY="munbon-github-actions"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
CLUSTER_NAME="munbon-staging"
EXECUTION_ROLE_ARN=""

echo -e "${BLUE}[INFO]${NC} Setting up ECS Task Definitions and Services"
echo -e "${BLUE}[INFO]${NC} Region: $AWS_REGION"
echo -e "${BLUE}[INFO]${NC} Cluster: $CLUSTER_NAME"

# Services to deploy with minimal resources for small project
# CPU: 256 (0.25 vCPU), Memory: 512 MB for most services
# Using simple arrays instead of associative array for compatibility
SERVICES=(
    "sensor-data:256:512"
    "auth:256:512"
    "gis:512:1024"  # GIS needs more memory for spatial operations
    "moisture-monitoring:256:512"
    "rid-ms:256:512"
    "ros:256:512"
    "awd-control:256:512"
    "flow-monitoring:512:1024"  # Python service needs more memory
)

# First, create IAM role for task execution
ROLE_NAME="munbon-ecs-task-execution-role"
echo -e "${BLUE}[INFO]${NC} Creating ECS task execution role..."

# Check if role exists
if aws iam get-role --role-name "$ROLE_NAME" &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} Role $ROLE_NAME already exists"
    EXECUTION_ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
else
    # Create role
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
    
    EXECUTION_ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY" \
        --query 'Role.Arn' \
        --output text)
    
    # Attach policies
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
    
    # Create custom policy for Secrets Manager access
    SECRETS_POLICY='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "secretsmanager:GetSecretValue"
          ],
          "Resource": "arn:aws:secretsmanager:'"$AWS_REGION"':'"$AWS_ACCOUNT_ID"':secret:munbon/*"
        }
      ]
    }'
    
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "MunbonSecretsAccess" \
        --policy-document "$SECRETS_POLICY"
    
    echo -e "${GREEN}[SUCCESS]${NC} Created role: $EXECUTION_ROLE_ARN"
fi

# Create CloudWatch log groups
echo -e "${BLUE}[INFO]${NC} Creating CloudWatch log groups..."
for service_config in "${SERVICES[@]}"; do
    IFS=':' read -r service cpu memory <<< "$service_config"
    log_group="/ecs/munbon/${service}"
    
    if aws logs describe-log-groups --log-group-name-prefix "$log_group" --query "logGroups[?logGroupName=='$log_group']" --output text | grep -q "$log_group"; then
        echo -e "${YELLOW}[WARNING]${NC} Log group $log_group already exists"
    else
        aws logs create-log-group --log-group-name "$log_group"
        aws logs put-retention-policy --log-group-name "$log_group" --retention-in-days 7  # 7 days for cost savings
        echo -e "${GREEN}[SUCCESS]${NC} Created log group: $log_group"
    fi
done

# Create task definitions and services
for service_config in "${SERVICES[@]}"; do
    IFS=':' read -r service cpu memory <<< "$service_config"
    
    echo -e "${BLUE}[INFO]${NC} Setting up $service (CPU: $cpu, Memory: $memory)"
    
    # Create task definition
    TASK_DEF_NAME="munbon-${service}-staging"
    
    TASK_DEFINITION=$(cat <<EOF
{
  "family": "${TASK_DEF_NAME}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "${cpu}",
  "memory": "${memory}",
  "executionRoleArn": "${EXECUTION_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${service}",
      "image": "${ECR_URI}:${service}-latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/munbon/${service}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "environment": [
        {"name": "NODE_ENV", "value": "production"},
        {"name": "SERVICE_NAME", "value": "${service}"}
      ],
      "portMappings": [
        {
          "containerPort": 3000,
          "protocol": "tcp"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:3000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF
)
    
    # Register task definition
    echo -e "${BLUE}[INFO]${NC} Registering task definition: $TASK_DEF_NAME"
    aws ecs register-task-definition \
        --cli-input-json "$TASK_DEFINITION" \
        --region "$AWS_REGION" > /dev/null
    
    echo -e "${GREEN}[SUCCESS]${NC} Registered task definition: $TASK_DEF_NAME"
    
    # Check if service exists
    SERVICE_NAME="munbon-${service}-service"
    
    if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --query "services[?status=='ACTIVE']" --output text 2>/dev/null | grep -q "ACTIVE"; then
        echo -e "${YELLOW}[WARNING]${NC} Service $SERVICE_NAME already exists"
    else
        # Get default VPC and subnets
        VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text)
        SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[*].SubnetId" --output text | tr '\t' ',')
        
        # Create security group if not exists
        SG_NAME="munbon-ecs-services-sg"
        SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)
        
        if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
            echo -e "${BLUE}[INFO]${NC} Creating security group..."
            SG_ID=$(aws ec2 create-security-group \
                --group-name "$SG_NAME" \
                --description "Security group for Munbon ECS services" \
                --vpc-id "$VPC_ID" \
                --query "GroupId" \
                --output text)
            
            # Allow inbound traffic on port 3000 from anywhere (for ALB later)
            aws ec2 authorize-security-group-ingress \
                --group-id "$SG_ID" \
                --protocol tcp \
                --port 3000 \
                --cidr 0.0.0.0/0
            
            echo -e "${GREEN}[SUCCESS]${NC} Created security group: $SG_ID"
        fi
        
        # Create service
        echo -e "${BLUE}[INFO]${NC} Creating ECS service: $SERVICE_NAME"
        
        aws ecs create-service \
            --cluster "$CLUSTER_NAME" \
            --service-name "$SERVICE_NAME" \
            --task-definition "${TASK_DEF_NAME}:1" \
            --desired-count 0 \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
            --region "$AWS_REGION" > /dev/null
        
        echo -e "${GREEN}[SUCCESS]${NC} Created service: $SERVICE_NAME (desired count: 0)"
    fi
done

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}ECS Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nResources created:"
echo -e "- Task execution role: $ROLE_NAME"
echo -e "- Task definitions for all services"
echo -e "- ECS services (desired count: 0 to save costs)"
echo -e "- CloudWatch log groups with 7-day retention"
echo -e "- Security group: $SG_NAME"
echo -e "\nResource allocation (optimized for small project):"
echo -e "- Most services: 0.25 vCPU, 512 MB RAM"
echo -e "- GIS & Flow Monitoring: 0.5 vCPU, 1 GB RAM"
echo -e "\nNext steps:"
echo -e "1. Push code changes to trigger Docker image builds"
echo -e "2. Services will auto-deploy when images are available"
echo -e "3. Scale services by updating desired count when ready"
echo -e "\nTo start a service manually:"
echo -e "aws ecs update-service --cluster $CLUSTER_NAME --service munbon-<service>-service --desired-count 1"