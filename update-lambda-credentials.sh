#!/bin/bash

# Script to update AWS credentials in Lambda functions

echo "Lambda Environment Variables Update Script"
echo "========================================="
echo ""
echo "This will update AWS credentials in your Lambda functions"
echo "Note: Lambda functions typically use IAM roles, not access keys"
echo "This script will check if any functions have hardcoded credentials"
echo ""

# List of known Lambda functions from your code
LAMBDA_FUNCTIONS=(
    "munbon-sensor-ingestion-dev-telemetry"
    "munbon-sensor-ingestion-prod-telemetry"
    "munbon-data-api-prod-waterLevelLatest"
    "munbon-data-api-prod-moistureLatest"
    "munbon-data-api-prod-aosLatest"
)

REGION="ap-southeast-1"

echo "Checking Lambda functions for environment variables..."
echo ""

for func in "${LAMBDA_FUNCTIONS[@]}"; do
    echo "Checking function: $func"
    
    # Get current environment variables
    ENV_VARS=$(aws lambda get-function-configuration \
        --function-name $func \
        --region $REGION \
        --query 'Environment.Variables' \
        --output json 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Check if AWS credentials are in environment variables
        if echo "$ENV_VARS" | grep -q "AWS_ACCESS_KEY_ID"; then
            echo "⚠️  WARNING: $func has AWS_ACCESS_KEY_ID in environment variables!"
            echo "   This is not recommended. Lambda should use IAM roles instead."
            
            read -p "Do you want to remove hardcoded credentials from this function? (y/n): " remove_creds
            
            if [ "$remove_creds" == "y" ]; then
                # Get all env vars except AWS credentials
                NEW_ENV_VARS=$(echo "$ENV_VARS" | jq 'del(.AWS_ACCESS_KEY_ID, .AWS_SECRET_ACCESS_KEY)')
                
                # Update the function
                aws lambda update-function-configuration \
                    --function-name $func \
                    --region $REGION \
                    --environment "Variables=$NEW_ENV_VARS" \
                    --output table
                    
                echo "✅ Removed hardcoded credentials from $func"
            fi
        else
            echo "✅ $func uses IAM role (recommended)"
        fi
    else
        echo "⏭️  Function $func not found or not accessible"
    fi
    echo ""
done

echo ""
echo "Lambda function check complete!"
echo ""
echo "Best Practices:"
echo "- Lambda functions should use IAM roles, not hardcoded credentials"
echo "- If your functions need AWS access, attach appropriate IAM policies to their execution role"