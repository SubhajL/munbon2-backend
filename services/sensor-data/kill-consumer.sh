#!/bin/bash

echo "🛑 Stopping all consumer processes..."

# Kill all processes using port 3004
for pid in $(lsof -ti :3004); do
    echo "  Killing process $pid on port 3004"
    kill -9 $pid 2>/dev/null
done

# Kill all consumer processes by name
pids=$(ps aux | grep "consumer/main.ts" | grep -v grep | awk '{print $2}')
if [ -n "$pids" ]; then
    echo "  Killing consumer processes: $pids"
    echo $pids | xargs kill -9 2>/dev/null
fi

# Wait for cleanup
sleep 2

# Verify
if lsof -i :3004 >/dev/null 2>&1; then
    echo "❌ Port 3004 is still in use!"
    lsof -i :3004
else
    echo "✅ Port 3004 is free"
fi