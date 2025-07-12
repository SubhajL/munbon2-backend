#!/bin/bash
echo "Testing Data API Proxy Setup..."
echo "=============================="
echo ""

# Test water level latest
echo "1. Testing Water Level Latest:"
echo "------------------------------"
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest

echo -e "\n\n2. Testing Moisture Latest:"
echo "------------------------------"
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest

echo -e "\n\n3. Testing AOS Latest:"
echo "------------------------------"  
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest

echo -e "\n\n4. Testing Invalid API Key:"
echo "------------------------------"
curl -H "X-API-Key: invalid-key" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest

echo -e "\n\nTest Complete!"