#!/bin/bash

# Setup ECR repositories for all Munbon microservices
# Usage: ./setup-ecr.sh [region]

set -e

REGION=${1:-ap-southeast-1}
REPOSITORY_PREFIX="munbon"

# List of all services that need ECR repositories
SERVICES=(
  "sensor-data"
  "auth"
  "awd-control"
  "weather-monitoring"
  "water-level-monitoring"
  "moisture-monitoring"
  "gis"
  "ros"
  "rid-ms"
)

echo "Setting up ECR repositories in region: $REGION"

# Create repositories
for service in "${SERVICES[@]}"; do
  REPO_NAME="$REPOSITORY_PREFIX-$service"
  
  echo "Creating repository: $REPO_NAME"
  
  # Check if repository already exists
  if aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" 2>/dev/null; then
    echo "Repository $REPO_NAME already exists, skipping..."
  else
    # Create repository
    aws ecr create-repository \
      --repository-name "$REPO_NAME" \
      --region "$REGION" \
      --image-scanning-configuration scanOnPush=true \
      --image-tag-mutability MUTABLE
    
    # Set lifecycle policy to keep only last 10 images
    aws ecr put-lifecycle-policy \
      --repository-name "$REPO_NAME" \
      --region "$REGION" \
      --lifecycle-policy-text '{
        "rules": [
          {
            "rulePriority": 1,
            "description": "Keep last 10 images",
            "selection": {
              "tagStatus": "any",
              "countType": "imageCountMoreThan",
              "countNumber": 10
            },
            "action": {
              "type": "expire"
            }
          }
        ]
      }'
    
    echo "Repository $REPO_NAME created successfully"
  fi
done

# Get login token
echo ""
echo "Getting ECR login token..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$REGION.amazonaws.com"

echo ""
echo "ECR setup complete! Repositories created:"
aws ecr describe-repositories --region "$REGION" --query "repositories[?starts_with(repositoryName, '$REPOSITORY_PREFIX')].repositoryUri" --output table