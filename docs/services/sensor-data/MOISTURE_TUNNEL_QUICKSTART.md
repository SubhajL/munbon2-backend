# Moisture Tunnel Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### 1. Run Setup Script
```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data
./setup-moisture-tunnel.sh
```

This will:
- Create Cloudflare tunnel named `munbon-moisture`
- Generate configuration files
- Create PM2 startup scripts
- Output the tunnel ID needed for DNS

### 2. Configure DNS

Add these CNAME records to beautifyai.io:

| Name | Type | Target | Proxy |
|------|------|--------|-------|
| munbon-moisture | CNAME | [TUNNEL_ID].cfargotunnel.com | Yes |
| munbon-moisture-health | CNAME | [TUNNEL_ID].cfargotunnel.com | Yes |

Replace [TUNNEL_ID] with the ID from step 1.

### 3. Start Services

```bash
# Start moisture monitoring service
cd /Users/subhajlimanond/dev/munbon2-backend/services/moisture-monitoring
npm run dev  # or npm start for production

# Start moisture tunnel
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data
./start-moisture-tunnel.sh
```

### 4. Test Everything
```bash
./test-dual-tunnel.sh
```

## 📡 Endpoints

### Public URLs (via tunnel)
- Telemetry: `https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry`
- Health: `https://munbon-moisture-health.beautifyai.io/health`
- Current Data: `https://munbon-moisture.beautifyai.io/api/v1/moisture/current`
- Alerts: `https://munbon-moisture.beautifyai.io/api/v1/moisture/alerts`

### Legacy Sensor Test
```bash
# Test with TLS 1.0
curl --tlsv1.0 -X POST https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "sensorType": "moisture",
    "sensorId": "00002-00003",
    "data": {
      "humid_hi": "45",
      "humid_low": "52",
      "temp_hi": "28.5",
      "flood": "no",
      "sensor_batt": "385"
    }
  }'
```

## 🔧 Management

### View Status
```bash
# Check tunnel status
pm2 status munbon-moisture-tunnel

# View logs
pm2 logs munbon-moisture-tunnel

# Check both tunnels
pm2 list | grep tunnel
```

### Restart/Stop
```bash
# Restart tunnel
pm2 restart munbon-moisture-tunnel

# Stop tunnel
pm2 stop munbon-moisture-tunnel

# Remove from PM2
pm2 delete munbon-moisture-tunnel
```

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│ Moisture Sensor │────▶│ munbon-moisture.     │────▶│ Moisture        │
│ (Legacy TLS)    │     │ beautifyai.io        │     │ Service (:3005) │
└─────────────────┘     │ (Cloudflare Tunnel)  │     └─────────────────┘
                        └──────────────────────┘              │
                                                              ▼
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│ External APIs   │────▶│ munbon-api-proxy.    │────▶│ Unified API     │
│                 │     │ beautifyai.io        │     │ (:3000)         │
└─────────────────┘     │ (Cloudflare Tunnel)  │     └─────────────────┘
                        └──────────────────────┘
```

## ❓ Troubleshooting

### Tunnel Won't Start
```bash
# Kill existing tunnels
pkill -f cloudflared

# Check for port conflicts
lsof -i :3005

# Restart fresh
./setup-moisture-tunnel.sh
```

### DNS Not Working
```bash
# Check DNS propagation
dig munbon-moisture.beautifyai.io CNAME

# Wait 5-10 minutes for propagation
# Or use Google DNS: dig @8.8.8.8 munbon-moisture.beautifyai.io
```

### Legacy TLS Issues
```bash
# Test supported TLS versions
curl -v --tlsv1.0 https://munbon-moisture.beautifyai.io/health
curl -v --tlsv1.1 https://munbon-moisture.beautifyai.io/health

# Check cipher support
openssl s_client -connect munbon-moisture.beautifyai.io:443 -cipher RC4-SHA
```

## 📊 Monitoring

1. **Tunnel Metrics**: `pm2 monit`
2. **Cloudflare Dashboard**: https://dash.cloudflare.com
3. **Application Logs**: `pm2 logs munbon-moisture-tunnel --lines 100`
4. **Health Checks**: https://munbon-moisture-health.beautifyai.io/health

## 🔒 Security Notes

- This tunnel supports legacy TLS 1.0+ for old sensors
- Consider IP allowlisting if sensor IPs are static
- Enable rate limiting in Cloudflare dashboard
- Monitor for unusual traffic patterns
- Validate tokens in application layer