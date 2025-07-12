#!/bin/bash

# Fix Lambda environment variables to use correct Munbon tunnel URL

echo "=== Fixing Lambda Tunnel URL Configuration ==="
echo ""

STAGE="prod"
SERVICE="munbon-data-api"
CORRECT_TUNNEL_URL="https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com"

# Function to update environment variables for a Lambda function
update_function_env() {
    local function_name=$1
    echo "Updating: $function_name"
    
    aws lambda update-function-configuration \
        --function-name "$function_name" \
        --environment Variables="{
            TUNNEL_URL='$CORRECT_TUNNEL_URL',
            INTERNAL_API_KEY='munbon-internal-f3b89263126548',
            EXTERNAL_API_KEYS='rid-ms-prod-key1,tmd-weather-key2,university-key3',
            STAGE='$STAGE'
        }" \
        --region ap-southeast-1
    
    if [ $? -eq 0 ]; then
        echo "✅ Updated $function_name"
    else
        echo "❌ Failed to update $function_name"
    fi
}

# List of functions to update
functions=(
    "${SERVICE}-${STAGE}-waterLevelLatest"
    "${SERVICE}-${STAGE}-waterLevelTimeseries"
    "${SERVICE}-${STAGE}-waterLevelStatistics"
    "${SERVICE}-${STAGE}-moistureLatest"
    "${SERVICE}-${STAGE}-moistureTimeseries"
    "${SERVICE}-${STAGE}-moistureStatistics"
    "${SERVICE}-${STAGE}-aosLatest"
    "${SERVICE}-${STAGE}-aosTimeseries"
    "${SERVICE}-${STAGE}-aosStatistics"
    "${SERVICE}-${STAGE}-corsOptions"
)

echo "Fixing tunnel URL for all functions..."
echo "Old URL: https://munbon-api-proxy.beautifyai.io"
echo "New URL: $CORRECT_TUNNEL_URL"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first:"
    echo "   brew install awscli"
    echo "   or"
    echo "   pip install awscli"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run:"
    echo "   aws configure"
    exit 1
fi

for func in "${functions[@]}"; do
    update_function_env "$func"
done

echo ""
echo "=== Update Complete ==="
echo ""
echo "Now test with:"
echo "curl -H \"X-API-Key: rid-ms-prod-key1\" https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest"