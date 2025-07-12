#!/bin/bash

# Permanent Cloudflare Tunnel Setup for Mock API Server
# This creates a stable, permanent tunnel that won't disconnect

set -e

echo "🚀 Setting Up Permanent Cloudflare Tunnel for Mock API"
echo "====================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
TUNNEL_NAME="munbon-mock-api"
MOCK_PORT="4010"
CONFIG_DIR="$HOME/.cloudflared"
MOCK_CONFIG_FILE="$CONFIG_DIR/mock-api-config.yml"

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}Error: cloudflared is not installed${NC}"
    echo "Install with: brew install cloudflare/cloudflare/cloudflared"
    exit 1
fi

# Function to create new tunnel
create_new_tunnel() {
    echo -e "${BLUE}Creating new permanent tunnel: $TUNNEL_NAME${NC}"
    
    # Check if tunnel already exists
    if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
        echo -e "${YELLOW}Tunnel '$TUNNEL_NAME' already exists${NC}"
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    else
        # Create new tunnel
        cloudflared tunnel create $TUNNEL_NAME
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    fi
    
    if [ -z "$TUNNEL_ID" ]; then
        echo -e "${RED}Failed to create/find tunnel${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Tunnel ID: $TUNNEL_ID${NC}"
    return 0
}

# Function to setup tunnel configuration
setup_tunnel_config() {
    echo -e "${BLUE}Setting up tunnel configuration...${NC}"
    
    # Create config directory if it doesn't exist
    mkdir -p "$CONFIG_DIR"
    
    # Create dedicated mock API config
    cat > "$MOCK_CONFIG_FILE" << EOF
# Cloudflare Tunnel Configuration for Mock API Server
tunnel: $TUNNEL_ID
credentials-file: $CONFIG_DIR/$TUNNEL_ID.json

# Tunnel metrics
metrics: localhost:2000

# Ingress rules
ingress:
  # Mock API endpoints
  - service: http://localhost:$MOCK_PORT
    originRequest:
      noTLSVerify: true
      connectTimeout: 30s
      keepAliveConnections: 100
      keepAliveTimeout: 90s
      httpHostHeader: "localhost"
      
# Log settings
loglevel: info
EOF

    echo -e "${GREEN}✓ Configuration created at: $MOCK_CONFIG_FILE${NC}"
}

# Function to setup DNS (optional)
setup_dns_route() {
    echo ""
    echo -e "${BLUE}DNS Route Setup${NC}"
    echo "To access your mock API via a domain, you need to:"
    echo ""
    echo "1. Have a domain in Cloudflare (free options: Freenom domains)"
    echo "2. Run: cloudflared tunnel route dns $TUNNEL_NAME mock-api.yourdomain.com"
    echo ""
    read -p "Do you want to set up a DNS route now? (y/n): " setup_dns
    
    if [[ "$setup_dns" == "y" ]]; then
        read -p "Enter your domain (e.g., mock-api.yourdomain.com): " domain
        if [ -n "$domain" ]; then
            echo -e "${BLUE}Setting up DNS route...${NC}"
            if cloudflared tunnel route dns $TUNNEL_NAME $domain; then
                echo -e "${GREEN}✓ DNS route created: $domain${NC}"
                echo "$domain" > "$CONFIG_DIR/mock-api-domain.txt"
            else
                echo -e "${YELLOW}Failed to create DNS route. You may need to add your domain to Cloudflare first.${NC}"
            fi
        fi
    fi
}

# Function to create systemd service (Linux) or launchd plist (macOS)
create_service() {
    echo ""
    echo -e "${BLUE}Service Setup${NC}"
    echo "This will create a system service to keep the tunnel running permanently."
    echo ""
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - Create launchd plist
        PLIST_FILE="$HOME/Library/LaunchAgents/com.munbon.mock-tunnel.plist"
        
        cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.munbon.mock-tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/cloudflared</string>
        <string>tunnel</string>
        <string>--config</string>
        <string>$MOCK_CONFIG_FILE</string>
        <string>run</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$HOME/.cloudflared/mock-tunnel-error.log</string>
    <key>StandardOutPath</key>
    <string>$HOME/.cloudflared/mock-tunnel.log</string>
</dict>
</plist>
EOF
        
        echo -e "${GREEN}✓ macOS service created${NC}"
        echo ""
        echo "To start the service:"
        echo "  launchctl load $PLIST_FILE"
        echo ""
        echo "To stop the service:"
        echo "  launchctl unload $PLIST_FILE"
        
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux - Create systemd service
        SERVICE_FILE="$HOME/.config/systemd/user/munbon-mock-tunnel.service"
        mkdir -p "$HOME/.config/systemd/user"
        
        cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Munbon Mock API Cloudflare Tunnel
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --config $MOCK_CONFIG_FILE run
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
        
        echo -e "${GREEN}✓ Linux systemd service created${NC}"
        echo ""
        echo "To start the service:"
        echo "  systemctl --user daemon-reload"
        echo "  systemctl --user enable munbon-mock-tunnel"
        echo "  systemctl --user start munbon-mock-tunnel"
    fi
}

# Function to create PM2 ecosystem file
create_pm2_config() {
    PM2_CONFIG="$CONFIG_DIR/mock-tunnel-pm2.json"
    
    cat > "$PM2_CONFIG" << EOF
{
  "apps": [
    {
      "name": "mock-api-server",
      "script": "npx",
      "args": "prism mock openapi/sensor-data-service.yaml -p $MOCK_PORT -h 0.0.0.0",
      "cwd": "$(pwd)",
      "error_file": "$CONFIG_DIR/mock-api-error.log",
      "out_file": "$CONFIG_DIR/mock-api-out.log",
      "merge_logs": true,
      "time": true
    },
    {
      "name": "mock-api-tunnel",
      "script": "cloudflared",
      "args": "tunnel --config $MOCK_CONFIG_FILE run",
      "error_file": "$CONFIG_DIR/tunnel-error.log",
      "out_file": "$CONFIG_DIR/tunnel-out.log",
      "merge_logs": true,
      "time": true,
      "restart_delay": 5000,
      "min_uptime": 10000
    }
  ]
}
EOF
    
    echo -e "${GREEN}✓ PM2 configuration created${NC}"
    echo ""
    echo "To use PM2 (recommended for reliability):"
    echo "  pm2 start $PM2_CONFIG"
    echo "  pm2 save"
    echo "  pm2 startup  # To start on system boot"
}

# Main setup flow
echo -e "${YELLOW}This script will set up a permanent, reliable tunnel for your mock API server.${NC}"
echo ""

# Step 1: Create or find tunnel
create_new_tunnel

# Step 2: Setup configuration
setup_tunnel_config

# Step 3: Optional DNS setup
setup_dns_route

# Step 4: Create service files
echo ""
read -p "Create system service for auto-start? (y/n): " create_svc
if [[ "$create_svc" == "y" ]]; then
    create_service
fi

# Step 5: Create PM2 config
create_pm2_config

# Final instructions
echo ""
echo "====================================================="
echo -e "${GREEN}✅ Permanent Tunnel Setup Complete!${NC}"
echo "====================================================="
echo ""
echo -e "${BLUE}Tunnel Information:${NC}"
echo "  Name: $TUNNEL_NAME"
echo "  ID: $TUNNEL_ID"
echo "  Config: $MOCK_CONFIG_FILE"
echo ""
echo -e "${BLUE}Quick Start Commands:${NC}"
echo ""
echo "1. Using PM2 (Recommended - Auto-restart on failure):"
echo "   pm2 start $CONFIG_DIR/mock-tunnel-pm2.json"
echo ""
echo "2. Manual start (separate terminals):"
echo "   Terminal 1: npm run mock:server"
echo "   Terminal 2: cloudflared tunnel --config $MOCK_CONFIG_FILE run"
echo ""
echo "3. Test the tunnel:"
echo "   cloudflared tunnel info $TUNNEL_NAME"
echo ""

# Save tunnel info
cat > "$CONFIG_DIR/mock-tunnel-info.txt" << EOF
Tunnel Name: $TUNNEL_NAME
Tunnel ID: $TUNNEL_ID
Config File: $MOCK_CONFIG_FILE
Mock Server Port: $MOCK_PORT
Created: $(date)
EOF

echo -e "${GREEN}Tunnel information saved to: $CONFIG_DIR/mock-tunnel-info.txt${NC}"

# Check if we have a domain configured
if [ -f "$CONFIG_DIR/mock-api-domain.txt" ]; then
    DOMAIN=$(cat "$CONFIG_DIR/mock-api-domain.txt")
    echo ""
    echo -e "${GREEN}Your mock API will be available at: https://$DOMAIN${NC}"
else
    echo ""
    echo -e "${YELLOW}Note: Without a DNS route, your tunnel will only be accessible via the Cloudflare UUID URL.${NC}"
    echo -e "${YELLOW}The URL will be shown when you start the tunnel.${NC}"
fi

echo ""
echo -e "${BLUE}Need help? Check the logs:${NC}"
echo "  tail -f $CONFIG_DIR/mock-api-*.log"
echo "  tail -f $CONFIG_DIR/tunnel-*.log"