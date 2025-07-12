#!/bin/bash

# Setup script for free domain with Cloudflare
# This script guides you through setting up a free domain with Cloudflare tunnel

echo "=== Free Domain + Cloudflare Setup Guide ==="
echo ""

# Function to setup Freenom domain
setup_freenom_domain() {
    echo "=== Setting up Freenom Domain ==="
    echo ""
    echo "1. Go to https://www.freenom.com"
    echo "2. Search for available domain (e.g., munbon-api.tk)"
    echo "3. Register the domain for free"
    echo "4. Once registered, go to 'Services' > 'My Domains'"
    echo "5. Click 'Manage Domain' > 'Management Tools' > 'Nameservers'"
    echo "6. Select 'Use custom nameservers' and enter:"
    echo "   - brad.ns.cloudflare.com"
    echo "   - coco.ns.cloudflare.com"
    echo ""
    echo "Press Enter when you've completed these steps..."
    read
    
    echo "Enter your Freenom domain (e.g., munbon-api.tk):"
    read DOMAIN
}

# Function to setup DuckDNS
setup_duckdns() {
    echo "=== Setting up DuckDNS ==="
    echo ""
    echo "1. Go to https://www.duckdns.org"
    echo "2. Sign in with GitHub, Reddit, or Google"
    echo "3. Create a subdomain (e.g., munbon-api)"
    echo "4. You'll get: munbon-api.duckdns.org"
    echo ""
    echo "Enter your DuckDNS subdomain (without .duckdns.org):"
    read SUBDOMAIN
    echo "Enter your DuckDNS token:"
    read -s DUCKDNS_TOKEN
    
    DOMAIN="${SUBDOMAIN}.duckdns.org"
    
    # For DuckDNS, we need to use Cloudflare Tunnel directly
    USE_TUNNEL_ONLY=true
}

# Choose domain type
echo "Choose your free domain provider:"
echo "1. Freenom (.tk, .ml, .ga, .cf)"
echo "2. DuckDNS (subdomain.duckdns.org)"
echo "3. I already have a domain"
read -p "Enter choice (1-3): " CHOICE

case $CHOICE in
    1)
        setup_freenom_domain
        ;;
    2)
        setup_duckdns
        ;;
    3)
        echo "Enter your domain:"
        read DOMAIN
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Add to Cloudflare (skip for DuckDNS)
if [ "$USE_TUNNEL_ONLY" != "true" ]; then
    echo ""
    echo "=== Adding Domain to Cloudflare ==="
    echo ""
    echo "1. Go to https://dash.cloudflare.com"
    echo "2. Sign up for free account (if needed)"
    echo "3. Click 'Add a Site'"
    echo "4. Enter your domain: $DOMAIN"
    echo "5. Select FREE plan"
    echo "6. Cloudflare will scan DNS records"
    echo "7. You'll get nameservers like:"
    echo "   - xxxx.ns.cloudflare.com"
    echo "   - yyyy.ns.cloudflare.com"
    echo ""
    echo "Press Enter when domain is added to Cloudflare..."
    read
fi

# Install cloudflared if not present
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install cloudflare/cloudflare/cloudflared
    else
        wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
        sudo dpkg -i cloudflared-linux-amd64.deb
        rm cloudflared-linux-amd64.deb
    fi
fi

# Login to Cloudflare
echo ""
echo "=== Authenticating with Cloudflare ==="
cloudflared tunnel login

# Create tunnel
echo ""
echo "=== Creating Cloudflare Tunnel ==="
TUNNEL_NAME="munbon-api-tunnel"
cloudflared tunnel create $TUNNEL_NAME

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep $TUNNEL_NAME | awk '{print $1}')

# Create config directory if not exists
mkdir -p ~/.cloudflared

# Create tunnel configuration
echo ""
echo "=== Creating Tunnel Configuration ==="

if [ "$USE_TUNNEL_ONLY" = "true" ]; then
    # For DuckDNS, we update their DNS to point to tunnel
    echo "Updating DuckDNS..."
    TUNNEL_DOMAIN="${TUNNEL_ID}.cfargotunnel.com"
    curl -s "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&txt=${TUNNEL_DOMAIN}"
    
    cat > ~/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: /home/${USER}/.cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:3001
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF
else
    # For regular domains, create DNS record
    cloudflared tunnel route dns $TUNNEL_NAME $DOMAIN
    
    cat > ~/.cloudflared/config.yml << EOF
tunnel: ${TUNNEL_ID}
credentials-file: /home/${USER}/.cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:3001
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF
fi

# Create environment file
cat > .env.tunnel << EOF
# Cloudflare Tunnel Configuration
TUNNEL_ID=${TUNNEL_ID}
TUNNEL_NAME=${TUNNEL_NAME}
PUBLIC_DOMAIN=${DOMAIN}
PUBLIC_URL=https://${DOMAIN}

# API Base URLs
PUBLIC_API_BASE=https://${DOMAIN}/api/v1/public
WATER_LEVEL_API=https://${DOMAIN}/api/v1/public/water-levels
MOISTURE_API=https://${DOMAIN}/api/v1/public/moisture
AOS_API=https://${DOMAIN}/api/v1/public/aos
EOF

# Create systemd service (Linux) or LaunchAgent (macOS)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo tee /etc/systemd/system/cloudflared.service > /dev/null << EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=notify
User=$USER
ExecStart=/usr/local/bin/cloudflared tunnel run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable cloudflared
    echo ""
    echo "To start tunnel: sudo systemctl start cloudflared"
    echo "To check status: sudo systemctl status cloudflared"
else
    # macOS LaunchAgent
    cat > ~/Library/LaunchAgents/com.cloudflare.tunnel.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
    
    launchctl load ~/Library/LaunchAgents/com.cloudflare.tunnel.plist
    echo ""
    echo "Tunnel service loaded and will start automatically"
fi

# Create test script
cat > test-api.sh << 'EOF'
#!/bin/bash
source .env.tunnel

echo "Testing API endpoints..."
echo ""

# Test health endpoint
echo "1. Testing health endpoint:"
curl -s ${PUBLIC_URL}/health | jq .

echo ""
echo "2. Testing moisture latest (with API key):"
curl -s -H "X-API-Key: ${TEST_API_KEY}" ${MOISTURE_API}/latest | jq .

echo ""
echo "3. Testing water level latest (with API key):"
curl -s -H "X-API-Key: ${TEST_API_KEY}" ${WATER_LEVEL_API}/latest | jq .

echo ""
echo "API Base URL: ${PUBLIC_API_BASE}"
EOF

chmod +x test-api.sh

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Your API is now available at:"
echo "https://${DOMAIN}"
echo ""
echo "API Endpoints:"
echo "- Moisture: https://${DOMAIN}/api/v1/public/moisture/*"
echo "- Water Level: https://${DOMAIN}/api/v1/public/water-levels/*"
echo "- AOS/Weather: https://${DOMAIN}/api/v1/public/aos/*"
echo ""
echo "Files created:"
echo "- ~/.cloudflared/config.yml - Tunnel configuration"
echo "- .env.tunnel - Environment variables"
echo "- test-api.sh - Test script"
echo ""
echo "To start tunnel manually: cloudflared tunnel run"
echo "To test API: ./test-api.sh"