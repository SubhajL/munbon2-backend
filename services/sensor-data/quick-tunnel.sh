#!/bin/bash

# Quick one-liner Cloudflare tunnel for Munbon API
# This gives you instant HTTPS with TLS 1.0+ support

echo "Starting Cloudflare tunnel with TLS 1.0+ support..."
echo ""

# Install cloudflared if not present
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install cloudflare/cloudflare/cloudflared 2>/dev/null || {
            curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz | tar xz
            sudo mv cloudflared /usr/local/bin/
        }
    else
        curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
        chmod +x cloudflared
        sudo mv cloudflared /usr/local/bin/
    fi
fi

# Run tunnel and save URL
echo "Creating tunnel..."
cloudflared tunnel --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com 2>&1 | tee tunnel.log &

# Wait and extract URL
sleep 5
TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9\-]*\.trycloudflare\.com' tunnel.log | head -1)

if [ -n "$TUNNEL_URL" ]; then
    echo ""
    echo "=== TUNNEL READY ==="
    echo "Your API is now available at:"
    echo "$TUNNEL_URL"
    echo ""
    echo "This URL supports TLS 1.0, 1.1, 1.2, 1.3"
    echo ""
    echo "Test endpoints:"
    echo "- $TUNNEL_URL/dev/api/v1/munbon-m2m-moisture/attributes"
    echo "- $TUNNEL_URL/dev/api/v1/munbon-m2m-moisture/telemetry"
    echo ""
    echo "$TUNNEL_URL" > tunnel-url.txt
    echo "URL saved to: tunnel-url.txt"
    echo ""
    echo "Press Ctrl+C to stop"
    wait
else
    echo "Failed to start tunnel. Check tunnel.log for details."
    exit 1
fi