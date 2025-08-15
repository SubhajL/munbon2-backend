#!/bin/bash

# Script to add HTTP endpoint to existing API Gateway
# This creates a custom domain with HTTP support

STAGE=${1:-dev}
DOMAIN_NAME="munbon-sensors-http.yourdomain.com"

echo "Creating HTTP endpoint for stage: $STAGE"

# Get the existing API Gateway ID
API_ID=$(aws apigateway get-rest-apis --region ap-southeast-1 \
  --query "items[?name=='${STAGE}-munbon-sensor-ingestion'].id" \
  --output text)

echo "Found API Gateway: $API_ID"

# Create HTTP API that forwards to the same Lambda
cat > http-api-template.json << EOF
{
  "Name": "munbon-sensor-http-${STAGE}",
  "ProtocolType": "HTTP",
  "RouteSelectionExpression": "\$request.method \$request.path",
  "DisableSchemaValidation": true,
  "Description": "HTTP endpoint for legacy sensors"
}
EOF

# Create the HTTP API
HTTP_API_ID=$(aws apigatewayv2 create-api \
  --cli-input-json file://http-api-template.json \
  --region ap-southeast-1 \
  --query "ApiId" \
  --output text)

echo "Created HTTP API: $HTTP_API_ID"

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function \
  --function-name munbon-sensor-ingestion-${STAGE}-telemetry \
  --region ap-southeast-1 \
  --query "Configuration.FunctionArn" \
  --output text)

echo "Lambda ARN: $LAMBDA_ARN"

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id $HTTP_API_ID \
  --integration-type AWS_PROXY \
  --integration-uri $LAMBDA_ARN \
  --payload-format-version "2.0" \
  --region ap-southeast-1 \
  --query "IntegrationId" \
  --output text)

echo "Created integration: $INTEGRATION_ID"

# Create routes
aws apigatewayv2 create-route \
  --api-id $HTTP_API_ID \
  --route-key "POST /moisture/{token}" \
  --target "integrations/$INTEGRATION_ID" \
  --region ap-southeast-1

aws apigatewayv2 create-route \
  --api-id $HTTP_API_ID \
  --route-key "POST /water-level/{token}" \
  --target "integrations/$INTEGRATION_ID" \
  --region ap-southeast-1

# Create deployment
aws apigatewayv2 create-deployment \
  --api-id $HTTP_API_ID \
  --stage-name $STAGE \
  --region ap-southeast-1

# Add Lambda permission
aws lambda add-permission \
  --function-name munbon-sensor-ingestion-${STAGE}-telemetry \
  --statement-id "AllowHTTPAPIInvoke" \
  --action "lambda:InvokeFunction" \
  --principal "apigateway.amazonaws.com" \
  --source-arn "arn:aws:execute-api:ap-southeast-1:108728974441:${HTTP_API_ID}/*/*" \
  --region ap-southeast-1

echo "HTTP API Endpoint: https://${HTTP_API_ID}.execute-api.ap-southeast-1.amazonaws.com/${STAGE}"
echo ""
echo "Your legacy devices can now use:"
echo "http://${HTTP_API_ID}.execute-api.ap-southeast-1.amazonaws.com/${STAGE}/moisture/munbon-m2m-moisture"

# Clean up
rm http-api-template.json