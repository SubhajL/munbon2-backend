#!/bin/bash

echo "Setting up Gravity Optimizer Service..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Setup complete!"
echo ""
echo "To run the service:"
echo "  source venv/bin/activate"
echo "  python -m uvicorn src.main:app --host 0.0.0.0 --port 3020 --reload"
echo ""
echo "To run tests:"
echo "  source venv/bin/activate"
echo "  python test_optimizer.py"