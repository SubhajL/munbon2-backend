#!/bin/bash
echo "Deploying Data API with Proxy to AWS Lambda..."

# Source environment variables
if [ -f .env.tunnel ]; then
    export $(cat .env.tunnel | grep -v '#' | xargs)
fi

# Deploy the Data API with proxy
serverless deploy --config serverless-data-api.yml --stage prod

echo "Deployment complete!"
echo ""
echo "API Gateway URLs:"
echo "=================="
echo "Water Level Latest: https://26ikiexzlc.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest"
echo "Moisture Latest: https://26ikiexzlc.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest"
echo "AOS Latest: https://26ikiexzlc.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest"
echo ""
echo "Testing with: X-API-Key: rid-ms-prod-key1"