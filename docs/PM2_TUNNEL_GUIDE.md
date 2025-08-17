# PM2 Cloudflare Tunnel Guide

## Overview

The PM2 ecosystem now includes **two Cloudflare tunnels**:

1. **`cloudflare-tunnel`** - Exposes local API (port 3000) to internet
2. **`cloudflare-tunnel-external`** - Provides TLS 1.0+ support for AWS API Gateway

## Quick Start

### Start Everything
```bash
# Start all services including tunnels
pm2 start pm2-ecosystem.config.js

# Or start only the external tunnel
pm2 start cloudflare-tunnel-external
```

### Get Tunnel URLs
```bash
# Check all tunnel URLs
./get-tunnel-urls.sh

# Or check PM2 logs
pm2 logs cloudflare-tunnel-external --lines 50
```

### Monitor Status
```bash
# Check all services
pm2 status

# Monitor specific tunnel
pm2 monit cloudflare-tunnel-external
```

## Service Details

### cloudflare-tunnel-external
- **Purpose**: Provides legacy TLS/cipher support for AWS API
- **Target**: `https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com`
- **Supports**: TLS 1.0, 1.1, 1.2, 1.3 and legacy cipher suites
- **URL File**: `./services/sensor-data/tunnel-external-url.txt`
- **Logs**: `./logs/tunnel-external-*.log`

### external-tunnel-monitor
- **Purpose**: Extracts and saves tunnel URL every 60 seconds
- **Output**: Updates `tunnel-external-url.txt` with current URL
- **Logs**: `./logs/external-tunnel-monitor-*.log`

## Common Commands

### Start Services
```bash
# Start all services
pm2 start pm2-ecosystem.config.js

# Start only external tunnel services
pm2 start cloudflare-tunnel-external external-tunnel-monitor

# Start with specific environment
pm2 start pm2-ecosystem.config.js --env production
```

### Check Status
```bash
# List all services
pm2 list

# Get detailed info
pm2 info cloudflare-tunnel-external

# View logs
pm2 logs cloudflare-tunnel-external
pm2 logs external-tunnel-monitor
```

### Restart/Stop
```bash
# Restart tunnel
pm2 restart cloudflare-tunnel-external

# Stop tunnel
pm2 stop cloudflare-tunnel-external

# Delete from PM2
pm2 delete cloudflare-tunnel-external
```

### Save Configuration
```bash
# Save current PM2 process list
pm2 save

# Setup PM2 to restart on system reboot
pm2 startup
```

## Tunnel URLs

After starting, your endpoints will be available at:

### Original AWS Endpoint
```
https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/{token}/telemetry
```

### Cloudflare Tunnel (with TLS 1.0+ support)
```
https://your-tunnel-subdomain.trycloudflare.com/dev/api/v1/{token}/telemetry
```

Both endpoints work simultaneously!

## Testing Legacy TLS

Test TLS 1.0:
```bash
TUNNEL_URL=$(cat ./services/sensor-data/tunnel-external-url.txt)
curl --tlsv1.0 -X GET $TUNNEL_URL/dev/api/v1/munbon-m2m-moisture/attributes
```

Test TLS 1.1:
```bash
curl --tlsv1.1 -X GET $TUNNEL_URL/dev/api/v1/munbon-m2m-moisture/attributes
```

Test with legacy cipher:
```bash
curl --ciphers 'AES256-SHA' -X GET $TUNNEL_URL/dev/api/v1/munbon-m2m-moisture/attributes
```

## Troubleshooting

### Tunnel URL not appearing
```bash
# Check logs
pm2 logs cloudflare-tunnel-external --lines 100

# Manually extract URL
grep -o 'https://[a-zA-Z0-9\-]*\.trycloudflare\.com' ./logs/tunnel-external-out.log | tail -1

# Restart tunnel
pm2 restart cloudflare-tunnel-external
```

### Cloudflared not installed
```bash
# macOS
brew install cloudflare/cloudflare/cloudflared

# Linux
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

### Port conflicts
The external tunnel doesn't use local ports, so there should be no conflicts.

## Integration with Existing Services

The PM2 ecosystem file manages:
- **API Services**: unified-api, sensor-data-service
- **Tunnels**: cloudflare-tunnel, cloudflare-tunnel-external
- **Monitors**: tunnel-monitor, external-tunnel-monitor
- **Workers**: sensor-consumer
- **GIS Services**: gis-api, gis-queue-processor

All services can run together without conflicts.

## Production Considerations

For production, consider:
1. Using permanent Cloudflare tunnels instead of quick tunnels
2. Setting up proper domain names
3. Implementing rate limiting
4. Adding authentication headers
5. Monitoring tunnel stability

## Logs Location

All logs are stored in `./logs/`:
- `tunnel-external-out.log` - Tunnel output
- `tunnel-external-error.log` - Tunnel errors
- `external-tunnel-monitor-out.log` - URL monitoring logs