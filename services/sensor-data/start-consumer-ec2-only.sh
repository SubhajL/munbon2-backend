#!/bin/bash

# Export environment variables to use only EC2 database
export NODE_ENV=production
export ENABLE_DUAL_WRITE=false
export TIMESCALE_HOST=43.209.22.250
export TIMESCALE_PORT=5432
export TIMESCALE_DB=sensor_data
export TIMESCALE_USER=postgres
export TIMESCALE_PASSWORD=P@ssw0rd123!
export EC2_DB_HOST=43.209.22.250
export EC2_DB_PORT=5432
export EC2_DB_NAME=sensor_data
export EC2_DB_USER=postgres
export EC2_DB_PASSWORD=P@ssw0rd123!
export AWS_REGION=ap-southeast-1
export SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue

echo "Starting consumer with EC2-only configuration..."
npm run consumer
