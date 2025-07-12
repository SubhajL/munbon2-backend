#!/bin/bash

echo "=== Cloudflare Permanent Tunnel Setup ==="
echo ""
echo "Step 1: Authenticate with Cloudflare"
echo "This will open a browser. When prompted:"
echo "1. Select any domain from the list (it doesn't matter which)"
echo "2. Click Authorize"
echo ""
read -p "Press Enter to continue..."

cloudflared tunnel login

echo ""
echo "Step 2: Create permanent named tunnel"
cloudflared tunnel create munbon-api

echo ""
echo "Step 3: Get your tunnel ID"
TUNNEL_ID=$(cloudflared tunnel list --name munbon-api --output json | jq -r '.[0].id')
echo "Your tunnel ID is: $TUNNEL_ID"
echo "Your permanent URL will be: https://$TUNNEL_ID.cfargotunnel.com"

echo ""
echo "Step 4: Create configuration"
cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  - service: http://localhost:3000
    originRequest:
      noTLSVerify: true
EOF

echo ""
echo "Step 5: Test the tunnel"
echo "Run: cloudflared tunnel run munbon-api"
echo ""
echo "Your permanent tunnel URL: https://$TUNNEL_ID.cfargotunnel.com"
echo ""
echo "To make it run permanently:"
echo "1. Install as service: sudo cloudflared service install"
echo "2. Or use PM2: pm2 start cloudflared -- tunnel run munbon-api"