#!/bin/bash

# Simple script to start HTTP server on EC2

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Compile TypeScript
echo "Compiling TypeScript..."
npx tsc src/simple-http-server.ts --outDir dist --esModuleInterop --resolveJsonModule

# Set environment variables
export HTTP_PORT=8080
export AWS_REGION=ap-southeast-1
export SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue

# Start with PM2
echo "Starting HTTP server with PM2..."
pm2 start dist/simple-http-server.js --name "moisture-http" --log-date-format "YYYY-MM-DD HH:mm:ss"

echo "✅ HTTP server started on port 8080"
echo "📡 Endpoint: http://ec2-43.209.22.250.ap-southeast-7.compute.amazonaws.com:8080/api/sensor-data/moisture/munbon-m2m-moisture"