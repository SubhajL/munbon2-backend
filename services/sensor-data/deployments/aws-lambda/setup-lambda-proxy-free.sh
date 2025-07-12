#!/bin/bash

# Setup Lambda as API Proxy (Free Tier Solution)
# This allows Lambda to call your local APIs without moving databases

echo "=== Lambda API Proxy Setup (Free Tier) ==="
echo ""
echo "This solution keeps your databases local and uses Lambda as a proxy"
echo ""

# Step 1: Setup Cloudflare Tunnel (free)
cat > setup-cloudflare-tunnel.md << 'EOF'
# Cloudflare Tunnel Setup (Free)

## 1. Install Cloudflared
```bash
# macOS
brew install cloudflared

# Or download from: https://github.com/cloudflare/cloudflared/releases
```

## 2. Login to Cloudflare
```bash
cloudflared tunnel login
```

## 3. Create Tunnel
```bash
cloudflared tunnel create munbon-api
```

## 4. Create config file (~/.cloudflared/config.yml)
```yaml
tunnel: munbon-api
credentials-file: /Users/YOUR_USER/.cloudflared/TUNNEL_ID.json

ingress:
  - hostname: munbon-api.YOUR_DOMAIN.com
    service: http://localhost:3000
  - service: http_status:404
```

## 5. Route traffic
```bash
cloudflared tunnel route dns munbon-api munbon-api.YOUR_DOMAIN.com
```

## 6. Run tunnel
```bash
cloudflared tunnel run munbon-api
```

Your local API is now accessible at: https://munbon-api.YOUR_DOMAIN.com
EOF

# Step 2: Update Lambda to use proxy
cat > lambda-proxy-handler.ts << 'EOF'
import { APIGatewayProxyHandler } from 'aws-lambda';

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'https://munbon-api.YOUR_DOMAIN.com';
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'your-internal-key';

// Helper to proxy requests to internal API
const proxyToInternal = async (path: string, queryParams?: any) => {
  const url = new URL(`${INTERNAL_API_URL}/api/v1${path}`);
  
  if (queryParams) {
    Object.keys(queryParams).forEach(key => 
      url.searchParams.append(key, queryParams[key])
    );
  }

  const response = await fetch(url.toString(), {
    headers: {
      'X-Internal-Key': INTERNAL_API_KEY,
      'X-Forwarded-For': 'AWS Lambda'
    }
  });

  if (!response.ok) {
    throw new Error(`Internal API error: ${response.status}`);
  }

  return response.json();
};

// Water level latest endpoint
export const waterLevelLatest: APIGatewayProxyHandler = async (event) => {
  try {
    // Validate external API key
    const apiKey = event.headers['X-API-Key'] || event.headers['x-api-key'];
    const validKeys = (process.env.EXTERNAL_API_KEYS || '').split(',');
    
    if (!apiKey || !validKeys.includes(apiKey)) {
      return {
        statusCode: 401,
        body: JSON.stringify({ error: 'Invalid API key' })
      };
    }

    // Proxy to internal API
    const data = await proxyToInternal('/sensors/water-level/latest');
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify(data)
    };
  } catch (error) {
    console.error('Error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal server error' })
    };
  }
};

// Similar handlers for other endpoints...
EOF

# Step 3: Alternative - ngrok setup (simpler but requires account for persistent URLs)
cat > setup-ngrok.md << 'EOF'
# ngrok Setup (Alternative to Cloudflare)

## 1. Install ngrok
```bash
brew install ngrok
# Or download from: https://ngrok.com/download
```

## 2. Sign up for free account
- Go to https://ngrok.com/signup
- Get your auth token

## 3. Authenticate
```bash
ngrok authtoken YOUR_AUTH_TOKEN
```

## 4. Run tunnel
```bash
ngrok http 3000
```

Free tier limitations:
- Random URL each time (unless you pay)
- 40 connections/minute
- 1 online tunnel

For production, use Cloudflare Tunnel instead.
EOF

# Step 4: Create combined API that accesses both databases
cat > local-unified-api.js << 'EOF'
// Unified API that Lambda will call
// This runs locally and has access to both TimescaleDB and MSSQL

const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');

const app = express();

// TimescaleDB connection
const timescaleDB = new Pool({
  host: 'localhost',
  port: 5433,
  database: 'sensor_data',
  user: 'postgres',
  password: 'postgres'
});

// MSSQL connection (for SCADA data)
const mssqlConfig = {
  server: 'localhost',
  database: 'SCADA_DB',
  user: 'sa',
  password: 'your_password',
  options: {
    encrypt: false,
    trustServerCertificate: true
  }
};

// Middleware for internal API key
app.use((req, res, next) => {
  const apiKey = req.headers['x-internal-key'];
  if (apiKey !== process.env.INTERNAL_API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
});

// Endpoint that combines data from both databases
app.get('/api/v1/sensors/combined/latest', async (req, res) => {
  try {
    // Get sensor data from TimescaleDB
    const sensorData = await timescaleDB.query(`
      SELECT sensor_id, data, timestamp 
      FROM sensor_readings 
      WHERE timestamp > NOW() - INTERVAL '1 hour'
      ORDER BY timestamp DESC
    `);

    // Get SCADA data from MSSQL
    await sql.connect(mssqlConfig);
    const scadaData = await sql.query`
      SELECT TagName, Value, Timestamp 
      FROM ScadaData 
      WHERE Timestamp > DATEADD(hour, -1, GETDATE())
    `;

    // Combine and return
    res.json({
      sensors: sensorData.rows,
      scada: scadaData.recordset,
      timestamp: new Date()
    });
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: 'Database error' });
  }
});

app.listen(3000, () => {
  console.log('Unified API running on port 3000');
});
EOF

# Step 5: Environment variables for Lambda
cat > lambda-proxy-env.txt << 'EOF'
# Environment variables for Lambda functions

# Your tunnel URL (Cloudflare or ngrok)
INTERNAL_API_URL=https://munbon-api.YOUR_DOMAIN.com

# Internal API key (generate a secure one)
INTERNAL_API_KEY=internal-key-$(openssl rand -hex 16)

# External API keys (for clients)
EXTERNAL_API_KEYS=rid-ms-prod-key1,rid-ms-dev-key2,test-key-123

# Stage
STAGE=dev
EOF

echo ""
echo "=== Setup Complete ==="
echo ""
echo "This free-tier solution:"
echo "✅ Keeps your TimescaleDB and MSSQL databases local"
echo "✅ Uses Lambda as a secure proxy layer"
echo "✅ Provides public API without exposing your databases"
echo "✅ Costs only Lambda execution fees (very minimal)"
echo ""
echo "Next steps:"
echo "1. Set up Cloudflare Tunnel (recommended) or ngrok"
echo "2. Run your local unified API that accesses both databases"
echo "3. Update Lambda functions to proxy requests"
echo "4. Deploy Lambda with tunnel URL configured"
echo ""
echo "Files created:"
echo "- setup-cloudflare-tunnel.md: Cloudflare Tunnel instructions"
echo "- setup-ngrok.md: ngrok instructions (alternative)"
echo "- lambda-proxy-handler.ts: Lambda proxy implementation"
echo "- local-unified-api.js: Local API that accesses both DBs"
echo "- lambda-proxy-env.txt: Environment variables"
echo ""
echo "Estimated monthly cost: <$1 (Lambda execution only)"