#!/bin/bash

# Script to update Lambda functions to use EC2 API proxy
# This will be run after port 8081 is opened

echo "🚀 Updating Lambda Functions to Use EC2 API Proxy"
echo "================================================"

# Configuration
REGION="ap-southeast-1"
RUNTIME="nodejs18.x"
TIMEOUT="30"
MEMORY="256"

# Create deployment package
echo "📦 Creating deployment package..."
mkdir -p lambda-deploy
cp lambda-proxy-function.js lambda-deploy/index.js
cd lambda-deploy
zip -q function.zip index.js
cd ..

# List of Lambda functions to update
LAMBDA_FUNCTIONS=(
    "munbon-data-api-prod-waterLevelLatest"
    "munbon-data-api-prod-waterLevelTimeseries"
    "munbon-data-api-prod-waterLevelStatistics"
    "munbon-data-api-prod-moistureLatest"
    "munbon-data-api-prod-moistureTimeseries"
    "munbon-data-api-prod-moistureStatistics"
    "munbon-data-api-prod-aosLatest"
    "munbon-data-api-prod-aosTimeseries"
    "munbon-data-api-prod-aosStatistics"
)

# Update each Lambda function
for FUNCTION in "${LAMBDA_FUNCTIONS[@]}"; do
    echo ""
    echo "📝 Updating $FUNCTION..."
    
    # Update function code
    aws lambda update-function-code \
        --function-name $FUNCTION \
        --zip-file fileb://lambda-deploy/function.zip \
        --region $REGION \
        --output json > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Code updated"
    else
        echo "❌ Failed to update code"
        continue
    fi
    
    # Wait for update to complete
    sleep 2
    
    # Update function configuration
    aws lambda update-function-configuration \
        --function-name $FUNCTION \
        --runtime $RUNTIME \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --environment Variables="{INTERNAL_API_KEY='lambda-internal-key-2025'}" \
        --region $REGION \
        --output json > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Configuration updated"
    else
        echo "❌ Failed to update configuration"
    fi
done

# Cleanup
rm -rf lambda-deploy

echo ""
echo "✅ Lambda functions updated!"
echo ""
echo "📋 Next Steps:"
echo "1. Ensure port 8081 is open on EC2 security group"
echo "2. Test the endpoints using test-updated-endpoints.sh"
echo ""