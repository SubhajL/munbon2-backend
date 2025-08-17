# Cloudflare Tunnel Quick Start Guide

## Option 1: Temporary URL (Fastest - 2 minutes)
```bash
# Just run this command:
cloudflared tunnel --url http://localhost:3001

# You'll get a URL like:
# https://amusing-tiger-happy.trycloudflare.com
```

## Option 2: Free Domain + Cloudflare (30 minutes)

### Step 1: Get Free Domain
#### Using Freenom:
1. Go to https://www.freenom.com
2. Search: `munbon-api` → Get `munbon-api.tk` free
3. Register (free for 12 months)

#### Using DuckDNS:
1. Go to https://www.duckdns.org
2. Login with GitHub/Google
3. Add domain: `munbon-api` → Get `munbon-api.duckdns.org`

### Step 2: Run Setup Script
```bash
cd services/sensor-data
./setup-free-domain-cloudflare.sh
```

The script will:
- Guide you through Cloudflare setup
- Create tunnel automatically
- Generate all configurations

### Step 3: Start Using API

Your API endpoints will be:
- `https://munbon-api.tk/api/v1/public/moisture/latest`
- `https://munbon-api.tk/api/v1/public/water-levels/latest`
- `https://munbon-api.tk/api/v1/public/aos/latest`

## Example API Calls

### Get Latest Moisture Data:
```bash
curl -H "X-API-Key: your-api-key" \
  https://munbon-api.tk/api/v1/public/moisture/latest
```

### Get Today's Water Level Data:
```bash
curl -H "X-API-Key: your-api-key" \
  "https://munbon-api.tk/api/v1/public/water-levels/timeseries?date=11/06/2568"
```

### Get AOS Weather Statistics:
```bash
curl -H "X-API-Key: your-api-key" \
  "https://munbon-api.tk/api/v1/public/aos/statistics?date=11/06/2568"
```

## API Key Setup

1. Generate API keys:
```bash
./generate-api-keys.sh
```

2. Add to your `.env`:
```
EXTERNAL_API_KEYS=rid-ms-prod-xxxxx,tmd-weather-yyyyy
```

3. Restart sensor-data service

## Troubleshooting

### Tunnel not starting?
```bash
# Check if service is running
sudo systemctl status cloudflared

# View logs
sudo journalctl -u cloudflared -f
```

### API returns 401 Unauthorized?
- Check API key is included in header: `X-API-Key: your-key`
- Verify key is in EXTERNAL_API_KEYS environment variable

### Can't access domain?
- Wait 5 minutes for DNS propagation
- Try: `nslookup your-domain.tk`
- Verify Cloudflare nameservers are set correctly

## Free Domain Comparison

| Provider | Domain | Setup Time | Reliability | Renewal |
|----------|--------|------------|-------------|---------|
| Cloudflare Tunnel (temp) | random.trycloudflare.com | 2 min | Changes on restart | N/A |
| Freenom | .tk, .ml, .ga | 20 min | Good | Free yearly |
| DuckDNS | .duckdns.org | 10 min | Excellent | Permanent |

## Recommended for Production
Use DuckDNS for reliability:
- Permanent subdomain
- No renewal needed
- 99.9% uptime
- Simple API updates