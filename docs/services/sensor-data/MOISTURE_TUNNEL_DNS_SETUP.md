# DNS Setup for Moisture Sensor Tunnel

## Overview
This guide explains how to set up DNS records for the moisture sensor tunnel using beautifyai.io domain.

## Required DNS Records

### 1. Primary Moisture Endpoint
```
Type: CNAME
Name: munbon-moisture
Target: [TUNNEL_ID].cfargotunnel.com
TTL: Auto (or 300 seconds)
Proxy: Yes (if using Cloudflare)
```

### 2. Health Check Endpoint
```
Type: CNAME
Name: munbon-moisture-health
Target: [TUNNEL_ID].cfargotunnel.com
TTL: Auto (or 300 seconds)
Proxy: Yes (if using Cloudflare)
```

## Step-by-Step Setup

### Option A: Using Cloudflare Dashboard

1. **Login to Cloudflare**
   - Go to https://dash.cloudflare.com
   - Select the `beautifyai.io` domain

2. **Navigate to DNS Management**
   - Click on "DNS" in the left sidebar
   - Click "Add record"

3. **Add Primary Endpoint**
   - Type: CNAME
   - Name: `munbon-moisture`
   - Target: `[TUNNEL_ID].cfargotunnel.com`
   - Proxy status: Proxied (orange cloud ON)
   - TTL: Auto
   - Click "Save"

4. **Add Health Check Endpoint**
   - Repeat step 3 with name: `munbon-moisture-health`

### Option B: Using Cloudflare CLI

```bash
# Add primary endpoint
cloudflared tunnel route dns [TUNNEL_ID] munbon-moisture.beautifyai.io

# Add health check endpoint  
cloudflared tunnel route dns [TUNNEL_ID] munbon-moisture-health.beautifyai.io
```

### Option C: Using Cloudflare API

```bash
# Get zone ID first
ZONE_ID=$(curl -X GET "https://api.cloudflare.com/client/v4/zones?name=beautifyai.io" \
  -H "Authorization: Bearer $CF_API_TOKEN" | jq -r '.result[0].id')

# Add primary endpoint
curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "CNAME",
    "name": "munbon-moisture",
    "content": "[TUNNEL_ID].cfargotunnel.com",
    "ttl": 1,
    "proxied": true
  }'

# Add health check endpoint
curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "CNAME",
    "name": "munbon-moisture-health",
    "content": "[TUNNEL_ID].cfargotunnel.com",
    "ttl": 1,
    "proxied": true
  }'
```

## Verify DNS Configuration

### 1. Check DNS Propagation
```bash
# Using dig
dig munbon-moisture.beautifyai.io CNAME
dig munbon-moisture-health.beautifyai.io CNAME

# Using nslookup
nslookup munbon-moisture.beautifyai.io
nslookup munbon-moisture-health.beautifyai.io

# Check global propagation
curl https://dns.google/resolve?name=munbon-moisture.beautifyai.io&type=CNAME
```

### 2. Test Endpoints (after tunnel is running)
```bash
# Health check
curl -v https://munbon-moisture-health.beautifyai.io/health

# Test with legacy TLS
curl --tlsv1.0 https://munbon-moisture.beautifyai.io/health

# Test telemetry endpoint
curl -X POST https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "sensorType": "moisture",
    "sensorId": "TEST-001",
    "data": {
      "humid_hi": "45",
      "humid_low": "52"
    }
  }'
```

## Troubleshooting

### DNS Not Resolving
1. Wait 5-10 minutes for propagation
2. Clear DNS cache: `sudo dscacheutil -flushcache` (macOS)
3. Check if records are proxied through Cloudflare

### SSL/TLS Errors
1. Ensure Cloudflare SSL mode is "Full" or "Flexible"
2. Check tunnel is running: `pm2 status munbon-moisture-tunnel`
3. Verify tunnel config: `cat ~/.cloudflared/config-moisture.yml`

### Connection Refused
1. Check moisture service is running on port 3005
2. Verify tunnel is connected: `pm2 logs munbon-moisture-tunnel`
3. Test local endpoint: `curl http://localhost:3005/health`

## Security Considerations

1. **Legacy TLS Support**: This tunnel supports TLS 1.0+ for legacy sensors
2. **IP Restrictions**: Consider adding IP allowlists if sensor IPs are known
3. **Rate Limiting**: Enable Cloudflare rate limiting to prevent abuse
4. **Authentication**: Ensure proper token validation in the application

## Monitoring

1. **Cloudflare Analytics**: Monitor traffic at dash.cloudflare.com
2. **Tunnel Status**: `cloudflared tunnel info munbon-moisture`
3. **Application Logs**: `pm2 logs munbon-moisture-tunnel`
4. **Health Checks**: Set up uptime monitoring for the health endpoint