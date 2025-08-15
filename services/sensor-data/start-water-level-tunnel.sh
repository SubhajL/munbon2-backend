#!/bin/bash

# Start the water level tunnel using PM2

echo "💧 Starting Munbon Water Level Tunnel..."

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 not found. Please install it: npm install -g pm2"
    exit 1
fi

# Create PM2 config for water level tunnel
cat > pm2-water-level-tunnel.json << EOF
{
  "apps": [{
    "name": "munbon-water-level-tunnel",
    "script": "bash",
    "args": "-c 'cloudflared tunnel --url http://localhost:3003 --hostname munbon-water-level.beautifyai.io 2>&1 | tee logs/water-level-tunnel.log'",
    "cwd": "/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data",
    "interpreter": "/bin/bash",
    "watch": false,
    "autorestart": true,
    "max_restarts": 10,
    "min_uptime": "10s",
    "error_file": "logs/water-level-tunnel-error.log",
    "out_file": "logs/water-level-tunnel-out.log"
  }]
}
EOF

# Start the tunnel
pm2 start pm2-water-level-tunnel.json

# Save PM2 configuration
pm2 save

# Show status
pm2 status munbon-water-level-tunnel

echo ""
echo "✅ Water level tunnel started!"
echo ""
echo "📊 View logs with: pm2 logs munbon-water-level-tunnel"
echo "🔄 Restart with: pm2 restart munbon-water-level-tunnel"
echo "🛑 Stop with: pm2 stop munbon-water-level-tunnel"
echo ""
echo "🌐 Tunnel URLs:"
echo "   - https://munbon-water-level.beautifyai.io"
echo "   - Endpoint: POST https://munbon-water-level.beautifyai.io/api/v1/munbon-water-level/telemetry"
echo ""
echo "📡 Example usage:"
echo '   curl -X POST https://munbon-water-level.beautifyai.io/api/v1/munbon-water-level/telemetry \'
echo '     -H "Content-Type: application/json" \'
echo '     -d @water-level-sample.json'