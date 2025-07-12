#!/bin/bash

# Deploy to Fly.io - Global edge deployment
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================"
echo "Deploy to Fly.io"
echo "======================================"
echo -e "${NC}"

# Create fly.toml
echo -e "${GREEN}Creating Fly.io configuration...${NC}"
cat > fly.toml << 'EOF'
# fly.toml - Fly.io configuration
app = "munbon-unified-api"
primary_region = "sin"  # Singapore, closest to Thailand
kill_signal = "SIGINT"
kill_timeout = 5

[build]
  builder = "heroku/buildpacks:22"

[env]
  NODE_ENV = "production"
  PORT = "8080"

[experimental]
  auto_rollback = true

[[services]]
  http_checks = []
  internal_port = 8080
  protocol = "tcp"
  script_checks = []

  [services.concurrency]
    hard_limit = 100
    soft_limit = 80
    type = "connections"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [[services.tcp_checks]]
    grace_period = "1s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"

  [[services.http_checks]]
    interval = "30s"
    grace_period = "5s"
    method = "get"
    path = "/health"
    protocol = "http"
    restart_limit = 0
    timeout = "2s"
    tls_skip_verify = false

[mounts]
  destination = "/data"
  source = "munbon_data"
EOF

# Create Dockerfile for Fly.io
cat > Dockerfile.fly << 'EOF'
FROM node:18-alpine

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies
RUN npm ci --only=production || npm install --production

# Copy application
COPY src/unified-api-v2.js ./src/

# Create data directory for persistent storage
RUN mkdir -p /data

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:8080/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1); })"

# Start application
CMD ["node", "src/unified-api-v2.js"]
EOF

# Create .dockerignore
cat > .dockerignore << 'EOF'
node_modules
npm-debug.log
.env
.env.*
.git
.gitignore
README.md
.next
.vercel
coverage
.nyc_output
dist
build
*.log
EOF

# Create deployment script
cat > fly-deploy.sh << 'EOF'
#!/bin/bash

echo "Deploying to Fly.io..."

# Check if Fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "Installing Fly CLI..."
    curl -L https://fly.io/install.sh | sh
    export FLYCTL_INSTALL="/home/$USER/.fly"
    export PATH="$FLYCTL_INSTALL/bin:$PATH"
fi

# Authenticate
echo "Authenticating with Fly.io..."
fly auth login

# Launch app (only needed first time)
if [ ! -f "fly.toml" ]; then
    echo "Launching new Fly app..."
    fly launch --name munbon-unified-api --region sin --no-deploy
fi

# Create PostgreSQL database
echo "Creating PostgreSQL database..."
fly postgres create --name munbon-db --region sin --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1

# Attach database to app
echo "Attaching database..."
fly postgres attach munbon-db --app munbon-unified-api

# Set secrets (environment variables)
echo "Setting environment variables..."
fly secrets set INTERNAL_API_KEY=munbon-internal-f3b89263126548 \
    MSSQL_HOST=moonup.hopto.org \
    MSSQL_PORT=1433 \
    MSSQL_DB=db_scada \
    MSSQL_USER=sa \
    MSSQL_PASSWORD=bangkok1234

# Deploy
echo "Deploying application..."
fly deploy

# Show app info
echo "Getting app info..."
fly info
fly status

echo "Deployment complete!"
echo "Your app URL: https://munbon-unified-api.fly.dev"
EOF

chmod +x fly-deploy.sh

# Create Fly-specific app file with optimizations
cat > src/app-fly.js << 'EOF'
// Fly.io optimized version with persistent storage support
const express = require('express');
const { Pool } = require('pg');
const sql = require('mssql');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json());
app.use(cors());

// Fly.io provides DATABASE_URL for attached Postgres
const timescaleDB = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Use Fly.io persistent storage for caching
const CACHE_DIR = '/data/cache';
if (!fs.existsSync(CACHE_DIR)) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
}

// Port binding for Fly.io
const PORT = process.env.PORT || 8080;

// Bind to all interfaces for Fly.io
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Fly.io Unified API running on port ${PORT}`);
  console.log('Region:', process.env.FLY_REGION);
  console.log('App Name:', process.env.FLY_APP_NAME);
});
EOF

# Create monitoring script
cat > monitor-fly.sh << 'EOF'
#!/bin/bash

# Monitor Fly.io deployment
echo "Monitoring Fly.io deployment..."

# Check status
fly status

# View logs
echo -e "\nRecent logs:"
fly logs --limit 50

# Check regions
echo -e "\nDeployed regions:"
fly regions list

# Monitor in real-time
echo -e "\nStarting real-time monitoring (Ctrl+C to stop)..."
fly logs
EOF

chmod +x monitor-fly.sh

# Create scaling configuration
cat > fly-scaling.toml << 'EOF'
# Scaling configuration for Fly.io

# Auto-scale based on traffic
[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1
  max_machines_running = 3

# Scale based on these metrics
[metrics]
  cpu_threshold = 80
  memory_threshold = 90
  response_time_threshold = 1000

# Regions to scale to
[regions]
  primary = "sin"  # Singapore
  backups = ["nrt", "hkg"]  # Tokyo, Hong Kong
EOF

# Create quick start guide
cat > FLY_IO_GUIDE.md << 'EOF'
# Fly.io Deployment Guide

## Why Fly.io?

- **Global edge network** - Deploy close to users
- **Persistent storage** - Built-in volumes
- **Auto-scaling** - Scale based on traffic
- **WebSocket support** - Real-time features
- **Great free tier** - 3 VMs, 3GB storage

## 🚀 Quick Deploy

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Deploy
./fly-deploy.sh
```

## 🌏 Regions

Default: Singapore (sin)
Available: Tokyo (nrt), Hong Kong (hkg), Sydney (syd)

Change region:
```bash
fly regions add nrt hkg
fly scale count 2 --region sin
```

## 💾 Persistent Storage

Fly provides persistent volumes:
```bash
fly volumes create munbon_data --size 1 --region sin
```

## 🔧 Environment Variables

Set secrets securely:
```bash
fly secrets set KEY=value
fly secrets list
```

## 📊 Monitoring

```bash
# Status
fly status

# Logs
fly logs

# Metrics
fly dashboard
```

## 🚄 Performance

- Edge deployment reduces latency
- Automatic SSL/TLS
- HTTP/2 support
- Built-in caching

## 💰 Pricing

Free tier includes:
- 3 shared-cpu-1x VMs (256MB RAM)
- 3GB persistent storage  
- 160GB outbound transfer

## 🔄 Update AWS Lambda

```bash
aws lambda update-function-configuration \
    --function-name munbon-sensor-handler \
    --environment "Variables={UNIFIED_API_URL=https://munbon-unified-api.fly.dev,INTERNAL_API_KEY=munbon-internal-f3b89263126548}" \
    --region ap-southeast-1
```

## 📝 Custom Domain

```bash
fly certs add yourdomain.com
fly certs show yourdomain.com
```

## 🆘 Troubleshooting

1. **App won't start**: Check `fly logs`
2. **Database issues**: Run `fly postgres connect`
3. **Scaling issues**: Check `fly scale show`
4. **SSL issues**: Run `fly certs check`

EOF

echo -e "\n${GREEN}======================================"
echo "Fly.io Deployment Setup Complete!"
echo "======================================"
echo -e "${NC}"
echo "Deploy with:"
echo -e "${YELLOW}./fly-deploy.sh${NC}"
echo ""
echo "Features:"
echo "- Global edge deployment (Singapore region)"
echo "- Persistent storage support"
echo "- Auto-scaling capabilities"
echo "- Built-in PostgreSQL"
echo ""
echo "Files created:"
echo "- fly.toml (Fly configuration)"
echo "- Dockerfile.fly (Optimized container)"
echo "- fly-deploy.sh (Deployment script)"
echo "- monitor-fly.sh (Monitoring script)"
echo "- FLY_IO_GUIDE.md (Complete guide)"
echo -e "${GREEN}======================================${NC}"