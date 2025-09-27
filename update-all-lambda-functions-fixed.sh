#!/bin/bash

# Update all Lambda functions with the fixed proxy code

echo "🚀 Updating ALL Lambda Functions with Fixed Proxy Code"
echo "===================================================="

# Configuration
REGION="ap-southeast-1"

# Create deployment package
echo "📦 Creating deployment package..."
mkdir -p lambda-deploy-fixed
cp lambda-proxy-function-fixed.js lambda-deploy-fixed/index.js
cd lambda-deploy-fixed
zip -q function.zip index.js
cd ..

# List of all Lambda functions
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
SUCCESS_COUNT=0
TOTAL=${#LAMBDA_FUNCTIONS[@]}

for FUNCTION in "${LAMBDA_FUNCTIONS[@]}"; do
    echo ""
    echo "📝 Updating $FUNCTION..."
    
    # Update function code
    aws lambda update-function-code \
        --function-name $FUNCTION \
        --zip-file fileb://lambda-deploy-fixed/function.zip \
        --region $REGION \
        --output json > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ Updated successfully"
        ((SUCCESS_COUNT++))
    else
        echo "❌ Failed to update"
    fi
done

# Cleanup
rm -rf lambda-deploy-fixed

echo ""
echo "===================================================="
echo "✅ Update complete! $SUCCESS_COUNT/$TOTAL functions updated"
echo ""
echo "🧪 Run the test script to verify all endpoints:"
echo "./test-updated-endpoints.sh"
echo ""