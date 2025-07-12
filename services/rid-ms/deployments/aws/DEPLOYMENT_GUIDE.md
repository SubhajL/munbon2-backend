# RID-MS Service AWS Deployment Guide

## Overview

The RID-MS Service follows a serverless architecture pattern similar to the water level and moisture monitoring services:

1. **Ingestion**: External API Gateway receives shape files pushed by external parties
2. **Storage**: DynamoDB stores parcel data and water demand calculations  
3. **Processing**: SQS queues and Lambda functions handle water demand calculations
4. **Exposure**: Node.js API service exposes data for frontend consumption

## Architecture Components

### Ingestion Layer
- **External API Gateway**: Receives shape file pushes with token authentication
- **API Gateway Lambda**: Validates requests and stores files in S3
- **S3 Upload Bucket**: Stores shape file uploads (zip format)
- **SQS Queue**: Coordinates asynchronous shape file processing
- **SQS Consumer Lambda**: Processes shape files from queue
- **DynamoDB Tables**: Store shape file metadata and parcel data

### Processing Layer
- **SQS Queue**: Coordinates water demand calculations
- **Lambda Function**: Calculates water demand using RID-MS, ROS, or AWD methods
- **DynamoDB Table**: Stores water demand calculations with history

### API Layer
- **Node.js Service**: Exposes REST APIs for data access
- **API Gateway**: Optional for external access
- **S3 Processed Bucket**: Stores processed GeoJSON files

## Deployment Steps

### 1. Build Lambda Functions

```bash
cd services/rid-ms

# Install dependencies
npm install

# Build TypeScript
npm run build

# Package Lambda functions
cd dist/lambda
zip -r api-gateway-handler.zip api-gateway-handler.js node_modules/
zip -r sqs-consumer.zip sqs-consumer.js node_modules/
zip -r water-demand-processor.zip water-demand-processor.js node_modules/

# Upload to S3
aws s3 cp api-gateway-handler.zip s3://rid-ms-lambda-code-${AWS_REGION}/
aws s3 cp sqs-consumer.zip s3://rid-ms-lambda-code-${AWS_REGION}/
aws s3 cp water-demand-processor.zip s3://rid-ms-lambda-code-${AWS_REGION}/
```

### 2. Deploy CloudFormation Stack

```bash
aws cloudformation create-stack \
  --stack-name rid-ms-infrastructure \
  --template-body file://deployments/aws/cloudformation.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=prod \
    ParameterKey=ServiceName,ParameterValue=rid-ms \
  --capabilities CAPABILITY_NAMED_IAM
```

### 3. Deploy API Service

#### Using Docker:
```bash
# Build Docker image
docker build -t rid-ms-service .

# Tag for ECR
docker tag rid-ms-service:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/rid-ms-service:latest

# Push to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/rid-ms-service:latest
```

#### Using ECS/Fargate:
```bash
# Update task definition with new image
aws ecs update-service \
  --cluster munbon-cluster \
  --service rid-ms-service \
  --force-new-deployment
```

### 4. Configure Environment Variables

Set these environment variables for the API service:

```bash
# AWS Configuration
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>

# DynamoDB Tables
SHAPE_FILE_TABLE=rid-ms-shapefiles-prod
PARCEL_TABLE=rid-ms-parcels-prod
WATER_DEMAND_TABLE=rid-ms-water-demand-prod

# S3 Buckets
UPLOAD_BUCKET=rid-ms-uploads-prod
PROCESSED_BUCKET=rid-ms-processed-prod

# Service Configuration
NODE_ENV=production
PORT=3048
```

## Usage Flow

### 1. External Push (For RID and External Partners)

```bash
# Convert shape file zip to base64
base64 parcels_2024.zip > parcels_base64.txt

# Push to external API
curl -X POST https://api.munbon.com/api/external/shapefile/push \
  -H "Authorization: Bearer munbon-ridms-shape" \
  -H "Content-Type: application/json" \
  -d '{
    "fileName": "parcels_2024.zip",
    "fileContent": "'$(cat parcels_base64.txt)'",
    "waterDemandMethod": "AWD",
    "processingInterval": "weekly",
    "metadata": {
      "zone": "Zone1",
      "uploadedBy": "RID-NakhonRatchasima"
    }
  }'

# Or use the provided script
./push-shapefile.sh parcels_2024.zip prod
```

### 2. Monitor Processing

```bash
# Check shape file status
curl https://api.munbon.com/api/v1/rid-ms/shapefiles/${SHAPE_FILE_ID} \
  -H "Authorization: Bearer ${TOKEN}"
```

### 3. Access Data

```bash
# Get parcels by zone
curl https://api.munbon.com/api/v1/rid-ms/zones/Zone1/parcels \
  -H "Authorization: Bearer ${TOKEN}"

# Get water demand summary
curl https://api.munbon.com/api/v1/rid-ms/zones/Zone1/water-demand-summary \
  -H "Authorization: Bearer ${TOKEN}"

# Get GeoJSON for visualization
curl https://api.munbon.com/api/v1/rid-ms/shapefiles/${SHAPE_FILE_ID}/geojson \
  -H "Authorization: Bearer ${TOKEN}"
```

## Monitoring

### CloudWatch Metrics
- Lambda invocation count and errors
- DynamoDB read/write capacity
- S3 upload/download metrics
- API Gateway request count and latency

### Alarms
- Shape file processing errors > 5 in 5 minutes
- Water demand calculation failures
- API error rate > 1%
- DynamoDB throttling

## Scaling Considerations

### Lambda Concurrency
- Shape file ingestion: Reserved concurrency of 10
- Water demand processor: Reserved concurrency of 50

### DynamoDB
- On-demand billing for automatic scaling
- Consider provisioned capacity for predictable workloads

### API Service
- Horizontal scaling with ECS/Fargate
- Auto-scaling based on CPU/memory utilization

## Cost Optimization

1. **S3 Lifecycle Policies**
   - Move processed files to Glacier after 90 days
   - Delete raw uploads after 30 days

2. **Lambda Optimization**
   - Use appropriate memory allocation (3GB for shape file processing)
   - Implement efficient batch processing

3. **DynamoDB**
   - Use on-demand for variable workloads
   - Enable point-in-time recovery for critical data

## Security

1. **IAM Roles**
   - Least privilege access for Lambda functions
   - Separate roles for different components

2. **S3 Bucket Policies**
   - Restrict upload access to authenticated users
   - Enable versioning and encryption

3. **API Security**
   - JWT authentication for all endpoints
   - Rate limiting to prevent abuse

## Troubleshooting

### Common Issues

1. **Shape file processing fails**
   - Check Lambda logs in CloudWatch
   - Verify file format (must be zip with .shp, .dbf, .shx files)
   - Check DLQ for error messages

2. **Water demand calculation errors**
   - Verify parcel data has required fields
   - Check crop type mappings
   - Review calculation Lambda logs

3. **API timeout errors**
   - Increase Lambda memory/timeout
   - Implement pagination for large datasets
   - Use async processing for bulk operations

### Debug Commands

```bash
# View Lambda logs
aws logs tail /aws/lambda/rid-ms-shapefile-ingestion --follow

# Check DLQ messages
aws sqs receive-message --queue-url ${DLQ_URL}

# Query DynamoDB
aws dynamodb query \
  --table-name rid-ms-parcels-prod \
  --index-name zone-index \
  --key-condition-expression "zone = :zone" \
  --expression-attribute-values '{":zone":{"S":"Zone1"}}'
```