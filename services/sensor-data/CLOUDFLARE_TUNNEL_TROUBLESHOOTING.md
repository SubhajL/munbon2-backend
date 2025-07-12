# Cloudflare Tunnel Troubleshooting Guide

## Common Error: "context canceled" Connection Failures

### Error Pattern
```
2025-07-07T11:38:49Z ERR Failed to serve tunnel connection error="context canceled" connIndex=0 event=0 ip=198.41.192.7
2025-07-07T11:38:49Z INF Retrying connection in up to 1m4s connIndex=0 event=0 ip=198.41.192.7
2025-07-07T11:38:49Z ERR Connection terminated error="context canceled" connIndex=0
```

### Root Causes & Solutions

#### 1. **Multiple Tunnel Instances Running**
**Symptoms**: Connection keeps getting canceled immediately after attempting
**Cause**: Multiple cloudflared processes competing for the same tunnel

**Solution**:
```bash
# Check for existing cloudflared processes
ps aux | grep cloudflared

# Kill all cloudflared processes
pkill -f cloudflared

# Start fresh tunnel
./setup-cloudflare-tunnel.sh
```

#### 2. **Stale Tunnel Configuration**
**Symptoms**: Was working, then suddenly stops
**Cause**: Tunnel URL expired or configuration changed

**Solution**:
```bash
# Remove old tunnel URL
rm tunnel-url.txt

# Update Lambda environment with new URL
cd deployments/aws-lambda
./update-tunnel-url.sh
```

#### 3. **Network/Firewall Issues**
**Symptoms**: Intermittent connection failures
**Cause**: Corporate firewall, VPN, or ISP blocking

**Solution**:
```bash
# Test direct connection to Cloudflare
curl -v https://api.cloudflare.com/client/v4/user

# Try with different protocol
cloudflared tunnel --url http://localhost:3000 --protocol http2

# Use SOCKS proxy if behind corporate firewall
cloudflared tunnel --url http://localhost:3000 --proxy-url socks5://localhost:1080
```

#### 4. **Resource Constraints**
**Symptoms**: Works initially, fails after some time
**Cause**: System running out of memory/CPU

**Solution**:
```bash
# Check system resources
top -b -n 1 | head -20

# Run tunnel with lower resource usage
cloudflared tunnel --url http://localhost:3000 --loglevel error --max-fetch-size 50
```

#### 5. **DNS Resolution Issues**
**Symptoms**: Cannot connect to Cloudflare edge servers
**Cause**: DNS configuration problems

**Solution**:
```bash
# Test DNS resolution
nslookup api.cloudflare.com
dig api.cloudflare.com

# Use alternative DNS
cloudflared tunnel --url http://localhost:3000 --edge-ip-version 4
```

### Quick Recovery Steps

1. **Immediate Fix** (for testing):
```bash
# Kill all tunnels
pkill -f cloudflared

# Start fresh quick tunnel
cloudflared tunnel --url http://localhost:3000
```

2. **Stable Setup**:
```bash
# Use systemd/launchd for auto-restart
# Create service file for cloudflared
sudo nano /etc/systemd/system/cloudflared.service
```

```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=your-user
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:3000 --no-autoupdate
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

### Monitoring & Prevention

1. **Monitor Tunnel Health**:
```bash
# Check tunnel status
cloudflared tunnel list
cloudflared tunnel info <tunnel-name>

# Monitor logs
journalctl -u cloudflared -f
```

2. **Automatic Recovery Script**:
```bash
#!/bin/bash
# save as monitor-tunnel.sh

while true; do
    if ! pgrep -f cloudflared > /dev/null; then
        echo "Tunnel down, restarting..."
        cloudflared tunnel --url http://localhost:3000 &
        sleep 5
        
        # Update Lambda with new URL
        TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9\-]*\.trycloudflare\.com' /tmp/cloudflared.log | head -1)
        if [ -n "$TUNNEL_URL" ]; then
            echo "$TUNNEL_URL" > tunnel-url.txt
            cd deployments/aws-lambda && ./update-tunnel-url.sh
        fi
    fi
    sleep 30
done
```

### Alternative Solutions

1. **Use ngrok instead**:
```bash
# Install ngrok
brew install ngrok

# Start tunnel
ngrok http 3000
```

2. **Deploy Unified API to Cloud**:
- Deploy to AWS EC2/ECS
- Use AWS App Runner
- Deploy to Vercel/Netlify

3. **Direct Lambda-to-Database Connection**:
- Configure Lambda to connect directly to databases
- Use RDS Proxy for connection pooling
- Set up VPC peering if databases are in private network

### Debug Commands

```bash
# Test if unified API is running
curl http://localhost:3000/health

# Check if tunnel URL is accessible
curl $(cat tunnel-url.txt)/health

# Test Lambda proxy
curl -X GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest \
  -H "X-API-Key: rid-ms-prod-key1"

# Check Lambda logs
aws logs tail /aws/lambda/munbon-sensor-data-prod-proxyHandler --follow
```

### When to Restart Everything

If errors persist after trying above solutions:

1. Stop all services:
```bash
pkill -f cloudflared
pkill -f "node.*unified-api"
```

2. Start unified API:
```bash
cd services/sensor-data
npm run start:unified-api
```

3. Start new tunnel:
```bash
./setup-cloudflare-tunnel.sh
# Choose option 1 for quick tunnel
```

4. Update Lambda:
```bash
cd deployments/aws-lambda
./update-tunnel-url.sh
```

5. Test the complete flow:
```bash
./test-deployed-api.sh
```