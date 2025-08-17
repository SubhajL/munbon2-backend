#!/bin/bash
# Source this file to load credentials from environment
# Usage: source ./load-credentials.sh

echo "Loading credentials from environment..."
echo "Make sure you have set:"
echo "  export POSTGRES_PASSWORD='your-password'"
echo "  export JWT_SECRET='your-jwt-secret'"
echo "  export REDIS_PASSWORD='your-redis-password'"

# Database configurations use environment variables
export DATABASE_URL="postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}@${EC2_HOST:-43.208.201.191}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-munbon_dev}"
export TIMESCALE_URL="postgresql://${TIMESCALE_USER:-postgres}:${POSTGRES_PASSWORD}@${EC2_HOST:-43.208.201.191}:${TIMESCALE_PORT:-5432}/${TIMESCALE_DB:-sensor_data}"
