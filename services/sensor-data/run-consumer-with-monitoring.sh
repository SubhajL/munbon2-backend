#!/bin/bash

# Kill any process on port 3004
echo "Cleaning up port 3004..."
for pid in $(lsof -ti :3004); do
    echo "Killing process $pid on port 3004"
    kill -9 $pid 2>/dev/null
done

# Wait for port to be released
sleep 2

# Start consumer
echo "Starting consumer with dual-write..."
echo "Dashboard will be available at: http://localhost:3004"
echo ""
echo "Dual-write status: ENABLED"
echo "Local DB: localhost:5433"
echo "EC2 DB: ${EC2_HOST:-43.208.201.191}:5432"
echo ""
echo "Press Ctrl+C to stop"
echo "----------------------------------------"

# Run with direct node to avoid npm wrapper issues
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data
npx ts-node --transpile-only src/cmd/consumer/main.ts