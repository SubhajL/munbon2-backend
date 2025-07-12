#!/bin/bash

echo "Fixing Serverless deployment..."
echo "==============================="

# Install the missing plugin
echo "Installing serverless-apigw-binary plugin..."
npm install --save-dev serverless-apigw-binary

# Also install any other missing dependencies
echo "Installing all dependencies..."
npm install

# Now try to deploy
echo ""
echo "Dependencies installed. Now deploying..."
serverless deploy

echo ""
echo "If deployment succeeds, test SHAPE upload with:"
echo "curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload \\"
echo "  -H \"Authorization: Bearer munbon-ridms-shape\" \\"
echo "  -F \"file=@test.zip\""