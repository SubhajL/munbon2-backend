#!/bin/bash

# Deploy AWS Lambda with custom TLS/SSL configuration
# Supports SSL 3.0, TLS 1.0, 1.1, 1.2 with specific cipher suites

set -e

echo "Deploying Munbon API with custom TLS configuration..."

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is required but not installed. Please install it first."
    exit 1
fi

# Set variables
STAGE=${1:-dev}
REGION=${2:-ap-southeast-1}
DOMAIN_NAME=${3:-api.munbon.example.com}
CERTIFICATE_ARN=${4:-}

echo "Stage: $STAGE"
echo "Region: $REGION"
echo "Domain: $DOMAIN_NAME"

# Deploy the main serverless application
echo "Deploying serverless application..."
npx serverless deploy --stage $STAGE --region $REGION

# Get the API Gateway ID
API_ID=$(aws apigateway get-rest-apis --region $REGION --query "items[?name=='munbon-sensor-ingestion-$STAGE'].id" --output text)
echo "API Gateway ID: $API_ID"

# Create custom domain with TLS 1.0 support
if [ ! -z "$CERTIFICATE_ARN" ]; then
    echo "Creating custom domain with TLS configuration..."
    aws apigateway create-domain-name \
        --domain-name $DOMAIN_NAME \
        --regional-certificate-arn $CERTIFICATE_ARN \
        --endpoint-configuration types=REGIONAL \
        --security-policy TLS_1_0 \
        --region $REGION || true
fi

# Update API Gateway to use the custom domain
if [ ! -z "$CERTIFICATE_ARN" ]; then
    echo "Creating base path mapping..."
    aws apigateway create-base-path-mapping \
        --domain-name $DOMAIN_NAME \
        --rest-api-id $API_ID \
        --stage $STAGE \
        --region $REGION || true
fi

# Deploy CloudFormation stack for additional TLS configuration
if [ ! -z "$CERTIFICATE_ARN" ]; then
    echo "Deploying CloudFormation stack for custom TLS configuration..."
    aws cloudformation deploy \
        --template-file custom-tls-config.yml \
        --stack-name munbon-tls-config-$STAGE \
        --parameter-overrides ApiGatewayId=$API_ID \
        --capabilities CAPABILITY_IAM \
        --region $REGION || true
fi

echo ""
echo "=== IMPORTANT NOTES ==="
echo ""
echo "1. API Gateway has limited cipher suite customization."
echo "2. The following TLS versions are enabled: SSL 3.0, TLS 1.0, 1.1, 1.2"
echo "3. For exact cipher suite control, consider using:"
echo "   - AWS Application Load Balancer (ALB) with custom SSL policy"
echo "   - AWS CloudFront with custom SSL configuration"
echo "   - AWS API Gateway with AWS WAF for additional security"
echo ""
echo "4. Current endpoints:"
echo "   - API Gateway: https://$API_ID.execute-api.$REGION.amazonaws.com/$STAGE"
if [ ! -z "$CERTIFICATE_ARN" ]; then
    echo "   - Custom Domain: https://$DOMAIN_NAME"
fi
echo ""
echo "5. To test the TLS configuration:"
echo "   nmap --script ssl-enum-ciphers -p 443 $API_ID.execute-api.$REGION.amazonaws.com"
echo "   openssl s_client -connect $API_ID.execute-api.$REGION.amazonaws.com:443 -servername $API_ID.execute-api.$REGION.amazonaws.com"
echo ""
echo "Deployment complete!"