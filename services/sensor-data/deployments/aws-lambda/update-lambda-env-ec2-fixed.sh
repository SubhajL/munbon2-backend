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
        --environment 'Variables={DB_HOST="${EC2_HOST:-43.208.201.191}",DB_PORT="5432",DB_NAME="sensor_data",DB_USER="postgres",DB_PASSWORD="P@ssw0rd123!",EXTERNAL_API_KEYS="rid-ms-prod-1234567890abcdef,rid-ms-dev-abcdef1234567890,tmd-weather-123abc456def789,test-key-123",STAGE="'$STAGE'"}' \
        --region ap-southeast-1 \
        > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ Updated $function_name"
    else
        echo "❌ Failed to update $function_name"
    fi
}

# Update both dev and prod functions
echo "Updating DEV environment functions..."
echo ""

# DEV functions
dev_functions=(
    "munbon-data-api-dev-waterLevelLatest"
    "munbon-data-api-dev-waterLevelTimeseries"
    "munbon-data-api-dev-waterLevelStatistics"
    "munbon-data-api-dev-moistureLatest"
    "munbon-data-api-dev-moistureTimeseries"
    "munbon-data-api-dev-moistureStatistics"
    "munbon-data-api-dev-aosLatest"
    "munbon-data-api-dev-aosTimeseries"
    "munbon-data-api-dev-aosStatistics"
    "munbon-data-api-dev-corsOptions"
)

for func in "${dev_functions[@]}"; do
    update_function_env "$func"
done

echo ""
echo "Updating PROD environment functions..."
echo ""

# PROD functions
STAGE="prod"
prod_functions=(
    "munbon-data-api-prod-waterLevelLatest"
    "munbon-data-api-prod-waterLevelTimeseries"
    "munbon-data-api-prod-waterLevelStatistics"
    "munbon-data-api-prod-moistureLatest"
    "munbon-data-api-prod-moistureTimeseries"
    "munbon-data-api-prod-moistureStatistics"
    "munbon-data-api-prod-aosLatest"
    "munbon-data-api-prod-aosTimeseries"
    "munbon-data-api-prod-aosStatistics"
    "munbon-data-api-prod-corsOptions"
)

for func in "${prod_functions[@]}"; do
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