#!/bin/bash

# Script to start mock API server with external access

echo "🚀 Starting Mock API Server for External Access"
echo "================================================"

# Get local IP address
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')

echo "📡 Mock server will be available at:"
echo "   - Local: http://localhost:4010"
echo "   - Network: http://$LOCAL_IP:4010"
echo ""

# Check if ngrok is installed
if command -v ngrok &> /dev/null; then
    echo "💡 To expose publicly, run in another terminal:"
    echo "   ngrok http 4010"
    echo ""
fi

echo "📋 Example endpoints:"
echo "   GET http://$LOCAL_IP:4010/api/v1/sensors"
echo "   GET http://$LOCAL_IP:4010/api/v1/telemetry/latest"
echo ""

echo "🔥 Starting Prism mock server on 0.0.0.0:4010..."
echo "Press Ctrl+C to stop"
echo ""

# Start the mock server binding to all interfaces
npx prism mock openapi/sensor-data-service.yaml -p 4010 -h 0.0.0.0