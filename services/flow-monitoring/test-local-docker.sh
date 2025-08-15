#!/bin/bash

# Test Flow Monitoring Service locally with Docker
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Testing Flow Monitoring Service locally...${NC}"

# Build the image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t flow-monitoring-test:latest .

# Run the container with test environment
echo -e "${YELLOW}Starting container...${NC}"
docker run -d \
  --name flow-monitoring-test \
  -p 3011:3011 \
  -e PORT=3011 \
  -e SERVICE_NAME=flow-monitoring \
  -e ENVIRONMENT=development \
  -e LOG_LEVEL=DEBUG \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5434/munbon_dev \
  -e TIMESCALE_URL=postgresql://postgres:postgres@host.docker.internal:5433/sensor_data \
  -e REDIS_URL=redis://host.docker.internal:6379/12 \
  -e INFLUXDB_URL=http://host.docker.internal:8086 \
  -e CORS_ORIGINS="*" \
  -v $(pwd)/src/munbon_network_final.json:/app/src/munbon_network_final.json:ro \
  -v $(pwd)/canal_geometry_template.json:/app/canal_geometry_template.json:ro \
  flow-monitoring-test:latest

# Wait for service to start
echo -e "${YELLOW}Waiting for service to start...${NC}"
sleep 10

# Check if container is running
if docker ps | grep -q flow-monitoring-test; then
    echo -e "${GREEN}Container is running${NC}"
else
    echo -e "${RED}Container failed to start${NC}"
    docker logs flow-monitoring-test
    docker rm flow-monitoring-test
    exit 1
fi

# Test health endpoint
echo -e "${YELLOW}Testing health endpoint...${NC}"
if curl -f http://localhost:3011/health; then
    echo -e "\n${GREEN}Health check passed${NC}"
else
    echo -e "\n${RED}Health check failed${NC}"
    docker logs flow-monitoring-test
fi

# Test API endpoints
echo -e "\n${YELLOW}Testing API endpoints...${NC}"

# Root endpoint
echo -e "\nRoot endpoint:"
curl http://localhost:3011/

# API docs
echo -e "\n\nAPI documentation available at:"
echo "http://localhost:3011/docs"

# Show logs
echo -e "\n${YELLOW}Recent logs:${NC}"
docker logs --tail 20 flow-monitoring-test

# Cleanup instructions
echo -e "\n${GREEN}Service is running at http://localhost:3011${NC}"
echo -e "To view logs: ${YELLOW}docker logs -f flow-monitoring-test${NC}"
echo -e "To stop: ${YELLOW}docker stop flow-monitoring-test && docker rm flow-monitoring-test${NC}"