#!/bin/bash

# Update Lambda environment variables for Munbon Data API

echo "=== Updating Lambda Environment Variables ==="
echo ""

STAGE="${1:-dev}"
SERVICE="munbon-data-api"

# Function to update environment variables for a Lambda function
update_function_env() {
    local function_name=$1
    echo "Updating: $function_name"
    
    aws lambda update-function-configuration \
        --function-name "$function_name" \
        --environment Variables="{
            DB_HOST='localhost',
            DB_PORT='5433',
            DB_NAME='sensor_data',
            DB_USER='postgres',
            DB_PASSWORD='postgres',
            EXTERNAL_API_KEYS='rid-ms-prod-1234567890abcdef,rid-ms-dev-abcdef1234567890,tmd-weather-123abc456def789,test-key-123',
            STAGE='$STAGE'
        }" \
        --region ap-southeast-1 \
        > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ Updated $function_name"
    else
        echo "❌ Failed to update $function_name"
    fi
}

# List of functions to update
functions=(
    "${SERVICE}-${STAGE}-waterLevelLatest"
    "${SERVICE}-${STAGE}-waterLevelTimeseries"
    "${SERVICE}-${STAGE}-waterLevelStatistics"
    "${SERVICE}-${STAGE}-moistureLatest"
    "${SERVICE}-${STAGE}-moistureTimeseries"
    "${SERVICE}-${STAGE}-moistureStatistics"
    "${SERVICE}-${STAGE}-aosLatest"
    "${SERVICE}-${STAGE}-aosTimeseries"
    "${SERVICE}-${STAGE}-aosStatistics"
    "${SERVICE}-${STAGE}-corsOptions"
)

echo "Updating environment variables for all functions..."
echo ""

for func in "${functions[@]}"; do
    update_function_env "$func"
done

echo ""
echo "=== Update Complete ==="
echo ""
echo "Note: The Lambda functions still need:"
echo "1. VPC configuration to access local database"
echo "2. Or use RDS/Aurora Serverless for database"
echo "3. Or use API Gateway VPC Link to access local services"
echo ""
echo "For testing without database, you can modify the Lambda handlers to return mock data."