#!/bin/bash

echo "Smart Farm Water Control - Quick Start"
echo "====================================="
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from production template..."
    cp .env.production .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and add your credentials:"
    echo "   - TIMESCALE_PASSWORD"
    echo "   - MSSQL_USER and MSSQL_PASSWORD"
    echo "   - ROS_API_KEY"
    echo "   - SENSOR_DATA_API_KEY"
    echo ""
    echo "After adding credentials, run this script again."
    exit 1
fi

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Run setup verification
echo ""
echo "1. Verifying database connections..."
echo "-----------------------------------"
node scripts/setup-databases.js

echo ""
echo "2. Testing ROS integration..."
echo "-----------------------------"
node scripts/test-ros-integration.js

echo ""
echo "3. Testing sensor data integration..."
echo "------------------------------------"
node scripts/test-sensor-integration.js

echo ""
echo "Ready to start?"
echo "==============="
echo ""
echo "If all tests passed, you can start the service with:"
echo "  npm start"
echo ""
echo "For development with auto-reload:"
echo "  npm run dev"
echo ""
echo "To run tests:"
echo "  npm test"