# AWS Lambda Deployment Guide

## Prerequisites

1. AWS CLI configured with your credentials OR
2. AWS credentials set in environment variables

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment variables**:
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env with your TimescaleDB connection details
   # DO NOT put AWS credentials in .env
   ```

3. **Set AWS credentials** (choose one method):

   **Method 1 - AWS CLI** (Recommended):
   ```bash
   aws configure
   # Enter your Access Key ID, Secret Access Key, and region
   ```

   **Method 2 - Environment variables**:
   ```bash
   export AWS_ACCESS_KEY_ID=AKIARSUGAPRU5GWX5G6I
   export AWS_SECRET_ACCESS_KEY=eKb90hW6hXeuvPbEx7A1FjWEp+7VSVJV5YSXMHbc
   export AWS_REGION=ap-southeast-1
   ```

   **Method 3 - .env.deploy file** (for convenience):
   ```bash
   cp .env.example .env.deploy
   # Add AWS credentials to .env.deploy (DO NOT commit this file)
   ```

## Deploy

```bash
# Deploy to development
./deploy.sh

# Or manually:
npx serverless deploy --stage dev

# Deploy to production
npx serverless deploy --stage prod
```

## Important Notes

1. **AWS Reserved Environment Variables**: Lambda does not allow setting AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or AWS_REGION as environment variables. These are automatically provided by AWS.

2. **Database Connection**: Update the TimescaleDB connection details in `.env` to point to your actual database (RDS or external).

3. **SQS Queue URL**: After deployment, note the SQS Queue URL from the output. You'll need this for the local consumer service.

## Verify Deployment

1. Check the Lambda functions in AWS Console
2. Test with a sample request:
   ```bash
   # Get your API Gateway URL from deployment output
   API_URL="https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/dev"
   
   # Test water level sensor
   curl -X POST $API_URL/api/v1/munbon-ridr-water-level/telemetry \
     -H 'Content-Type: application/json' \
     -d '{"deviceID":"test-001","level":15,"latitude":13.7563,"longitude":100.5018}'
   ```

## Troubleshooting

1. **"Reserved keys" error**: Make sure AWS credentials are not in the Lambda environment variables
2. **"Access denied" error**: Verify your AWS credentials have necessary permissions
3. **Database connection error**: Check that Lambda can reach your database (VPC, security groups)