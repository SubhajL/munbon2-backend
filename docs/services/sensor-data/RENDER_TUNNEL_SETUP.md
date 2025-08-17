# Render + Local Database Setup Guide

This guide shows how to deploy the unified API to Render while keeping databases local.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   AWS Lambda    │────▶│  Render.com API  │────▶│  Ngrok/Tunnel   │
│  (API Gateway)  │     │  (Cloud)         │     │  (Your Local)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           │
                                                           ▼
                                                   ┌───────────────┐
                                                   │ Local DBs:    │
                                                   │ - TimescaleDB │
                                                   │ - MSSQL       │
                                                   └───────────────┘
```

## Step 1: Set Up Tunnel to Local Databases

### Option A: Ngrok (Easiest)

```bash
# Install ngrok
brew install ngrok

# Expose TimescaleDB port
ngrok tcp 5433

# You'll get a URL like: tcp://2.tcp.ngrok.io:12345
# Save this URL - you'll need it for Render
```

### Option B: Cloudflare Tunnel (More Stable)

```bash
# Install cloudflared
brew install cloudflared

# Create tunnel
cloudflared tunnel create munbon-db

# Run tunnel for TimescaleDB
cloudflared tunnel run --url tcp://localhost:5433 munbon-db
```

### Option C: LocalTunnel (Free Alternative)

```bash
# Install localtunnel
npm install -g localtunnel

# Expose TimescaleDB
lt --port 5433 --subdomain munbon-timescale
```

## Step 2: Create Render-Ready API

Create `src/unified-api-cloud.js`:

```javascript
const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// Parse tunnel URL for TimescaleDB
function parseNgrokUrl(url) {
  // Example: tcp://2.tcp.ngrok.io:12345 -> host: 2.tcp.ngrok.io, port: 12345
  const match = url.match(/tcp:\/\/(.+):(\d+)/);
  if (match) {
    return { host: match[1], port: parseInt(match[2]) };
  }
  return { host: 'localhost', port: 5433 };
}

const tunnelConfig = parseNgrokUrl(process.env.TIMESCALE_TUNNEL_URL || '');

// TimescaleDB through tunnel
const timescaleDB = new Pool({
  host: tunnelConfig.host,
  port: tunnelConfig.port,
  database: process.env.TIMESCALE_DB || 'sensor_data',
  user: process.env.TIMESCALE_USER || 'postgres',
  password: process.env.TIMESCALE_PASSWORD || 'postgres',
  ssl: false
});

// MSSQL (already accessible externally)
const mssqlConfig = {
  server: 'moonup.hopto.org',
  database: 'db_scada',
  user: 'sa',
  password: 'bangkok1234',
  options: {
    encrypt: false,
    trustServerCertificate: true,
    port: 1433
  }
};

// Your API endpoints here...
```

## Step 3: Deploy to Render

1. **Push to GitHub** with the new file

2. **Create Web Service on Render**:
   - Connect GitHub repo
   - Build Command: `npm install --production`
   - Start Command: `node src/unified-api-cloud.js`

3. **Set Environment Variables**:
   ```
   INTERNAL_API_KEY=munbon-internal-f3b89263126548
   TIMESCALE_TUNNEL_URL=tcp://2.tcp.ngrok.io:12345
   TIMESCALE_DB=sensor_data
   TIMESCALE_USER=postgres
   TIMESCALE_PASSWORD=postgres
   ```

## Step 4: Keep Tunnel Alive

### For Ngrok:
```bash
# Create a script to auto-restart
while true; do
  ngrok tcp 5433
  sleep 5
done
```

### For Production: Use Cloudflare Tunnel
- More stable
- Custom domain support
- No random URL changes

## Step 5: Update AWS Lambda

```bash
# Update Lambda to use Render URL
aws lambda update-function-configuration \
  --function-name munbon-sensor-handler \
  --environment "Variables={
    UNIFIED_API_URL=https://munbon-unified-api.onrender.com,
    INTERNAL_API_KEY=munbon-internal-f3b89263126548
  }" \
  --region ap-southeast-1
```

## Important Notes

1. **Tunnel URL Changes**: Ngrok free tier gives new URLs on restart
2. **Update Render**: When tunnel URL changes, update env vars on Render
3. **Keep Tunnel Running**: Use tmux/screen or a process manager
4. **Security**: The tunnel is the security boundary - ensure it's properly configured

## Testing

```bash
# Test tunnel connection
curl http://2.tcp.ngrok.io:12345

# Test Render API
curl https://munbon-unified-api.onrender.com/health

# Test full flow
curl https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest \
  -H "x-api-key: your-key"
```

## Alternative: Expose Databases Directly

If you have a static IP or dynamic DNS, you could:
1. Configure your router to forward ports
2. Use dynamic DNS service
3. Configure firewall rules
4. Connect Render directly to your IP

This avoids tunnel complexity but requires network configuration.