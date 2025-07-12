#!/bin/bash

RENDER_URL="${RENDER_URL:-https://munbon-unified-api.onrender.com}"
API_KEY="munbon-internal-f3b89263126548"

echo "Testing Render deployment..."
echo "URL: $RENDER_URL"
echo ""

# Test health
echo "1. Testing health endpoint..."
curl -s "$RENDER_URL/health" | jq .

# Test API
echo -e "\n2. Testing API endpoint..."
curl -s "$RENDER_URL/api/v1/sensors/water-level/latest" \
  -H "x-internal-key: $API_KEY" | jq .

# Test Lambda
echo -e "\n3. Testing through Lambda..."
curl -s "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest" \
  -H "x-api-key: test-key-123" | jq .
