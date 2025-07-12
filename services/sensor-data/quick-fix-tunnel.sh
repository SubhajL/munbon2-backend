#!/bin/bash

echo "🔄 Quick Tunnel Fix Script"
echo "========================="

# Get current tunnel URL from PM2 logs
TUNNEL_URL=$(pm2 logs quick-tunnel --lines 50 --nostream | grep -E "https://.*trycloudflare.com" | tail -1 | grep -oE "https://[a-z-]+\.trycloudflare\.com")

if [ -z "$TUNNEL_URL" ]; then
    echo "❌ No tunnel URL found. Make sure quick-tunnel is running."
    exit 1
fi

echo "✅ Found tunnel URL: $TUNNEL_URL"
echo ""
echo "Deploying to Lambda..."

cd deployments/aws-lambda
TUNNEL_URL=$TUNNEL_URL npx serverless deploy --config serverless-data-api.yml --stage prod --region ap-southeast-1

echo ""
echo "✅ Done! Test with:"
echo "curl -H \"X-API-Key: rid-ms-prod-key1\" https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest"