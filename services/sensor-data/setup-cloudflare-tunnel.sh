#!/bin/bash

# Cloudflare Tunnel Setup Script for Munbon API with TLS 1.0+ Support
# This creates a free subdomain that supports old TLS versions and ciphers

set -e

echo "=== Cloudflare Tunnel Setup for Munbon API ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# API Gateway endpoint
API_GATEWAY_URL="https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com"

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${YELLOW}Installing cloudflared...${NC}"
    
    # Detect OS and install cloudflared
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install cloudflare/cloudflare/cloudflared
        else
            echo "Installing via direct download..."
            curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz | tar xz
            sudo mv cloudflared /usr/local/bin/
            chmod +x /usr/local/bin/cloudflared
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux - detect package manager
        if command -v apt-get &> /dev/null; then
            # Debian/Ubuntu
            wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
            sudo dpkg -i cloudflared-linux-amd64.deb
            rm cloudflared-linux-amd64.deb
        elif command -v yum &> /dev/null; then
            # RedHat/CentOS
            sudo rpm -i https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-x86_64.rpm
        else
            # Generic Linux
            curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
            chmod +x cloudflared
            sudo mv cloudflared /usr/local/bin/
        fi
    else
        echo -e "${RED}Unsupported OS. Please install cloudflared manually.${NC}"
        echo "Visit: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation"
        exit 1
    fi
fi

# Function to run quick tunnel (temporary but immediate)
run_quick_tunnel() {
    echo -e "${BLUE}Starting quick tunnel (temporary URL)...${NC}"
    echo ""
    echo "This will create a free subdomain that supports TLS 1.0+"
    echo ""
    
    # Start tunnel and capture output
    echo -e "${YELLOW}Starting tunnel...${NC}"
    
    # Create a temporary file for output
    TEMP_FILE=$(mktemp)
    
    # Run cloudflared in background and capture output
    cloudflared tunnel --url $API_GATEWAY_URL > $TEMP_FILE 2>&1 &
    TUNNEL_PID=$!
    
    # Wait for tunnel to start (check for URL in output)
    echo -n "Waiting for tunnel to initialize"
    for i in {1..30}; do
        if grep -q "trycloudflare.com" $TEMP_FILE 2>/dev/null; then
            echo ""
            break
        fi
        echo -n "."
        sleep 1
    done
    echo ""
    
    # Extract the tunnel URL
    TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9\-]*\.trycloudflare\.com' $TEMP_FILE | head -1)
    
    if [ -n "$TUNNEL_URL" ]; then
        echo -e "${GREEN}✓ Tunnel is running!${NC}"
        echo ""
        echo -e "${GREEN}Your temporary tunnel URL:${NC}"
        echo -e "${BLUE}$TUNNEL_URL${NC}"
        echo ""
        echo -e "${GREEN}API Endpoints (supports TLS 1.0+):${NC}"
        echo "- Telemetry: $TUNNEL_URL/dev/api/v1/{token}/telemetry"
        echo "- Attributes: $TUNNEL_URL/dev/api/v1/{token}/attributes"
        echo "- File Upload: $TUNNEL_URL/dev/api/v1/rid-ms/upload"
        echo ""
        echo "Example test commands:"
        echo -e "${YELLOW}# Test with TLS 1.0:${NC}"
        echo "curl --tlsv1.0 -X GET $TUNNEL_URL/dev/api/v1/munbon-m2m-moisture/attributes"
        echo ""
        echo -e "${YELLOW}# Test with old cipher:${NC}"
        echo "curl --ciphers 'AES256-SHA' -X GET $TUNNEL_URL/dev/api/v1/munbon-m2m-moisture/attributes"
        echo ""
        echo -e "${YELLOW}This is a temporary URL. It will change when you restart the tunnel.${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop the tunnel.${NC}"
        echo ""
        
        # Save URL to file
        echo "$TUNNEL_URL" > tunnel-url.txt
        echo -e "${GREEN}URL saved to: tunnel-url.txt${NC}"
        
        # Clean up temp file
        rm -f $TEMP_FILE
        
        # Keep the tunnel running
        wait $TUNNEL_PID
    else
        echo -e "${RED}Failed to get tunnel URL.${NC}"
        echo "Debug output:"
        cat $TEMP_FILE
        kill $TUNNEL_PID 2>/dev/null
        rm -f $TEMP_FILE
        exit 1
    fi
}

# Function to setup permanent tunnel
setup_permanent_tunnel() {
    echo -e "${BLUE}Setting up permanent tunnel...${NC}"
    echo ""
    echo "This requires a free Cloudflare account."
    echo "1. Sign up at: https://dash.cloudflare.com/sign-up"
    echo "2. Add a domain (or use a free domain from Freenom)"
    echo ""
    read -p "Press Enter when ready to continue..."
    
    # Login to Cloudflare
    echo -e "${BLUE}Logging in to Cloudflare...${NC}"
    cloudflared tunnel login
    
    # Create tunnel
    TUNNEL_NAME="munbon-api-$(date +%Y%m%d%H%M%S)"
    echo -e "${BLUE}Creating tunnel: $TUNNEL_NAME${NC}"
    cloudflared tunnel create $TUNNEL_NAME
    
    # Get tunnel ID
    TUNNEL_ID=$(cloudflared tunnel list | grep $TUNNEL_NAME | awk '{print $1}')
    
    if [ -z "$TUNNEL_ID" ]; then
        echo -e "${RED}Error: Failed to create tunnel${NC}"
        exit 1
    fi
    
    # Create config directory if it doesn't exist
    mkdir -p ~/.cloudflared
    
    # Create config file
    cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  # Forward all traffic to API Gateway
  - service: $API_GATEWAY_URL
    originRequest:
      noTLSVerify: true
      httpHostHeader: c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com
EOF
    
    echo -e "${GREEN}✓ Permanent tunnel created!${NC}"
    echo ""
    echo "Tunnel ID: $TUNNEL_ID"
    echo "Tunnel Name: $TUNNEL_NAME"
    echo ""
    echo "To setup DNS (if you have a domain):"
    echo "cloudflared tunnel route dns $TUNNEL_NAME your-subdomain.yourdomain.com"
    echo ""
    echo "To run the permanent tunnel:"
    echo "cloudflared tunnel run $TUNNEL_NAME"
}

# Function to run existing tunnel
run_existing_tunnel() {
    echo -e "${BLUE}Available tunnels:${NC}"
    cloudflared tunnel list
    echo ""
    read -p "Enter tunnel name to run: " tunnel_name
    
    if [ -n "$tunnel_name" ]; then
        echo -e "${BLUE}Starting tunnel: $tunnel_name${NC}"
        cloudflared tunnel run $tunnel_name
    else
        echo -e "${RED}No tunnel name provided${NC}"
        exit 1
    fi
}

# Main menu
echo ""
echo -e "${GREEN}=== Cloudflare Tunnel Options ===${NC}"
echo ""
echo "Choose an option:"
echo "1) Quick tunnel (temporary URL - recommended for testing)"
echo "2) Permanent tunnel (requires Cloudflare account)"
echo "3) Run existing tunnel"
echo "4) Check tunnel status"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        run_quick_tunnel
        ;;
    2)
        setup_permanent_tunnel
        ;;
    3)
        run_existing_tunnel
        ;;
    4)
        echo -e "${BLUE}Checking tunnel status...${NC}"
        cloudflared tunnel list
        ;;
    *)
        echo -e "${RED}Invalid choice. Please run the script again.${NC}"
        exit 1
        ;;
esac