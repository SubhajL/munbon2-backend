# Mock API Server with Cloudflare Tunnel via moonup.hopto.org

## Investigation Results

### Current Situation
1. **moonup.hopto.org** - Currently points to IP: 182.53.226.237 (your MSSQL server)
2. **Existing Cloudflare Tunnel** - "munbon-api" (ID: f3b89263-1265-4843-b08c-5391e73e8c75)
3. **Domain Control** - hopto.org is a free DDNS service by No-IP

### Challenge with moonup.hopto.org
- **DNS Control**: hopto.org domains are managed by No-IP, not Cloudflare
- **CNAME Limitation**: Cannot add Cloudflare CNAME records to hopto.org subdomains
- **Current Use**: Already pointing to your MSSQL database server

## Recommended Solutions

### Option 1: Use Subdomain Pattern (RECOMMENDED)
Since you cannot directly use moonup.hopto.org with Cloudflare, use a different pattern:

```bash
# Use Cloudflare's free subdomain
mock-api.moonup.trycloudflare.com  # Temporary
```

### Option 2: Port-Based Routing on Existing Server
If moonup.hopto.org points to a server you control:
```
moonup.hopto.org:4010  # Mock API
moonup.hopto.org:1433  # MSSQL (existing)
```

### Option 3: Get a Free Domain for API
1. Register free domain at Freenom (.tk, .ml, .ga, .cf)
2. Point it to Cloudflare nameservers
3. Use Cloudflare tunnel with full control

## Setup Guide: Permanent Cloudflare Tunnel for Mock API

### Step 1: Create Dedicated Mock API Tunnel Config

```bash
# Create new config for mock API
cat > ~/.cloudflared/mock-api-config.yml << EOF
tunnel: f3b89263-1265-4843-b08c-5391e73e8c75
credentials-file: $HOME/.cloudflared/f3b89263-1265-4843-b08c-5391e73e8c75.json

ingress:
  # Mock API Server
  - hostname: mock-api.munbon.com
    service: http://localhost:4010
  # Catch-all (required)
  - service: http_status:404
EOF
```

### Step 2: Setup DNS (if you have domain control)
```bash
# If you have a domain in Cloudflare
cloudflared tunnel route dns munbon-api mock-api.yourdomain.com
```

### Step 3: Start Services

**Terminal 1 - Mock Server:**
```bash
cd api-contracts
npm run mock:server  # Runs on 0.0.0.0:4010
```

**Terminal 2 - Cloudflare Tunnel:**
```bash
cloudflared tunnel --config ~/.cloudflared/mock-api-config.yml run
```

## Alternative: Quick Tunnel (No Domain Needed)

For immediate testing without domain setup:

```bash
# Terminal 1: Start mock server
cd api-contracts
npm run mock:server

# Terminal 2: Create temporary tunnel
cloudflared tunnel --url http://localhost:4010
# This gives you: https://something.trycloudflare.com
```

## Docker Compose Solution

Create `docker-compose.mock-tunnel.yml`:

```yaml
version: '3.8'

services:
  mock-api:
    image: stoplight/prism:4
    command: mock -h 0.0.0.0 /openapi/sensor-data-service.yaml
    volumes:
      - ./openapi:/openapi:ro
    ports:
      - "4010:4010"
    
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    depends_on:
      - mock-api
```

## Permanent Solution Architecture

```
Internet → Cloudflare Network → Cloudflare Tunnel → Local Services
                                        ↓
                              ┌─────────┴──────────┐
                              │                    │
                    mock-api.domain.com    api.domain.com
                              ↓                    ↓
                        localhost:4010      localhost:3000
                        (Prism Mock)        (Real API)
```

## Why moonup.hopto.org Won't Work Directly

1. **DNS Management**: hopto.org DNS is controlled by No-IP, not you
2. **CNAME Records**: Cannot add Cloudflare tunnel CNAME to hopto.org
3. **Conflict**: Already used for MSSQL server access

## Best Practice Recommendation

1. **Keep moonup.hopto.org** for MSSQL database access (current use)
2. **Use Cloudflare tunnel** with temporary URL for mock API
3. **Future**: Consider getting a free domain you control for permanent setup

## Quick Start Commands

```bash
# Option 1: Temporary tunnel (easiest)
cd api-contracts
./start-mock-server-external.sh  # Terminal 1
cloudflared tunnel --url http://localhost:4010  # Terminal 2

# Option 2: Use existing permanent tunnel
cloudflared tunnel run munbon-api  # Uses existing tunnel
```

The temporary Cloudflare tunnel is perfect for mock API testing and avoids the domain control issues with moonup.hopto.org.