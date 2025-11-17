#!/bin/bash
cd "$(dirname "$0")"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  export $(cat .env | grep -v '^#' | xargs)
fi

# Override for PM2 deployment - disable mock server
export USE_MOCK_SERVER=false

# Use PORT from environment or default to 3022
PORT=${PORT:-3022}

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port $PORT
