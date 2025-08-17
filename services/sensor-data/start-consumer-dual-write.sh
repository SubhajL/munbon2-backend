#!/bin/bash

echo "🚀 Starting Sensor Data Consumer with Dual-Write"
echo "=============================================="

# Change to the script's directory
cd "$(dirname "$0")"

# Kill any existing consumer processes
echo "🛑 Stopping any existing consumer processes..."
lsof -i :3004 2>/dev/null | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null
ps aux | grep "consumer/main.ts" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

# Wait a moment for ports to be released
sleep 2

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "❌ Error: .env.local not found!"
    echo "Please ensure .env.local exists with dual-write configuration"
    exit 1
fi

# Check if dual-write is enabled
if grep -q "ENABLE_DUAL_WRITE=true" .env.local; then
    echo "✅ Dual-write is ENABLED in .env.local"
else
    echo "⚠️  Warning: Dual-write is NOT enabled in .env.local"
    echo "Add 'ENABLE_DUAL_WRITE=true' to enable dual-write"
fi

# Display connection info
echo ""
echo "📊 Database Connections:"
echo "  Local: localhost:5433 (munbon_timescale)"
echo "  EC2:   ${EC2_HOST:-43.208.201.191}:5432 (sensor_data)"
echo ""

# Start the consumer
echo "🔄 Starting consumer..."
npm run consumer