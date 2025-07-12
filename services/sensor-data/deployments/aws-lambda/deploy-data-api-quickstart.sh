#!/bin/bash

# Quick deployment script for Munbon Public Data API

echo "=== Munbon Public Data API Deployment ==="
echo ""

# Check if we're in the right directory
if [ ! -f "serverless-data-api.yml" ]; then
    echo "Error: serverless-data-api.yml not found!"
    echo "Please run this script from the deployments/aws-lambda directory"
    exit 1
fi

# Set deployment stage
STAGE="${1:-dev}"
echo "Deploying to stage: $STAGE"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS credentials not configured!"
    echo "Please run: aws configure"
    exit 1
fi

# Create utils directory if it doesn't exist
mkdir -p utils

# Create a simple logger for Lambda
cat > utils/logger.ts << 'EOF'
export const logger = {
  info: (message: string, data?: any) => {
    console.log(JSON.stringify({ level: 'info', message, data, timestamp: new Date().toISOString() }));
  },
  error: (message: string, error?: any) => {
    console.error(JSON.stringify({ level: 'error', message, error: error?.message || error, timestamp: new Date().toISOString() }));
  },
  warn: (message: string, data?: any) => {
    console.warn(JSON.stringify({ level: 'warn', message, data, timestamp: new Date().toISOString() }));
  },
  debug: (message: string, data?: any) => {
    console.log(JSON.stringify({ level: 'debug', message, data, timestamp: new Date().toISOString() }));
  }
};
EOF

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Build TypeScript
echo "Building TypeScript..."
npx tsc --init --target es2020 --module commonjs --outDir dist --strict false --esModuleInterop true --skipLibCheck true --forceConsistentCasingInFileNames true 2>/dev/null
npx tsc

# Deploy
echo ""
echo "Deploying to AWS..."
serverless deploy --config serverless-data-api.yml --stage $STAGE

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "To test the deployed API:"
echo "1. Copy the API Gateway URL from above"
echo "2. Test with: curl -H 'X-API-Key: your-key' https://[api-id].execute-api.ap-southeast-1.amazonaws.com/$STAGE/api/v1/public/water-levels/latest"