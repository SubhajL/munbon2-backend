#!/bin/bash

# Setup script for Munbon Moisture Sensor Tunnel
# This creates a permanent Cloudflare tunnel for moisture sensor data with legacy TLS support

set -e

echo "🌱 Munbon Moisture Sensor Tunnel Setup"
echo "====================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}❌ cloudflared not found. Please install it first:${NC}"
    echo "brew install cloudflared"
    exit 1
fi

# Check if logged in to Cloudflare
if ! cloudflared tunnel list &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Cloudflare. Please login:${NC}"
    cloudflared tunnel login
fi

# Configuration
TUNNEL_NAME="munbon-moisture"
MOISTURE_PORT="3005"
CONFIG_DIR="$HOME/.cloudflared"
TUNNEL_CONFIG="$CONFIG_DIR/config-moisture.yml"

echo -e "\n${GREEN}1. Creating Cloudflare tunnel: $TUNNEL_NAME${NC}"

# Check if tunnel already exists
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo -e "${YELLOW}⚠️  Tunnel '$TUNNEL_NAME' already exists${NC}"
    read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing tunnel..."
        cloudflared tunnel delete "$TUNNEL_NAME" -f
    else
        echo "Using existing tunnel..."
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    fi
fi

# Create tunnel if it doesn't exist
if [ -z "$TUNNEL_ID" ]; then
    echo "Creating new tunnel..."
    TUNNEL_OUTPUT=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1)
    TUNNEL_ID=$(echo "$TUNNEL_OUTPUT" | grep -oE '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}' | head -1)
fi

if [ -z "$TUNNEL_ID" ]; then
    echo -e "${RED}❌ Failed to get tunnel ID${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Tunnel created/found: $TUNNEL_ID${NC}"

# Create tunnel configuration
echo -e "\n${GREEN}2. Creating tunnel configuration${NC}"

cat > "$TUNNEL_CONFIG" << EOF
tunnel: $TUNNEL_ID
credentials-file: $CONFIG_DIR/$TUNNEL_ID.json

# Ingress rules for moisture sensor data
ingress:
  # Moisture sensor telemetry endpoint
  - hostname: munbon-moisture.beautifyai.io
    service: http://localhost:$MOISTURE_PORT
    originRequest:
      connectTimeout: 30s
      noTLSVerify: true
      
  # Health check endpoint
  - hostname: munbon-moisture-health.beautifyai.io
    service: http://localhost:$MOISTURE_PORT/health
    
  # Catch-all rule
  - service: http_status:404
EOF

echo -e "${GREEN}✅ Configuration created at: $TUNNEL_CONFIG${NC}"

# Create PM2 configuration
echo -e "\n${GREEN}3. Creating PM2 configuration${NC}"

PM2_CONFIG="/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/pm2-moisture-tunnel.json"

cat > "$PM2_CONFIG" << EOF
{
  "apps": [
    {
      "name": "munbon-moisture-tunnel",
      "script": "cloudflared",
      "args": "tunnel --config $TUNNEL_CONFIG run",
      "cwd": "/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data",
      "env": {
        "NODE_ENV": "production"
      },
      "autorestart": true,
      "watch": false,
      "max_restarts": 10,
      "min_uptime": "10s",
      "error_file": "./logs/moisture-tunnel-error.log",
      "out_file": "./logs/moisture-tunnel-out.log",
      "log_file": "./logs/moisture-tunnel-combined.log",
      "time": true
    }
  ]
}
EOF

echo -e "${GREEN}✅ PM2 configuration created${NC}"

# Create DNS setup instructions
echo -e "\n${GREEN}4. DNS Configuration Instructions${NC}"

DNS_INSTRUCTIONS="/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/moisture-tunnel-dns.md"

cat > "$DNS_INSTRUCTIONS" << EOF
# DNS Configuration for Moisture Tunnel

## Required DNS Records

Add the following CNAME records to your DNS provider for beautifyai.io:

### 1. Main moisture endpoint
\`\`\`
Type: CNAME
Name: munbon-moisture
Target: $TUNNEL_ID.cfargotunnel.com
TTL: Auto or 300
\`\`\`

### 2. Health check endpoint
\`\`\`
Type: CNAME
Name: munbon-moisture-health
Target: $TUNNEL_ID.cfargotunnel.com
TTL: Auto or 300
\`\`\`

## Cloudflare Dashboard Setup

1. Log into Cloudflare Dashboard: https://dash.cloudflare.com
2. Select the beautifyai.io domain
3. Go to DNS → Records
4. Add the CNAME records above

## Testing DNS

After adding records, test with:
\`\`\`bash
# Check DNS propagation
nslookup munbon-moisture.beautifyai.io
dig munbon-moisture.beautifyai.io CNAME

# Test the endpoint (after tunnel is running)
curl https://munbon-moisture.beautifyai.io/health
\`\`\`

## Tunnel URLs

- Public URL: https://munbon-moisture.beautifyai.io
- Tunnel URL: https://$TUNNEL_ID.cfargotunnel.com
- Health Check: https://munbon-moisture-health.beautifyai.io/health
EOF

echo -e "${GREEN}✅ DNS instructions saved to: $DNS_INSTRUCTIONS${NC}"

# Route the tunnel to Cloudflare network
echo -e "\n${GREEN}5. Routing tunnel to Cloudflare network${NC}"

cloudflared tunnel route dns "$TUNNEL_ID" "munbon-moisture.beautifyai.io" 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Note: DNS routing requires domain ownership verification in Cloudflare${NC}"
}

# Create start script
echo -e "\n${GREEN}6. Creating start script${NC}"

START_SCRIPT="/Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/start-moisture-tunnel.sh"

cat > "$START_SCRIPT" << 'EOF'
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
EOF

chmod +x "$START_SCRIPT"
echo -e "${GREEN}✅ Start script created${NC}"

# Summary
echo -e "\n${YELLOW}📋 Setup Summary:${NC}"
echo "=================="
echo "Tunnel Name: $TUNNEL_NAME"
echo "Tunnel ID: $TUNNEL_ID"
echo "Local Port: $MOISTURE_PORT"
echo "Config File: $TUNNEL_CONFIG"
echo "PM2 Config: $PM2_CONFIG"
echo "DNS Instructions: $DNS_INSTRUCTIONS"
echo "Start Script: $START_SCRIPT"
echo ""
echo -e "${YELLOW}📌 Next Steps:${NC}"
echo "1. Configure DNS records as per $DNS_INSTRUCTIONS"
echo "2. Ensure moisture monitoring service is running on port $MOISTURE_PORT"
echo "3. Run: $START_SCRIPT"
echo ""
echo -e "${GREEN}✅ Moisture tunnel setup complete!${NC}"