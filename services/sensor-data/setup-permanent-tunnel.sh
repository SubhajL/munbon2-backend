#!/bin/bash

echo "Setting up permanent Cloudflare tunnel..."

# 1. Login to Cloudflare (one-time)
cloudflared tunnel login

# 2. Create a named tunnel
TUNNEL_NAME="munbon-api-stable"
cloudflared tunnel create $TUNNEL_NAME

# 3. Create config file
TUNNEL_ID=$(cloudflared tunnel list | grep $TUNNEL_NAME | awk '{print $1}')

cat > ~/.cloudflared/config.yml <<EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: munbon-api.yourdomain.com
    service: http://localhost:3000
    originRequest:
      httpHostHeader: localhost
      noTLSVerify: true
  - service: http_status:404
EOF

# 4. Route DNS (if you have a domain)
# cloudflared tunnel route dns $TUNNEL_NAME munbon-api.yourdomain.com

# 5. Run tunnel
cloudflared tunnel run $TUNNEL_NAME