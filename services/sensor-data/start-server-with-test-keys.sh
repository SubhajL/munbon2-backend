#!/bin/bash

# Start the sensor data service with test API keys

echo "=== Starting Sensor Data Service with Test API Keys ==="

# Set environment variables
export NODE_ENV=development
export PORT=3000

# Database configuration
export TIMESCALE_HOST=localhost
export TIMESCALE_PORT=5433
export TIMESCALE_DB=sensor_data
export TIMESCALE_USER=postgres
export TIMESCALE_PASSWORD=postgres

# Test API keys for external access
export EXTERNAL_API_KEYS="rid-ms-dev-1234567890abcdef,tmd-weather-abcdef1234567890,test-key-fedcba0987654321"

# Valid tokens for sensor data ingestion
export VALID_TOKENS="munbon-ridr-water-level:water-level,munbon-m2m-moisture:moisture"

# Admin token
export ADMIN_TOKEN="admin-secret-token"

# SQS configuration (for consumer)
export AWS_REGION=ap-southeast-1
export SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue

echo ""
echo "Configuration:"
echo "- API Port: 3000"
echo "- TimescaleDB: localhost:5433"
echo "- Test API Keys:"
echo "  - rid-ms-dev-1234567890abcdef (RID-MS Development)"
echo "  - tmd-weather-abcdef1234567890 (TMD Weather)"
echo "  - test-key-fedcba0987654321 (Testing)"
echo ""

# Check if npm start script exists
if [ -f "package.json" ]; then
    echo "Starting server..."
    npm start
else
    echo "Error: package.json not found. Are you in the correct directory?"
    echo "Current directory: $(pwd)"
    exit 1
fi