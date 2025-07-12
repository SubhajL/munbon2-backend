#!/bin/bash

# Deployment script for AWS Lambda sensor ingestion functions

set -e

echo "🚀 Deploying Munbon Sensor Ingestion to AWS Lambda"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure your settings"
    exit 1
fi

# Load deployment credentials
if [ -f .env.deploy ]; then
    export $(cat .env.deploy | grep -v '^#' | xargs)
fi

# Load Lambda environment variables
export $(cat .env | grep -v '^#' | grep -v '^AWS_' | xargs)

# Check required environment variables
required_vars=(
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "TIMESCALE_HOST"
    "TIMESCALE_PORT"
    "TIMESCALE_DB"
    "TIMESCALE_USER"
    "TIMESCALE_PASSWORD"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: $var is not set in .env file"
        exit 1
    fi
done

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Deploy based on stage
STAGE=${1:-dev}

echo "🌍 Deploying to stage: $STAGE"

if [ "$STAGE" == "prod" ]; then
    echo "⚠️  Production deployment - are you sure? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled"
        exit 0
    fi
fi

# Deploy with serverless
echo "☁️  Deploying to AWS..."
npx serverless@3.40.0 deploy --stage "$STAGE"

# Get deployment info
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Deployment Info:"
npx serverless@3.40.0 info --stage "$STAGE"

# Save API endpoint
API_URL=$(npx serverless@3.40.0 info --stage "$STAGE" | grep "endpoint:" | head -1 | awk '{print $2}')

if [ -n "$API_URL" ]; then
    echo ""
    echo "🌐 API Gateway URL: $API_URL"
    echo ""
    echo "📡 Test your deployment:"
    echo "curl -X POST $API_URL/api/v1/munbon-test-devices/telemetry \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"deviceID\":\"test-001\",\"level\":15,\"latitude\":13.7563,\"longitude\":100.5018}'"
fi

echo ""
echo "📊 View logs:"
echo "npx serverless@3.40.0 logs -f telemetry --tail --stage $STAGE"

echo ""
echo "🗑️  To remove deployment:"
echo "npx serverless@3.40.0 remove --stage $STAGE"