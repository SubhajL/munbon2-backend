#!/bin/bash

# Deploy to Render.com - The reliable free hosting solution
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "Deploy to Render.com"
echo "======================================"
echo -e "${NC}"

# Check if render.yaml exists
if [ -f "render.yaml" ]; then
    echo -e "${YELLOW}render.yaml already exists. Updating...${NC}"
else
    echo -e "${GREEN}Creating render.yaml...${NC}"
fi

# Create render.yaml
cat > render.yaml << 'EOF'
services:
  # Web Service
  - type: web
    name: munbon-unified-api
    runtime: node
    buildCommand: npm install --production
    startCommand: node src/unified-api-v2.js
    healthCheckPath: /health
    envVars:
      - key: NODE_ENV
        value: production
      - key: PORT
        value: 3000
      - key: INTERNAL_API_KEY
        value: munbon-internal-f3b89263126548
      # TimescaleDB settings (we'll use Render's PostgreSQL instead)
      - key: TIMESCALE_HOST
        fromDatabase:
          name: munbon-timescale
          property: host
      - key: TIMESCALE_PORT
        fromDatabase:
          name: munbon-timescale
          property: port
      - key: TIMESCALE_DB
        fromDatabase:
          name: munbon-timescale
          property: database
      - key: TIMESCALE_USER
        fromDatabase:
          name: munbon-timescale
          property: user
      - key: TIMESCALE_PASSWORD
        fromDatabase:
          name: munbon-timescale
          property: password
      # MSSQL settings (external)
      - key: MSSQL_HOST
        value: moonup.hopto.org
      - key: MSSQL_PORT
        value: 1433
      - key: MSSQL_DB
        value: db_scada
      - key: MSSQL_USER
        value: sa
      - key: MSSQL_PASSWORD
        value: bangkok1234

databases:
  # PostgreSQL with TimescaleDB extension
  - name: munbon-timescale
    databaseName: sensor_data
    user: munbon
    plan: free
EOF

echo -e "${GREEN}✓ render.yaml created${NC}"

# Create Dockerfile for Render
echo -e "${YELLOW}Creating Dockerfile for Render...${NC}"
cat > Dockerfile.render << 'EOF'
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies
RUN npm ci --only=production || npm install --production

# Copy application files
COPY src/unified-api-v2.js ./src/

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1); })"

# Start application
CMD ["node", "src/unified-api-v2.js"]
EOF

echo -e "${GREEN}✓ Dockerfile.render created${NC}"

# Create a simplified version for direct deployment
echo -e "${YELLOW}Creating simplified unified API for Render...${NC}"
cat > src/unified-api-render.js << 'EOF'
const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// Use Render's PostgreSQL as TimescaleDB replacement
const timescaleDB = new Pool({
  connectionString: process.env.DATABASE_URL || 
    `postgresql://${process.env.TIMESCALE_USER}:${process.env.TIMESCALE_PASSWORD}@${process.env.TIMESCALE_HOST}:${process.env.TIMESCALE_PORT}/${process.env.TIMESCALE_DB}`,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});

// Copy the rest from unified-api-v2.js but use the Pool above
EOF

# Append the rest of unified-api-v2.js
tail -n +21 src/unified-api-v2.js >> src/unified-api-render.js

echo -e "${GREEN}✓ unified-api-render.js created${NC}"

# Update package.json for Render
echo -e "${YELLOW}Updating package.json...${NC}"
if command -v jq &> /dev/null; then
    jq '.scripts.start = "node src/unified-api-render.js"' package.json > package.json.tmp && mv package.json.tmp package.json
else
    echo -e "${YELLOW}jq not found, please manually update package.json start script${NC}"
fi

# Create deployment instructions
cat > RENDER_DEPLOYMENT.md << 'EOF'
# Render.com Deployment Instructions

## Quick Start

1. **Sign up** at https://render.com (free, no credit card required)

2. **Connect GitHub**:
   - Go to Dashboard → New → Web Service
   - Connect your GitHub account
   - Select your repository

3. **Configure Service**:
   - **Name**: munbon-unified-api
   - **Runtime**: Node
   - **Build Command**: `npm install --production`
   - **Start Command**: `node src/unified-api-render.js`

4. **Environment Variables** (auto-filled from render.yaml):
   - All variables will be set automatically
   - Database will be created automatically

5. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment (5-10 minutes)

## Manual CLI Deployment

```bash
# Install Render CLI (optional)
brew tap render-oss/render
brew install render

# Deploy
render up
```

## Get Your API URL

After deployment, your API will be available at:
```
https://munbon-unified-api.onrender.com
```

## Update AWS Lambda

Run this command with your Render URL:
```bash
aws lambda update-function-configuration \
    --function-name munbon-sensor-handler \
    --environment "Variables={UNIFIED_API_URL=https://munbon-unified-api.onrender.com,INTERNAL_API_KEY=munbon-internal-f3b89263126548}" \
    --region ap-southeast-1
```

## Notes

- Free tier services sleep after 15 minutes of inactivity
- First request after sleep takes ~30 seconds (cold start)
- For always-on service, upgrade to paid plan ($7/month)
EOF

echo -e "${GREEN}✓ Deployment instructions created${NC}"

# Create test script
cat > test-render-deployment.sh << 'EOF'
#!/bin/bash

RENDER_URL="${RENDER_URL:-https://munbon-unified-api.onrender.com}"
API_KEY="munbon-internal-f3b89263126548"

echo "Testing Render deployment..."
echo "URL: $RENDER_URL"
echo ""

# Test health
echo "1. Testing health endpoint..."
curl -s "$RENDER_URL/health" | jq .

# Test API
echo -e "\n2. Testing API endpoint..."
curl -s "$RENDER_URL/api/v1/sensors/water-level/latest" \
  -H "x-internal-key: $API_KEY" | jq .

# Test Lambda
echo -e "\n3. Testing through Lambda..."
curl -s "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest" \
  -H "x-api-key: test-key-123" | jq .
EOF

chmod +x test-render-deployment.sh

echo -e "\n${GREEN}======================================"
echo "Render.com Deployment Setup Complete!"
echo "======================================"
echo -e "${NC}"
echo "Next steps:"
echo "1. Create account at https://render.com"
echo "2. Connect your GitHub repository"
echo "3. Render will auto-detect render.yaml and deploy"
echo "4. Update AWS Lambda with your Render URL"
echo ""
echo "Files created:"
echo "- render.yaml (Render configuration)"
echo "- Dockerfile.render (Container setup)"
echo "- src/unified-api-render.js (Optimized for Render)"
echo "- RENDER_DEPLOYMENT.md (Instructions)"
echo "- test-render-deployment.sh (Test script)"
echo -e "${GREEN}======================================${NC}"