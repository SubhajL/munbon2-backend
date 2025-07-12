#!/bin/bash

echo "Quick deployment for RID-MS service..."

# Create dist directory if it doesn't exist
mkdir -p dist/lambda

# Compile just the simple handler
echo "Compiling simple handler..."
npx tsc src/lambda/simple-handler.ts --outDir dist --esModuleInterop --skipLibCheck --target ES2018 --module commonjs

# Copy package.json for Lambda
cp lambda-package.json dist/package.json

# Check if serverless is installed
if ! command -v serverless &> /dev/null; then
    echo "Installing Serverless Framework..."
    npm install -g serverless
fi

# Deploy
echo "Deploying to AWS..."
serverless deploy --config serverless-simple.yml

echo "Deployment complete!"