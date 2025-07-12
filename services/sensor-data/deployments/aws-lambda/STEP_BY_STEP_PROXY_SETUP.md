# Step-by-Step: AWS Lambda Proxy Setup (Free Tier)

## Overview
This setup allows your AWS Lambda functions to access your local TimescaleDB and MSSQL databases without migrating data or paying for RDS.

## Architecture
```
External API Users
       ↓
AWS API Gateway (https://26ikiexzlc.execute-api.ap-southeast-1.amazonaws.com)
       ↓
Lambda Functions (Proxy)
       ↓
Cloudflare Tunnel (Free)
       ↓
Your Local API (Port 3000)
       ↓
TimescaleDB (5433) + MSSQL (1433)
```

## Step 1: Set Up Cloudflare Tunnel (15 minutes)

### 1.1 Install Cloudflared
```bash
# macOS
brew install cloudflared

# Verify installation
cloudflared version
```

### 1.2 Create Cloudflare Account (Free)
- Go to https://dash.cloudflare.com/sign-up
- Sign up for free account
- No credit card required

### 1.3 Authenticate
```bash
cloudflared tunnel login
# This will open a browser - select your domain or use Cloudflare's free subdomain
```

### 1.4 Create Tunnel
```bash
cloudflared tunnel create munbon-api

# Output will show:
# Tunnel credentials written to /Users/YOUR_USER/.cloudflared/TUNNEL_ID.json
# Created tunnel munbon-api with id abc123def456
```

### 1.5 Create Configuration
```bash
# Get your tunnel ID from previous step
export TUNNEL_ID=abc123def456  # Replace with your actual tunnel ID

# Create config file
cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  - service: http://localhost:3000
EOF
```

### 1.6 Start Tunnel (for testing)
```bash
# Run in foreground to test
cloudflared tunnel run munbon-api

# You'll see:
# INF Connection registered connIndex=0 connection=abc123 ip=198.41.x.x
# Your tunnel is live at: https://abc123def456.cfargotunnel.com
```

## Step 2: Create Local Unified API (20 minutes)

### 2.1 Navigate to sensor-data directory
```bash
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data
```

### 2.2 Create the unified API
```bash
# Copy the generated template
cp deployments/aws-lambda/local-unified-api.js src/unified-api.js

# Install additional dependencies
npm install mssql
```

### 2.3 Update the unified API with your configs
Edit `src/unified-api.js`:
```javascript
// Update MSSQL connection for your SCADA
const mssqlConfig = {
  server: 'localhost',  // or your MSSQL server IP
  database: 'SCADA_DB', // your actual database name
  user: 'sa',
  password: 'your_password',
  options: {
    encrypt: false,
    trustServerCertificate: true,
    port: 1433  // default MSSQL port
  }
};

// Add authentication
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'munbon-internal-' + require('crypto').randomBytes(16).toString('hex');
console.log('Internal API Key:', INTERNAL_API_KEY);
```

### 2.4 Start the unified API
```bash
# Set environment variable
export INTERNAL_API_KEY=munbon-internal-abc123def456

# Run the API
node src/unified-api.js

# Should see: "Unified API running on port 3000"
```

### 2.5 Test locally
```bash
# In another terminal
curl -H "X-Internal-Key: munbon-internal-abc123def456" \
  http://localhost:3000/api/v1/sensors/combined/latest
```

## Step 3: Update Lambda Functions (15 minutes)

### 3.1 Update data-exposure-handler.ts
```bash
cd deployments/aws-lambda

# Replace the existing handler with proxy version
cp lambda-proxy-handler.ts data-exposure-handler.ts

# Update with your tunnel URL
sed -i '' "s|https://munbon-api.YOUR_DOMAIN.com|https://abc123def456.cfargotunnel.com|g" data-exposure-handler.ts
```

### 3.2 Update all handler functions
Edit `data-exposure-handler.ts` to add all endpoints:
```typescript
// Add handlers for each endpoint
export const waterLevelTimeseries: APIGatewayProxyHandler = async (event) => {
  const date = event.queryStringParameters?.date;
  return proxyToInternal('/sensors/water-level/timeseries', { date });
};

export const moistureLatest: APIGatewayProxyHandler = async (event) => {
  return proxyToInternal('/sensors/moisture/latest');
};

// ... add all other handlers
```

### 3.3 Build the functions
```bash
# Install dependencies if needed
npm install

# Build
npm run build
```

## Step 4: Deploy Updated Lambda (10 minutes)

### 4.1 Update environment variables
```bash
# Update Lambda environment
./update-lambda-env.sh dev

# Or manually in serverless-data-api.yml:
environment:
  INTERNAL_API_URL: https://abc123def456.cfargotunnel.com
  INTERNAL_API_KEY: munbon-internal-abc123def456
  EXTERNAL_API_KEYS: rid-ms-prod-key1,test-key-123
```

### 4.2 Deploy
```bash
serverless deploy --config serverless-data-api.yml --stage dev
```

## Step 5: Test Complete Setup (5 minutes)

### 5.1 Test via deployed Lambda
```bash
# Test water levels endpoint
curl -H "X-API-Key: test-key-123" \
  https://26ikiexzlc.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/public/water-levels/latest

# Test with date parameter (Buddhist calendar)
curl -H "X-API-Key: test-key-123" \
  "https://26ikiexzlc.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/public/water-levels/timeseries?date=30/06/2568"
```

### 5.2 Monitor logs
```bash
# Check Lambda logs
serverless logs -f waterLevelLatest --tail

# Check local API logs
# (in the terminal running unified-api.js)
```

## Step 6: Production Setup

### 6.1 Run tunnel as service
```bash
# Install as service (macOS)
sudo cloudflared service install
sudo cloudflared service start

# Or use PM2
npm install -g pm2
pm2 start cloudflared -- tunnel run munbon-api
pm2 save
pm2 startup
```

### 6.2 Run unified API as service
```bash
# Create ecosystem file
cat > ecosystem.config.js << EOF
module.exports = {
  apps: [{
    name: 'munbon-unified-api',
    script: './src/unified-api.js',
    env: {
      NODE_ENV: 'production',
      INTERNAL_API_KEY: 'munbon-internal-abc123def456'
    }
  }]
}
EOF

# Start with PM2
pm2 start ecosystem.config.js
pm2 save
```

## Troubleshooting

### If tunnel connection fails:
```bash
# Check tunnel status
cloudflared tunnel list
cloudflared tunnel info munbon-api

# Restart tunnel
cloudflared tunnel cleanup munbon-api
cloudflared tunnel run munbon-api
```

### If Lambda timeout:
- Increase timeout in serverless-data-api.yml:
```yaml
provider:
  timeout: 30  # seconds
```

### If database connection fails:
- Ensure local API can access both databases
- Check firewall rules
- Verify database credentials

## Cost Summary
- **Cloudflare Tunnel**: FREE
- **Lambda Invocations**: $0.0000002 per request
- **API Gateway**: $0.0000035 per request
- **Monthly estimate for 100k requests**: ~$0.50

## Security Notes
1. The tunnel URL is public but requires Internal API Key
2. Lambda validates External API Keys
3. Databases remain completely local
4. Use strong, unique API keys
5. Rotate keys regularly

## Next Steps
1. Add monitoring with CloudWatch
2. Set up alerts for errors
3. Implement caching in Lambda
4. Add rate limiting
5. Configure custom domain (optional)