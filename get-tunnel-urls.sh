#!/bin/bash

# Script to display all Cloudflare tunnel URLs

echo "=== Cloudflare Tunnel URLs ==="
echo ""

# Check internal API tunnel
if [ -f "./services/sensor-data/tunnel-url.txt" ]; then
    INTERNAL_URL=$(cat ./services/sensor-data/tunnel-url.txt)
    echo "Internal API Tunnel (port 3000):"
    echo "  $INTERNAL_URL"
else
    echo "Internal API Tunnel: Not found or not running"
fi

echo ""

# Check external API tunnel (legacy TLS support)
if [ -f "./services/sensor-data/tunnel-external-url.txt" ]; then
    EXTERNAL_URL=$(cat ./services/sensor-data/tunnel-external-url.txt)
    echo "External API Tunnel (AWS API Gateway with TLS 1.0+ support):"
    echo "  $EXTERNAL_URL"
    echo ""
    echo "This tunnel provides:"
    echo "  - TLS 1.0, 1.1, 1.2, 1.3 support"
    echo "  - Legacy cipher suite compatibility"
    echo "  - Same API endpoints as: https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com"
else
    # Try to extract from logs
    if [ -f "./logs/tunnel-external-out.log" ]; then
        EXTERNAL_URL=$(grep -o 'https://[a-zA-Z0-9\-]*\.trycloudflare\.com' ./logs/tunnel-external-out.log | tail -1)
        if [ -n "$EXTERNAL_URL" ]; then
            echo "External API Tunnel (AWS API Gateway with TLS 1.0+ support):"
            echo "  $EXTERNAL_URL"
            echo "$EXTERNAL_URL" > ./services/sensor-data/tunnel-external-url.txt
        else
            echo "External API Tunnel: Starting up, please wait..."
        fi
    else
        echo "External API Tunnel: Not running"
        echo "Start with: pm2 start cloudflare-tunnel-external"
    fi
fi

echo ""
echo "Test endpoints:"
if [ -n "$EXTERNAL_URL" ]; then
    echo "  curl $EXTERNAL_URL/dev/api/v1/munbon-m2m-moisture/attributes"
    echo "  curl --tlsv1.0 $EXTERNAL_URL/dev/api/v1/munbon-m2m-moisture/attributes"
fi