#!/bin/bash

# Deploy to Railway.app - The easiest deployment option
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "Deploy to Railway.app"
echo "======================================"
echo -e "${NC}"

# Create railway.json
echo -e "${GREEN}Creating Railway configuration...${NC}"
cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "node src/unified-api-v2.js",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF

# Create Procfile for Railway
cat > Procfile << 'EOF'
web: node src/unified-api-v2.js
EOF

# Create nixpacks.toml for better control
cat > nixpacks.toml << 'EOF'
[phases.setup]
nixPkgs = ["nodejs-18_x"]

[phases.install]
cmds = ["npm ci --only=production || npm install --production"]

[start]
cmd = "node src/unified-api-v2.js"
EOF

# Create .env.example for Railway
cat > .env.railway << 'EOF'
# Railway Environment Variables
NODE_ENV=production
PORT=3000

# Internal API Key (used by AWS Lambda)
INTERNAL_API_KEY=munbon-internal-f3b89263126548

# Database Configuration
# Railway will provide DATABASE_URL automatically when you add PostgreSQL
TIMESCALE_HOST=${{PGHOST}}
TIMESCALE_PORT=${{PGPORT}}
TIMESCALE_DB=${{PGDATABASE}}
TIMESCALE_USER=${{PGUSER}}
TIMESCALE_PASSWORD=${{PGPASSWORD}}

# External MSSQL for AOS Weather Data
MSSQL_HOST=moonup.hopto.org
MSSQL_PORT=1433
MSSQL_DB=db_scada
MSSQL_USER=sa
MSSQL_PASSWORD=bangkok1234
EOF

# Create deployment script
cat > railway-deploy.sh << 'EOF'
#!/bin/bash

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Installing Railway CLI..."
    npm install -g @railway/cli
fi

echo "Logging into Railway..."
railway login

echo "Creating new project..."
railway init

echo "Adding PostgreSQL database..."
railway add

echo "Setting environment variables..."
railway variables set NODE_ENV=production
railway variables set PORT=3000
railway variables set INTERNAL_API_KEY=munbon-internal-f3b89263126548
railway variables set MSSQL_HOST=moonup.hopto.org
railway variables set MSSQL_PORT=1433
railway variables set MSSQL_DB=db_scada
railway variables set MSSQL_USER=sa
railway variables set MSSQL_PASSWORD=bangkok1234

echo "Deploying to Railway..."
railway up

echo "Getting deployment URL..."
railway open
EOF

chmod +x railway-deploy.sh

# Create one-click deploy button HTML
cat > railway-button.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Deploy to Railway</title>
</head>
<body>
    <h1>Deploy Munbon Unified API to Railway</h1>
    <a href="https://railway.app/template/munbon-api">
        <img src="https://railway.app/button.svg" alt="Deploy on Railway">
    </a>
    
    <h2>Manual Setup:</h2>
    <ol>
        <li>Click the button above or go to <a href="https://railway.app">railway.app</a></li>
        <li>Sign in with GitHub</li>
        <li>Create new project from GitHub repo</li>
        <li>Add PostgreSQL database</li>
        <li>Deploy!</li>
    </ol>
</body>
</html>
EOF

# Create Railway-specific app file
cat > src/app-railway.js << 'EOF'
// Railway-optimized version
const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// Railway provides DATABASE_URL
const timescaleDB = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

// Internal API key
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || 'munbon-internal-f3b89263126548';

console.log('Starting Railway Unified API...');
console.log('Port:', process.env.PORT || 3000);
console.log('Database URL:', process.env.DATABASE_URL ? 'Configured' : 'Not configured');
EOF

# Append rest of the API code
tail -n +35 src/unified-api-v2.js >> src/app-railway.js

# Modify the last lines for Railway port binding
cat >> src/app-railway.js << 'EOF'

// Railway dynamic port binding
const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Railway Unified API running on port ${PORT}`);
  console.log('Internal API Key:', INTERNAL_API_KEY);
});
EOF

# Create test script
cat > test-railway.sh << 'EOF'
#!/bin/bash

# Get Railway URL from CLI or environment
RAILWAY_URL="${RAILWAY_URL:-$(railway open --json | jq -r .url)}"
API_KEY="munbon-internal-f3b89263126548"

if [ -z "$RAILWAY_URL" ]; then
    echo "Please set RAILWAY_URL or run 'railway open' to get URL"
    exit 1
fi

echo "Testing Railway deployment..."
echo "URL: $RAILWAY_URL"
echo ""

# Test health
echo "1. Testing health endpoint..."
curl -s "$RAILWAY_URL/health" | jq .

# Test API
echo -e "\n2. Testing API endpoint..."
curl -s "$RAILWAY_URL/api/v1/sensors/water-level/latest" \
  -H "x-internal-key: $API_KEY" | jq .

# Update Lambda
echo -e "\n3. Updating AWS Lambda..."
aws lambda update-function-configuration \
    --function-name munbon-sensor-handler \
    --environment "Variables={UNIFIED_API_URL=$RAILWAY_URL,INTERNAL_API_KEY=$API_KEY}" \
    --region ap-southeast-1

echo -e "\n4. Testing through Lambda..."
sleep 5
curl -s "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest" \
  -H "x-api-key: test-key-123" | jq .
EOF

chmod +x test-railway.sh

# Create quick start guide
cat > RAILWAY_QUICKSTART.md << 'EOF'
# Railway.app Quick Start Guide

## Why Railway?

- **Easiest deployment** - Just connect GitHub and click deploy
- **Free PostgreSQL** - Automatic database provisioning
- **GitHub integration** - Auto-deploy on push
- **One-click deployments** - No configuration needed
- **Built-in SSL** - HTTPS out of the box

## 🚀 Quick Deploy (2 minutes)

### Option 1: CLI Deploy
```bash
# Install CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway add postgresql
railway up

# Get URL
railway open
```

### Option 2: Web Deploy
1. Go to [railway.app](https://railway.app)
2. Sign in with GitHub
3. New Project → Deploy from GitHub repo
4. Select your repository
5. Add Database → PostgreSQL
6. Deploy!

## 🔧 Environment Variables

Railway will ask for these (or auto-detect from code):

```env
INTERNAL_API_KEY=munbon-internal-f3b89263126548
MSSQL_HOST=moonup.hopto.org
MSSQL_PORT=1433
MSSQL_DB=db_scada
MSSQL_USER=sa
MSSQL_PASSWORD=bangkok1234
```

## 📡 Update AWS Lambda

After deployment, update Lambda with your Railway URL:

```bash
# Get your Railway URL first
RAILWAY_URL=$(railway open --json | jq -r .url)

# Update Lambda
aws lambda update-function-configuration \
    --function-name munbon-sensor-handler \
    --environment "Variables={UNIFIED_API_URL=$RAILWAY_URL,INTERNAL_API_KEY=munbon-internal-f3b89263126548}" \
    --region ap-southeast-1
```

## 💰 Pricing

- **Free**: $5 credit/month (~ 500 hours)
- **Hobby**: $5/month for 24/7 uptime
- **Pro**: $20/month for production

## 🔍 Monitoring

View logs and metrics:
```bash
railway logs
railway status
```

Or use the web dashboard at [railway.app/dashboard](https://railway.app/dashboard)

## ⚡ Tips

1. Railway auto-scales based on traffic
2. Supports WebSockets out of the box
3. Can add custom domains for free
4. Automatic HTTPS on all deployments
5. Zero-downtime deployments

## 🆘 Troubleshooting

If deployment fails:
1. Check `railway logs`
2. Ensure all environment variables are set
3. Verify PostgreSQL is connected
4. Check build logs in dashboard

EOF

echo -e "\n${GREEN}======================================"
echo "Railway.app Deployment Setup Complete!"
echo "======================================"
echo -e "${NC}"
echo "Deploy with ONE command:"
echo -e "${YELLOW}./railway-deploy.sh${NC}"
echo ""
echo "Or manually:"
echo "1. Go to https://railway.app"
echo "2. Connect GitHub and deploy"
echo ""
echo "Files created:"
echo "- railway.json (Railway config)"
echo "- nixpacks.toml (Build config)"
echo "- Procfile (Process file)"
echo "- railway-deploy.sh (Auto-deploy script)"
echo "- test-railway.sh (Test script)"
echo "- RAILWAY_QUICKSTART.md (Guide)"
echo -e "${GREEN}======================================${NC}"