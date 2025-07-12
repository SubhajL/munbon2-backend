#!/bin/bash

# Setup script for RID-MS Lambda deployment
set -e

echo "Setting up RID-MS service for AWS Lambda deployment..."

# Install serverless framework globally if not installed
if ! command -v serverless &> /dev/null; then
    echo "Installing Serverless Framework globally..."
    npm install -g serverless
fi

# Install required dependencies
echo "Installing deployment dependencies..."
npm install --save-dev serverless serverless-esbuild serverless-offline

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# AWS Configuration
AWS_REGION=ap-southeast-1
AWS_PROFILE=default

# Database Configuration (will be set in Lambda environment)
POSTGIS_HOST=localhost
POSTGIS_PORT=5432
POSTGIS_DB=munbon_dev
POSTGIS_USER=postgres
POSTGIS_PASSWORD=postgres

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
EOF
fi

# Build the project
echo "Building TypeScript..."
npm run build

echo "Setup complete! You can now deploy using: npm run deploy"
echo ""
echo "Available commands:"
echo "  npm run deploy          - Deploy all functions"
echo "  npm run deploy:function - Deploy a specific function"
echo "  npm run remove         - Remove the deployment"
echo ""
echo "Make sure you have AWS credentials configured!"