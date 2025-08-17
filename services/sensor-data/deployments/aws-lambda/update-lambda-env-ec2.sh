#!/bin/bash

# Update Lambda environment variables for Munbon Data API to use EC2 database

echo "=== Updating Lambda Environment Variables for EC2 Database ==="
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
            DB_HOST='${EC2_HOST:-43.208.201.191}',
            DB_PORT='5432',
            DB_NAME='sensor_data',
            DB_USER='postgres',
            DB_PASSWORD='P@ssw0rd123!',
            EXTERNAL_API_KEYS='rid-ms-prod-1234567890abcdef,rid-ms-dev-abcdef1234567890,tmd-weather-123abc456def789,test-key-123',
            STAGE='$STAGE'
        }" \
        --region ap-southeast-1 \
        2>&1
    
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
echo "Lambda functions are now configured to connect to EC2 PostgreSQL database:"
echo "- Host: ${EC2_HOST:-43.208.201.191}"
echo "- Port: 5432"
echo "- Database: sensor_data"
echo ""
echo "Note: Make sure the EC2 security group allows connections from Lambda functions."
echo "You may need to:"
echo "1. Add Lambda's public IP to EC2 security group"
echo "2. Or use VPC configuration if Lambda and EC2 are in the same VPC"