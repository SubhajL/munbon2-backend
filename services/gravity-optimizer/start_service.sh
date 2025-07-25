#!/bin/bash

# Start Gravity Flow Optimizer Service

echo "Starting Gravity Flow Optimizer Service..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Export Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Start the service
echo "Starting service on port 3025..."
python src/main.py