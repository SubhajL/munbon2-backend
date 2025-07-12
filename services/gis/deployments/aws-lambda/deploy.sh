#!/bin/bash

# Deploy GIS Shapefile Lambda to AWS

set -e

echo "🚀 Deploying GIS Shapefile Lambda..."

# Check if we're in the right directory
if [ ! -f "serverless.yml" ]; then
    echo "❌ Error: serverless.yml not found. Please run from the aws-lambda directory."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Deploy to AWS
echo "☁️  Deploying to AWS..."
npx serverless deploy --stage ${1:-dev}

# Get the API endpoint
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 API Endpoints:"
npx serverless info --stage ${1:-dev} | grep "POST -" || true

echo ""
echo "📝 Example usage:"
echo ""
echo "# External API (requires bearer token):"
echo "curl -X POST \\"
echo "  https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/gis/shapefile/upload \\"
echo "  -H 'Authorization: Bearer munbon-gis-shapefile' \\"
echo "  -F 'file=@path/to/shapefile.zip' \\"
echo "  -F 'waterDemandMethod=RID-MS' \\"
echo "  -F 'zone=Zone1'"
echo ""
echo "# Internal API (no auth required):"
echo "curl -X POST \\"
echo "  https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/gis/internal/shapefile/upload \\"
echo "  -F 'file=@path/to/shapefile.zip'"