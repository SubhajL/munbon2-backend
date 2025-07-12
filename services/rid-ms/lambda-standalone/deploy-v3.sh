#!/bin/bash

echo "Installing Serverless Framework v3 (no account required)..."

# Uninstall v4 and install v3
npm uninstall -g serverless
npm install -g serverless@3

# Deploy
echo "Deploying to AWS..."
serverless deploy

echo "Deployment complete!"