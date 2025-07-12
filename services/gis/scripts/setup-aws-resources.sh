#!/bin/bash

# Setup AWS resources for GIS shape file processing

AWS_REGION=${AWS_REGION:-ap-southeast-1}
QUEUE_NAME="munbon-gis-shapefile-queue"
DLQ_NAME="munbon-gis-shapefile-dlq"
BUCKET_NAME="munbon-gis-shape-files"

echo "Setting up AWS resources for GIS shape file processing..."

# Create DLQ first
echo "Creating Dead Letter Queue..."
DLQ_URL=$(aws sqs create-queue \
  --queue-name "$DLQ_NAME" \
  --region "$AWS_REGION" \
  --attributes MessageRetentionPeriod=1209600 \
  --query 'QueueUrl' \
  --output text 2>/dev/null || \
  aws sqs get-queue-url --queue-name "$DLQ_NAME" --region "$AWS_REGION" --query 'QueueUrl' --output text)

echo "DLQ URL: $DLQ_URL"

# Get DLQ ARN
DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --region "$AWS_REGION" \
  --query 'Attributes.QueueArn' \
  --output text)

# Create main queue with DLQ redrive policy
echo "Creating main SQS queue..."
QUEUE_URL=$(aws sqs create-queue \
  --queue-name "$QUEUE_NAME" \
  --region "$AWS_REGION" \
  --attributes "{
    \"MessageRetentionPeriod\": \"1209600\",
    \"VisibilityTimeout\": \"300\",
    \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
  }" \
  --query 'QueueUrl' \
  --output text 2>/dev/null || \
  aws sqs get-queue-url --queue-name "$QUEUE_NAME" --region "$AWS_REGION" --query 'QueueUrl' --output text)

echo "Queue URL: $QUEUE_URL"

# Create S3 bucket
echo "Creating S3 bucket..."
if aws s3 ls "s3://$BUCKET_NAME" 2>&1 | grep -q 'NoSuchBucket'; then
  aws s3 mb "s3://$BUCKET_NAME" --region "$AWS_REGION"
  
  # Enable versioning
  aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled \
    --region "$AWS_REGION"
  
  echo "S3 bucket created: $BUCKET_NAME"
else
  echo "S3 bucket already exists: $BUCKET_NAME"
fi

# Output environment variables
echo ""
echo "Add these environment variables to your .env file:"
echo "GIS_SQS_QUEUE_URL=$QUEUE_URL"
echo "GIS_SQS_DLQ_URL=$DLQ_URL"
echo "SHAPE_FILE_BUCKET=$BUCKET_NAME"
echo "AWS_REGION=$AWS_REGION"

# Save to .env.example
cat > /Users/subhajlimanond/dev/munbon2-backend/services/gis/.env.example << EOF
# GIS Service Configuration
NODE_ENV=development
PORT=3007
HOST=0.0.0.0

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/munbon_gis

# AWS Configuration
AWS_REGION=$AWS_REGION
GIS_SQS_QUEUE_URL=$QUEUE_URL
GIS_SQS_DLQ_URL=$DLQ_URL
SHAPE_FILE_BUCKET=$BUCKET_NAME

# External API Token
EXTERNAL_UPLOAD_TOKEN=munbon-gis-shapefile

# Redis Cache
REDIS_URL=redis://localhost:6379

# API Configuration
API_PREFIX=/api/v1
EOF

echo ""
echo "Setup complete! .env.example file created."