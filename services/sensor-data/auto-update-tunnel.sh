#!/bin/bash

echo "🚀 Auto-Update Tunnel URL System"
echo "================================"
echo ""
echo "This script will:"
echo "1. Monitor the Cloudflare tunnel for URL changes"
echo "2. Automatically update AWS Parameter Store"
echo "3. No Lambda redeployment needed!"
echo ""

# Function to get current tunnel URL
get_tunnel_url() {
    pm2 logs quick-tunnel --lines 50 --nostream 2>/dev/null | grep -oE "https://[a-z-]+\.trycloudflare\.com" | tail -1
}

# Initial URL
LAST_URL=""

echo "📡 Monitoring tunnel URL changes..."
echo "Press Ctrl+C to stop"
echo ""

while true; do
    CURRENT_URL=$(get_tunnel_url)
    
    if [ -n "$CURRENT_URL" ] && [ "$CURRENT_URL" != "$LAST_URL" ]; then
        echo "[$(date)] New tunnel URL detected: $CURRENT_URL"
        
        # Update Parameter Store using AWS CLI
        if command -v aws &> /dev/null; then
            aws ssm put-parameter \
                --name "/munbon/tunnel-url" \
                --value "$CURRENT_URL" \
                --type "String" \
                --overwrite \
                --region ap-southeast-1 \
                2>/dev/null
            
            if [ $? -eq 0 ]; then
                echo "✅ Updated Parameter Store successfully!"
            else
                echo "❌ Failed to update Parameter Store"
            fi
        else
            # Use Node.js script as fallback
            node update-tunnel-parameter.js
        fi
        
        LAST_URL=$CURRENT_URL
    fi
    
    sleep 30  # Check every 30 seconds
done