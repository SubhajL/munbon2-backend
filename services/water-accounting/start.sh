#!/bin/bash
cd "$(dirname "$0")"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 3020
