#!/bin/bash

# Start the SQS consumer with proper environment and logging

cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data

# Kill any existing consumer on port 3002
lsof -ti :3002 | xargs kill -9 2>/dev/null

echo "Starting SQS Consumer..."
echo "========================"
echo "Time: $(date)"
echo "Dashboard will be available at: http://localhost:3002"
echo ""

# Run the consumer with error handling
npm run consumer 2>&1 | tee consumer-output.log | grep -E "(Processing|ERROR|Connected|Messages processed|shape-file)"