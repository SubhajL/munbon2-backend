#!/bin/bash

echo "Deploying with AWS SAM..."

# Check if SAM is installed
if ! command -v sam &> /dev/null; then
    echo "Please install AWS SAM CLI first:"
    echo "brew install aws-sam-cli"
    exit 1
fi

# Build
sam build

# Deploy (will prompt for stack name and parameters)
sam deploy --guided

echo "Deployment complete!"