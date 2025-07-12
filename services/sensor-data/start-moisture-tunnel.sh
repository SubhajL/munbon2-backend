#!/bin/bash

# Start the moisture tunnel using PM2

echo "🌱 Starting Munbon Moisture Tunnel..."

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 not found. Please install it: npm install -g pm2"
    exit 1
fi

# Start the tunnel
pm2 start /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/pm2-moisture-tunnel.json

# Save PM2 configuration
pm2 save

# Show status
pm2 status munbon-moisture-tunnel

echo ""
echo "✅ Moisture tunnel started!"
echo ""
echo "📊 View logs with: pm2 logs munbon-moisture-tunnel"
echo "🔄 Restart with: pm2 restart munbon-moisture-tunnel"
echo "🛑 Stop with: pm2 stop munbon-moisture-tunnel"
echo ""
echo "🌐 Tunnel URLs:"
echo "   - https://munbon-moisture.beautifyai.io"
echo "   - https://munbon-moisture-health.beautifyai.io/health"
