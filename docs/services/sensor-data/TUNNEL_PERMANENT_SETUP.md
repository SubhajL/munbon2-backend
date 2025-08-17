# Cloudflare Tunnel Permanent Setup Guide

## Current Tunnel Information
- **Tunnel Name**: munbon-api
- **Tunnel ID**: f3b89263-1265-4843-b08c-5391e73e8c75
- **Permanent URL**: https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com
- **Status**: Running
- **Cost**: FREE forever

## Options to Keep Tunnel Running Permanently

### Option 1: PM2 (Recommended for Development)
```bash
# Install PM2 globally
npm install -g pm2

# Start tunnel with PM2
pm2 start cloudflared --name munbon-tunnel -- tunnel run munbon-api

# Save PM2 configuration
pm2 save

# Set PM2 to start on system boot
pm2 startup
# Follow the instructions printed by this command

# Check status
pm2 status munbon-tunnel
pm2 logs munbon-tunnel
```

### Option 2: macOS LaunchAgent (Recommended for macOS)
```bash
# Create launch agent plist file
cat > ~/Library/LaunchAgents/com.cloudflare.munbon-tunnel.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.munbon-tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>munbon-api</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/munbon-tunnel.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/munbon-tunnel.error.log</string>
</dict>
</plist>
EOF

# Load the service
launchctl load ~/Library/LaunchAgents/com.cloudflare.munbon-tunnel.plist

# Start the service
launchctl start com.cloudflare.munbon-tunnel

# Check status
launchctl list | grep munbon-tunnel
```

### Option 3: Docker Compose (Good for All Platforms)
```bash
# Create docker-compose.tunnel-permanent.yml
cat > docker-compose.tunnel-permanent.yml << EOF
version: '3.8'
services:
  cloudflare-tunnel:
    image: cloudflare/cloudflared:latest
    container_name: munbon-cloudflare-tunnel
    restart: unless-stopped
    command: tunnel run munbon-api
    volumes:
      - ~/.cloudflared:/home/nonroot/.cloudflared:ro
    network_mode: host
EOF

# Run in background
docker-compose -f docker-compose.tunnel-permanent.yml up -d

# Check logs
docker logs munbon-cloudflare-tunnel
```

### Option 4: Systemd Service (Linux)
```bash
# Create systemd service file
sudo tee /etc/systemd/system/cloudflared-munbon.service > /dev/null << EOF
[Unit]
Description=Cloudflare Tunnel for Munbon API
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/cloudflared tunnel run munbon-api
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable cloudflared-munbon.service
sudo systemctl start cloudflared-munbon.service

# Check status
sudo systemctl status cloudflared-munbon.service
```

### Option 5: Screen/Tmux (Quick but Manual)
```bash
# Using screen
screen -S munbon-tunnel
cloudflared tunnel run munbon-api
# Press Ctrl+A, D to detach

# To reattach
screen -r munbon-tunnel

# Using tmux
tmux new -s munbon-tunnel
cloudflared tunnel run munbon-api
# Press Ctrl+B, D to detach

# To reattach
tmux attach -t munbon-tunnel
```

## Monitoring Tunnel Health

### Check if tunnel is running
```bash
# Check process
ps aux | grep "cloudflared.*munbon-api" | grep -v grep

# Check tunnel status
cloudflared tunnel info munbon-api

# Test tunnel connectivity
curl -s -H "x-internal-key: munbon-internal-f3b89263126548" \
  https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com/health
```

### Monitor with PM2 (if using PM2)
```bash
# Real-time logs
pm2 logs munbon-tunnel

# Monitor dashboard
pm2 monit

# Web dashboard (optional)
pm2 install pm2-web
# Access at http://localhost:9615
```

## AWS Lambda Configuration Update

To update the Lambda functions to use the new tunnel URL, you need AWS CLI configured with appropriate credentials:

1. **Install AWS CLI** (if not installed):
```bash
# macOS
brew install awscli

# Or using pip
pip install awscli
```

2. **Configure AWS credentials**:
```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region (ap-southeast-1)
```

3. **Update Lambda functions**:
```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data/deployments/aws-lambda
./update-tunnel-url.sh "https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com"
```

Alternatively, update manually in AWS Console:
1. Go to AWS Lambda console
2. For each function (waterLevelLatest, moistureLatest, etc.)
3. Go to Configuration > Environment variables
4. Update TUNNEL_URL to: `https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com`
5. Save

## Testing the Complete Setup

Once tunnel is running and Lambda is updated:

```bash
# Test water level data
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/water-levels/latest

# Test moisture data
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/moisture/latest

# Test AOS weather data
curl -H "X-API-Key: rid-ms-prod-key1" \
  https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1/public/aos/latest
```

## Troubleshooting

### Tunnel not starting
```bash
# Check for existing processes
ps aux | grep cloudflared | grep -v grep

# Kill existing processes if needed
pkill -f "cloudflared.*munbon-api"

# Check logs
tail -f /tmp/munbon-tunnel.log  # If using LaunchAgent
pm2 logs munbon-tunnel           # If using PM2
docker logs munbon-cloudflare-tunnel  # If using Docker
```

### Connection errors
```bash
# Verify tunnel is connected
cloudflared tunnel info munbon-api

# Test local API directly
curl -H "x-internal-key: munbon-internal-f3b89263126548" http://localhost:3000/health

# Test through tunnel
curl -H "x-internal-key: munbon-internal-f3b89263126548" \
  https://f3b89263-1265-4843-b08c-5391e73e8c75.cfargotunnel.com/health
```

## Best Practices

1. **Use PM2 or systemd** for production reliability
2. **Monitor tunnel health** with automated checks
3. **Set up alerts** for tunnel downtime
4. **Keep credentials secure** in ~/.cloudflared/
5. **Regular updates**: `cloudflared update` (if not using package manager)

## Cost Summary

- Cloudflare Tunnel: **FREE**
- No bandwidth limits for reasonable use
- No time restrictions
- Includes DDoS protection
- SSL/TLS termination included