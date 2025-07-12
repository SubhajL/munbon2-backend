#!/bin/bash

echo "Deploying RID-MS Lambda functions..."

# Check if serverless is installed
if ! command -v serverless &> /dev/null; then
    echo "Installing Serverless Framework..."
    npm install -g serverless
fi

# Deploy from this directory
echo "Deploying to AWS..."
serverless deploy

echo "Deployment complete!"