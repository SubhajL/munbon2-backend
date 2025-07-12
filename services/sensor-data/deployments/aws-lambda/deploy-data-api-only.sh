#!/bin/bash

# Safe deployment script that ONLY deploys the data exposure API
# This will NOT affect existing ingestion endpoints

echo "=== Munbon Data API Deployment (Safe Mode) ==="
echo ""
echo "This script will ONLY deploy the data exposure API."
echo "Your existing ingestion endpoints will NOT be affected."
echo ""

# Check existing services
echo "📋 Checking existing AWS services..."
echo ""
echo "Existing Lambda functions:"
aws lambda list-functions --query "Functions[?contains(FunctionName, 'munbon-sensor-ingestion')].[FunctionName]" --output table
echo ""

read -p "Continue with data API deployment? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
npm install

# Deploy ONLY the data API
echo ""
echo "🚀 Deploying Data Exposure API..."
serverless deploy --config serverless-data-api.yml --stage prod --verbose

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Data API deployed successfully!"
    echo ""
    
    # Get the new API endpoint
    DATA_API_URL=$(serverless info --config serverless-data-api.yml --stage prod | grep "endpoint:" | head -1 | awk '{print $2}')
    
    echo "📤 New Data API Endpoints:"
    echo "   GET $DATA_API_URL/api/v1/public/water-levels/latest"
    echo "   GET $DATA_API_URL/api/v1/public/moisture/latest"
    echo "   GET $DATA_API_URL/api/v1/public/aos/latest"
    echo ""
    
    echo "✅ Your existing ingestion endpoints are UNCHANGED:"
    INGESTION_URL=$(serverless info --config serverless.yml --stage prod 2>/dev/null | grep "endpoint:" | head -1 | awk '{print $2}')
    if [ ! -z "$INGESTION_URL" ]; then
        echo "   POST $INGESTION_URL/api/v1/{token}/telemetry"
        echo "   POST $INGESTION_URL/api/v1/rid-ms/upload"
    else
        echo "   (Run 'serverless info --config serverless.yml --stage prod' to see ingestion endpoints)"
    fi
    echo ""
    
    # Save info
    cat > data-api-endpoints.txt << EOF
Munbon Data API Endpoints (Deployed: $(date))
========================================

Data Exposure API (NEW):
$DATA_API_URL

Endpoints:
- GET /api/v1/public/water-levels/latest
- GET /api/v1/public/water-levels/timeseries?date=DD/MM/YYYY
- GET /api/v1/public/water-levels/statistics?date=DD/MM/YYYY
- GET /api/v1/public/moisture/latest
- GET /api/v1/public/moisture/timeseries?date=DD/MM/YYYY
- GET /api/v1/public/moisture/statistics?date=DD/MM/YYYY
- GET /api/v1/public/aos/latest
- GET /api/v1/public/aos/timeseries?date=DD/MM/YYYY
- GET /api/v1/public/aos/statistics?date=DD/MM/YYYY

Authentication:
- Header: X-API-Key: your-api-key

Example:
curl -H "X-API-Key: rid-ms-prod-xxxxx" \\
  "$DATA_API_URL/api/v1/public/water-levels/latest"
EOF
    
    echo "📄 Endpoints saved to data-api-endpoints.txt"
    
else
    echo ""
    echo "❌ Deployment failed!"
    echo "Your existing services were NOT affected."
fi