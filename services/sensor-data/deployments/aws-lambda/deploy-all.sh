#!/bin/bash

# Deploy both Ingestion and Data Exposure APIs to AWS Lambda
# This script deploys within AWS Free Tier limits

echo "=== Munbon AWS Lambda Deployment Script ==="
echo ""

# Check if serverless is installed
if ! command -v serverless &> /dev/null; then
    echo "Installing Serverless Framework..."
    npm install -g serverless
fi

# Function to deploy a service
deploy_service() {
    local service_name=$1
    local config_file=$2
    
    echo ""
    echo "=== Deploying $service_name ==="
    echo ""
    
    # Install dependencies
    echo "Installing dependencies..."
    npm install
    
    # Deploy to AWS
    echo "Deploying to AWS..."
    serverless deploy --config $config_file --stage prod --verbose
    
    if [ $? -eq 0 ]; then
        echo "✅ $service_name deployed successfully!"
    else
        echo "❌ $service_name deployment failed!"
        return 1
    fi
}

# Deploy Data Ingestion API
deploy_service "Data Ingestion API" "serverless.yml"

# Deploy Data Exposure API
deploy_service "Data Exposure API" "serverless-data-api.yml"

echo ""
echo "=== Deployment Summary ==="
echo ""

# Get the API endpoints
INGESTION_URL=$(serverless info --config serverless.yml --stage prod | grep "endpoint:" | head -1 | awk '{print $2}')
DATA_API_URL=$(serverless info --config serverless-data-api.yml --stage prod | grep "endpoint:" | head -1 | awk '{print $2}')

echo "📥 Data Ingestion Endpoints:"
echo "   POST $INGESTION_URL/api/v1/{token}/telemetry"
echo "   GET  $INGESTION_URL/api/v1/{token}/attributes"
echo "   POST $INGESTION_URL/api/v1/rid-ms/upload"
echo ""
echo "📤 Data Exposure Endpoints:"
echo "   GET $DATA_API_URL/api/v1/public/water-levels/latest"
echo "   GET $DATA_API_URL/api/v1/public/moisture/latest"
echo "   GET $DATA_API_URL/api/v1/public/aos/latest"
echo ""
echo "🔑 Example API Usage:"
echo "   curl -H 'X-API-Key: your-api-key' $DATA_API_URL/api/v1/public/water-levels/latest"
echo ""
echo "📊 AWS Free Tier Limits:"
echo "   - API Gateway: 1M requests/month"
echo "   - Lambda: 1M requests + 400,000 GB-seconds"
echo "   - Current usage: Check AWS Console"
echo ""

# Save endpoints to file
cat > endpoints.txt << EOF
Munbon API Endpoints (Deployed: $(date))

Data Ingestion API:
$INGESTION_URL

Data Exposure API:
$DATA_API_URL

API Keys:
- Add to EXTERNAL_API_KEYS environment variable
- Format: key1,key2,key3

Example Usage:
curl -H "X-API-Key: rid-ms-prod-xxxxx" \\
  "$DATA_API_URL/api/v1/public/water-levels/latest"
EOF

echo "✅ Deployment complete! Endpoints saved to endpoints.txt"