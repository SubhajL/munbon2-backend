#!/bin/bash

# Package Lambda functions for RID-MS deployment

echo "📦 Packaging RID-MS Lambda functions..."

# Create deployment directory
mkdir -p lambda-packages

# Package shapefile ingestion Lambda
echo "Building shapefile-ingestion Lambda..."
cd ../../src/lambda
zip -r ../../deployments/aws/lambda-packages/shapefile-ingestion.zip shapefile-ingestion.ts
cd ../../deployments/aws

# Package API Gateway handler Lambda
echo "Building api-gateway-handler Lambda..."
cd ../../src/lambda
zip -r ../../deployments/aws/lambda-packages/api-gateway-handler.zip api-gateway-handler.ts
cd ../../deployments/aws

# Install production dependencies for Lambda
echo "Installing Lambda dependencies..."
cd lambda-packages
npm init -y
npm install --production @aws-sdk/client-s3 @aws-sdk/client-dynamodb @turf/turf proj4 shapefile
zip -r shapefile-ingestion.zip node_modules
zip -r api-gateway-handler.zip node_modules
cd ..

echo "✅ Lambda functions packaged successfully"