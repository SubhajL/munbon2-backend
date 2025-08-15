#!/bin/bash
# Run consumer with transpile-only to avoid TypeScript compilation cache issues

# Change to the script's directory
cd "$(dirname "$0")"

# Check if .env.local exists and load it
if [ -f .env.local ]; then
    echo "Loading environment from .env.local"
    export $(cat .env.local | grep -v '^#' | xargs)
fi

# Run the consumer
echo "Starting consumer with dual-write enabled: $ENABLE_DUAL_WRITE"
npx ts-node --transpile-only src/cmd/consumer/main.ts