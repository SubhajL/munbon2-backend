#!/bin/bash

# Start ROS-GIS Integration Service
echo "Starting ROS-GIS Integration Service..."
echo "=================================="

# Set environment variables
export USE_MOCK_SERVER=false
export ROS_SERVICE_URL=http://localhost:3047
export GIS_SERVICE_URL=http://localhost:3007
export POSTGRES_URL=postgresql://postgres:P@ssw0rd123!@43.209.22.250:5432/munbon_dev
export REDIS_URL=redis://localhost:6379/2
export LOG_LEVEL=INFO

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with Python 3.11..."
    /opt/homebrew/Cellar/python@3.11/3.11.12/bin/python3.11 -m venv venv
    echo "Installing dependencies..."
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

# Activate virtual environment and start service
echo ""
echo "Configuration:"
echo "- ROS Service: $ROS_SERVICE_URL"
echo "- GIS Service: $GIS_SERVICE_URL"
echo "- Database: munbon_dev on port 5434"
echo "- Mock Server: Disabled"
echo ""
echo "Starting service on port 3022..."
./venv/bin/python src/main.py