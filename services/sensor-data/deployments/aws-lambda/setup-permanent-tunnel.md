# Setting Up Permanent Cloudflare Tunnel

## Step 1: Create Free Cloudflare Account
1. Go to https://dash.cloudflare.com/sign-up
2. Sign up with email (no credit card needed)
3. Verify your email

## Step 2: Set Up Zero Trust (Free for up to 50 users)
1. After login, go to: https://one.dash.cloudflare.com/
2. Click "Set up Zero Trust" 
3. Choose the free plan (50 users)
4. Create a team name (e.g., "munbon-team")

## Step 3: Create Named Tunnel
```bash
# 1. Login with your new account
cloudflared tunnel login

# 2. Create a permanent named tunnel
cloudflared tunnel create munbon-api

# Output will show:
# Created tunnel munbon-api with id: abc123-def456-ghi789
# Your tunnel ID is permanent!
```

## Step 4: Configure Tunnel
```bash
# Create config file
cat > ~/.cloudflared/config.yml << EOF
tunnel: YOUR_TUNNEL_ID
credentials-file: /Users/$USER/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: munbon-api.YOUR_TEAM.cloudflareaccess.com
    service: http://localhost:3000
  - service: http_status:404
EOF
```

## Step 5: Create DNS Route
```bash
# This creates your permanent subdomain
cloudflared tunnel route dns munbon-api munbon-api.YOUR_TEAM.cloudflareaccess.com
```

## Step 6: Run Tunnel
```bash
# Start your permanent tunnel
cloudflared tunnel run munbon-api

# Your permanent URL:
# https://munbon-api.YOUR_TEAM.cloudflareaccess.com
```

## Alternative: Use Tunnel's Built-in Domain
If you don't want to set up Zero Trust, you can use the tunnel UUID directly:
```bash
# After creating tunnel, your permanent URL is:
https://YOUR_TUNNEL_ID.cfargotunnel.com
```

## Making it Permanent as a Service

### macOS:
```bash
# Install as service
sudo cloudflared service install
sudo launchctl start com.cloudflare.cloudflared
```

### Using PM2:
```bash
npm install -g pm2
pm2 start cloudflared -- tunnel run munbon-api
pm2 save
pm2 startup
```

## Free Permanent Options Summary:

1. **Cloudflare Zero Trust**: 
   - URL: `https://munbon-api.YOUR_TEAM.cloudflareaccess.com`
   - Completely free for 50 users
   - Most professional option

2. **Cloudflare Tunnel UUID**: 
   - URL: `https://YOUR_TUNNEL_ID.cfargotunnel.com`
   - Always free
   - Less readable URL

3. **ngrok with Account**:
   - URL: `https://munbon-api.ngrok-free.app`
   - Free tier available
   - Easy setup