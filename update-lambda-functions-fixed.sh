#!/bin/bash

# Script to update Lambda functions with fixed proxy code (no API key validation)

echo "🚀 Updating Lambda Functions with Fixed Proxy Code"
echo "================================================="

# Configuration
REGION="ap-southeast-1"

# Create deployment package
echo "📦 Creating deployment package..."
mkdir -p lambda-deploy-fixed
cp lambda-proxy-function-fixed.js lambda-deploy-fixed/index.js
cd lambda-deploy-fixed
zip -q function.zip index.js
cd ..

# Update just one function first to test
FUNCTION="munbon-data-api-prod-waterLevelLatest"

echo ""
echo "📝 Updating $FUNCTION with fixed code..."

# Update function code
aws lambda update-function-code \
    --function-name $FUNCTION \
    --zip-file fileb://lambda-deploy-fixed/function.zip \
    --region $REGION \
    --output json > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ Code updated successfully"
else
    echo "❌ Failed to update code"
    exit 1
fi

# Wait for update to complete
echo "⏳ Waiting for function to update..."
sleep 3

# Cleanup
rm -rf lambda-deploy-fixed

echo ""
echo "✅ Test function updated!"
echo ""
echo "🧪 Test the endpoint now:"
echo "curl -H \"x-api-key: rid-ms-prod-key1\" \\"
echo "  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest"
echo ""
echo "📋 Check logs:"
echo "aws logs tail /aws/lambda/$FUNCTION --region $REGION --follow"
echo ""