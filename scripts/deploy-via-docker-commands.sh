#!/bin/bash

# Direct Docker deployment commands for EC2
# Run these commands on the EC2 instance

echo "=== EC2 Docker Deployment ==="
echo ""

# Pull latest images (if using Docker Hub)
# docker pull munbon/sensor-data:latest
# docker pull munbon/auth:latest

# Stop existing containers
docker stop munbon-sensor-data munbon-sensor-data-consumer munbon-auth munbon-gis || true
docker rm munbon-sensor-data munbon-sensor-data-consumer munbon-auth munbon-gis || true

# Start PostgreSQL if not running
docker ps | grep postgres || docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=P@ssw0rd123! \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:13-alpine

# Start Redis if not running  
docker ps | grep redis || docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:6-alpine

# Wait for PostgreSQL to be ready
sleep 5

# Run sensor-data service
docker run -d \
  --name munbon-sensor-data \
  --network host \
  -e NODE_ENV=production \
  -e PORT=3001 \
  -e TIMESCALE_HOST=localhost \
  -e TIMESCALE_PORT=5432 \
  -e TIMESCALE_DB=sensor_data \
  -e TIMESCALE_USER=postgres \
  -e TIMESCALE_PASSWORD=P@ssw0rd123! \
  -e REDIS_HOST=localhost \
  -e REDIS_PORT=6379 \
  -v /home/ubuntu/munbon2-backend/services/sensor-data:/app \
  -w /app \
  node:18-alpine \
  sh -c "npm install && npm start"

# Run consumer service
docker run -d \
  --name munbon-sensor-data-consumer \
  --network host \
  -e NODE_ENV=production \
  -e CONSUMER_PORT=3002 \
  -e TIMESCALE_HOST=localhost \
  -e TIMESCALE_PORT=5432 \
  -e TIMESCALE_DB=sensor_data \
  -e TIMESCALE_USER=postgres \
  -e TIMESCALE_PASSWORD=P@ssw0rd123! \
  -e AWS_REGION=ap-southeast-1 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  -v /home/ubuntu/munbon2-backend/services/sensor-data:/app \
  -w /app \
  node:18-alpine \
  sh -c "npm install && npm run consumer:prod"

echo ""
echo "Services deployed!"
echo "Check status: docker ps"
echo "View logs: docker logs -f munbon-sensor-data"
