#!/bin/bash

# Setup script for External API with Kong
# This script configures Kong to route to the external API service

set -e

echo "Setting up External API with Kong..."

# Wait for Kong to be ready
echo "Waiting for Kong to be ready..."
until curl -s http://localhost:8001 > /dev/null; do
    echo "Waiting for Kong admin API..."
    sleep 5
done

echo "Kong is ready!"

# Load external API configuration
echo "Loading external API configuration..."
curl -X POST http://localhost:8001/config \
    -H "Content-Type: application/json" \
    -d @../services/external-api.yml

# Create test API keys
echo "Creating test API keys..."

# External API client
curl -X POST http://localhost:8001/consumers \
    -H "Content-Type: application/json" \
    -d '{
        "username": "test-external-client",
        "custom_id": "test-external-001"
    }'

curl -X POST http://localhost:8001/consumers/test-external-client/key-auth \
    -H "Content-Type: application/json" \
    -d '{
        "key": "external_api_test_key_123"
    }'

# Frontend client
curl -X POST http://localhost:8001/consumers \
    -H "Content-Type: application/json" \
    -d '{
        "username": "test-frontend",
        "custom_id": "test-frontend-001"
    }'

curl -X POST http://localhost:8001/consumers/test-frontend/key-auth \
    -H "Content-Type: application/json" \
    -d '{
        "key": "frontend_api_key_456"
    }'

echo "Setup complete!"
echo ""
echo "Test the setup with:"
echo ""
echo "# Public endpoint (no auth):"
echo "curl http://localhost:8000/health"
echo ""
echo "# External API endpoint:"
echo "curl -H 'x-api-key: external_api_test_key_123' http://localhost:8000/api/v1/dashboard/summary"
echo ""
echo "# Frontend endpoint:"
echo "curl -H 'x-api-key: frontend_api_key_456' http://localhost:8000/api/v1/sensors/water-level/latest"
echo ""
echo "# Or with Bearer token (for authenticated users):"
echo "curl -H 'Authorization: Bearer YOUR_JWT_TOKEN' http://localhost:8000/api/v1/analytics/water-demand"