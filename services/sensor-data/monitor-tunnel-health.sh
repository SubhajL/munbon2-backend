#!/bin/bash

# Monitor tunnel health and auto-update Parameter Store

PARAM_NAME="/munbon/tunnel-url"
CHECK_INTERVAL=60  # seconds
MAX_FAILURES=3

failure_count=0
last_url=""

while true; do
    # Get current tunnel URL from PM2 logs
    current_url=$(pm2 logs quick-tunnel --lines 50 --nostream 2>/dev/null | \
                  grep -oE "https://[a-z-]+\.trycloudflare\.com" | tail -1)
    
    if [ -z "$current_url" ]; then
        ((failure_count++))
        echo "[$(date)] No tunnel URL found (failure $failure_count/$MAX_FAILURES)"
        
        if [ $failure_count -ge $MAX_FAILURES ]; then
            echo "[$(date)] Restarting tunnel due to repeated failures"
            pm2 restart quick-tunnel
            failure_count=0
            sleep 30
        fi
    else
        failure_count=0
        
        # Test if tunnel is actually working
        if curl -s -f "$current_url/health" \
                -H "X-Internal-Key: munbon-internal-f3b89263126548" \
                --max-time 5 > /dev/null; then
            
            echo "[$(date)] Tunnel healthy: $current_url"
            
            # Update Parameter Store if URL changed
            if [ "$current_url" != "$last_url" ]; then
                echo "[$(date)] Updating Parameter Store with new URL"
                aws ssm put-parameter \
                    --name "$PARAM_NAME" \
                    --value "$current_url" \
                    --type "String" \
                    --overwrite \
                    --region ap-southeast-1
                
                last_url="$current_url"
            fi
        else
            echo "[$(date)] Tunnel not responding: $current_url"
            ((failure_count++))
        fi
    fi
    
    sleep $CHECK_INTERVAL
done