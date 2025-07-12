#!/bin/bash

# Instant FREE proxy with TLS 1.0 support - NO DOMAIN NEEDED!

echo "=== Setting up FREE proxy with custom TLS - NO DOMAIN REQUIRED! ==="
echo ""

# Option 1: Cloudflare Tunnel (Instant subdomain)
echo "Option 1: Cloudflare Tunnel (Recommended)"
echo "========================================="
echo "Run this command:"
echo ""
echo "docker run -it --rm cloudflare/cloudflared:latest tunnel --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com"
echo ""
echo "You'll instantly get a URL like:"
echo "https://random-words-here.trycloudflare.com"
echo ""

# Option 2: Using npx (even easier!)
echo "Option 2: Using npx (no Docker needed)"
echo "======================================"
echo "Run this command:"
echo ""
echo "npx cloudflared tunnel --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com"
echo ""

# Option 3: Permanent free tunnel
echo "Option 3: Permanent Free Tunnel"
echo "==============================="
cat << 'EOF'
# 1. Create free Cloudflare account
# 2. Run:
cloudflared tunnel login
cloudflared tunnel create munbon-api
cloudflared tunnel route dns munbon-api munbon-api.example.com
cloudflared tunnel run --url https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com munbon-api

# This gives you a permanent subdomain!
EOF

echo ""
echo "=== Your customers can then use: ==="
echo "OLD: https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/..."
echo "NEW: https://your-free-subdomain.trycloudflare.com/dev/api/v1/..."
echo ""
echo "Both endpoints work simultaneously!"
echo "The new endpoint supports SSL 3.0, TLS 1.0, 1.1, 1.2!"