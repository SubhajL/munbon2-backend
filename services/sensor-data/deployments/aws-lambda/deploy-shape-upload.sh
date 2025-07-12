#!/bin/bash

echo "Deploying SHAPE file upload function..."
echo "======================================="

# Check current directory
if [ ! -f "serverless.yml" ]; then
    echo "Error: serverless.yml not found. Please run from aws-lambda directory"
    exit 1
fi

# First, let's check what functions are defined
echo "Functions defined in serverless.yml:"
grep -A2 "^functions:" serverless.yml
echo ""

# Deploy the fileUpload function
echo "Deploying fileUpload function..."
serverless deploy function -f fileUpload

# Or deploy everything to ensure all functions are up to date
echo ""
echo "To deploy all functions with updated tokens, run:"
echo "serverless deploy"

echo ""
echo "After deployment, test with:"
echo "curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload \\"
echo "  -H \"Authorization: Bearer munbon-ridms-shape\" \\"
echo "  -F \"file=@test.zip\""